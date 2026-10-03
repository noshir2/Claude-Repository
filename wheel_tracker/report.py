"""Plain-English text and HTML reports."""
from html import escape

from .analyze import Analysis


def money(x: float, sign: bool = True) -> str:
    """$1,234.50 style. With sign=True, positives get a leading +."""
    prefix = "-" if x < 0 else ("+" if sign else "")
    return f"{prefix}${abs(x):,.2f}"


def verdict(a: Analysis) -> str:
    total = a.realized
    if not a.legs and not a.stock_sales:
        return "No finished trades found yet, so there is no result to report."
    if total >= 0:
        line = f"Overall you are UP {money(total, False)} in cash actually made."
    else:
        line = f"Overall you are DOWN {money(total, False)} in cash actually lost."
    held = [t for t in a.tickers.values() if t.open_shares > 0]
    if held and any(t.price is None for t in held):
        line += (" This does not include the value of shares you still hold, which can be higher "
                 "or lower than what you paid. Pass --price TICKER=PRICE to include them.")
    return line


def _sections(a: Analysis) -> dict:
    wins, total_legs = a.win_rate()
    ann = a.put_return_annualized()
    held = [t for t in a.tickers.values() if t.open_shares > 0]
    return {
        "headline": [
            ("Cash-secured puts (premium kept, minus buybacks)", a.total("put_pnl")),
            ("Covered calls (premium kept, minus buybacks)", a.total("call_pnl")),
            ("Gain/loss selling shares you were assigned", a.total("stock_pnl")),
            ("Other options you bought", a.total("long_pnl")),
        ],
        "wins": (wins, total_legs),
        "annualized": ann,
        "held": held,
    }


def text_report(a: Analysis) -> str:
    s = _sections(a)
    out = [f"WHEEL RESULTS as of {a.today}", "=" * 60, verdict(a), ""]
    out.append(f"Total made so far (finished trades only): {money(a.realized)}")
    for label, value in s["headline"]:
        out.append(f"   {label:<52}{money(value):>12}")
    out.append(f"Premium collected on contracts still open: {money(a.open_premium, False)}"
               "  (NOT counted above - it is not yours until the contract ends)")
    wins, n = s["wins"]
    if n:
        out.append(f"Finished option sales that made money: {wins} of {n} ({wins / n:.0%})")
    if s["annualized"] is not None:
        out.append(f"Puts only: about {s['annualized']:.1%} per year on the cash you had set aside "
                   "(ignores any stock gain/loss)")

    out += ["", "BY TICKER", "-" * 60,
            f"{'Ticker':<8}{'Puts':>11}{'Calls':>11}{'Shares':>11}{'Total':>12}"]
    for t in sorted(a.tickers.values(), key=lambda t: -t.realized):
        out.append(f"{t.underlying:<8}{money(t.put_pnl):>11}{money(t.call_pnl + t.long_pnl):>11}"
                   f"{money(t.stock_pnl):>11}{money(t.realized):>12}")

    if s["held"]:
        out += ["", "SHARES YOU STILL HOLD", "-" * 60]
        for t in s["held"]:
            avg = t.open_cost / t.open_shares
            line = (f"{t.underlying}: {t.open_shares:g} shares, paid ${avg:,.2f} each. "
                    f"Break-even price (counting everything made on {t.underlying}): ${t.breakeven:,.2f}.")
            if t.unrealized is not None:
                line += f" At ${t.price:,.2f} the shares are {money(t.unrealized)}."
            out.append(line)

    months = a.by_month()
    if months:
        out += ["", "BY MONTH (by the date each trade finished)", "-" * 60]
        out += [f"{m}  {money(v):>12}" for m, v in months.items()]

    out += ["", "OPEN OPTION POSITIONS", "-" * 60]
    if a.open_options:
        for o in sorted(a.open_options, key=lambda o: o.expiry):
            kind = "put" if o.right == "P" else "call"
            out.append(f"{o.underlying} ${o.strike:g} {kind}, {o.direction} {o.qty}, expires {o.expiry}: "
                       f"{money(o.premium, False)} premium so far")
    else:
        out.append("None.")

    notes = list(a.warnings)
    if a.assumed_expired:
        names = ", ".join(sorted({l.contract for l in a.assumed_expired}))
        notes.append(
            f"I counted {len({l.contract for l in a.assumed_expired})} contract(s) as expired worthless "
            "(you kept the full premium) because the export has no buyback and no matching share purchase. "
            "Webull's order export does not list assignments. If any were actually assigned, add the "
            f"contract symbol to data/assigned.txt (one per line) and re-run. Contracts: {names}")
    if notes:
        out += ["", "PLEASE CHECK", "-" * 60] + [f"* {n}" for n in notes]
    return "\n".join(out)


def html_report(a: Analysis) -> str:
    s = _sections(a)

    def table(headers, rows):
        head = "".join(f"<th>{escape(h)}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td class='{c}'>{escape(v)}</td>" for v, c in r) + "</tr>"
                       for r in rows)
        return f"<table><tr>{head}</tr>{body}</table>"

    def m(x):
        return (money(x), "pos" if x >= 0 else "neg")

    ticker_rows = [[(t.underlying, ""), m(t.put_pnl), m(t.call_pnl + t.long_pnl), m(t.stock_pnl), m(t.realized)]
                   for t in sorted(a.tickers.values(), key=lambda t: -t.realized)]
    leg_rows = [[(str(l.closed), ""), (l.underlying, ""),
                 (f"${l.strike:g} {'put' if l.right == 'P' else 'call'} ({l.direction} {l.qty})", ""),
                 (l.outcome, ""), m(l.pnl)] for l in reversed(a.legs)]
    month_rows = [[(mo, ""), m(v)] for mo, v in a.by_month().items()]
    held_rows = [[(t.underlying, ""), (f"{t.open_shares:g}", ""), (f"${t.open_cost / t.open_shares:,.2f}", ""),
                  (f"${t.breakeven:,.2f}", ""), m(t.unrealized) if t.unrealized is not None else ("n/a", "")]
                 for t in s["held"]]
    notes = "".join(f"<li>{escape(n)}</li>" for n in a.warnings)
    if a.assumed_expired:
        notes += ("<li>Counted as expired worthless (Webull's export does not list assignments). If any were "
                  "assigned, add the symbol to data/assigned.txt: "
                  + escape(", ".join(sorted({l.contract for l in a.assumed_expired}))) + "</li>")
    headline = "".join(f"<div class='row'><span>{escape(k)}</span><b class='{'pos' if v >= 0 else 'neg'}'>"
                       f"{money(v)}</b></div>" for k, v in s["headline"])
    big_cls = "pos" if a.realized >= 0 else "neg"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Wheel results</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mute:#666;--line:#ddd;--pos:#0a7d33;--neg:#c0262d}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16181b;--fg:#e8e8e8;--mute:#9aa;--line:#33383d;--pos:#4cc77a;--neg:#ff6b72}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px}}
h1{{margin:.2em 0}}h2{{margin-top:1.6em;border-bottom:1px solid var(--line)}}
.big{{font-size:2.2em;font-weight:700}}.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.mute{{color:var(--mute)}}
.row{{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px solid var(--line)}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}}
td.pos,td.neg{{text-align:right;font-variant-numeric:tabular-nums}}
.wrap{{overflow-x:auto}}
</style></head><body>
<h1>Wheel results</h1><p class="mute">As of {a.today}</p>
<p class="big {big_cls}">{money(a.realized)}</p>
<p>{escape(verdict(a))}</p>
{headline}
<p class="mute">Premium on contracts still open: {money(a.open_premium, False)} (not counted until they end).</p>
<h2>By ticker</h2><div class="wrap">{table(["Ticker", "Puts", "Calls", "Shares", "Total"], ticker_rows)}</div>
{"<h2>Shares you still hold</h2><div class='wrap'>" + table(["Ticker", "Shares", "Paid each", "Break-even", "Unrealized"], held_rows) + "</div>" if held_rows else ""}
<h2>By month</h2><div class="wrap">{table(["Month", "Made"], month_rows)}</div>
<h2>Every finished option trade</h2><div class="wrap">{table(["Finished", "Ticker", "Contract", "How it ended", "Result"], leg_rows)}</div>
{"<h2>Please check</h2><ul>" + notes + "</ul>" if notes else ""}
</body></html>"""
