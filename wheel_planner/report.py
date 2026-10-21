"""Plain-English text and HTML output for compare, roll and expiry."""
from datetime import date
from html import escape

from .expiry import ExpiryCheck
from .planner import Candidate, Evaluation, RollResult, Rules

DISCLAIMER = ("Estimates from numbers you typed; no live data; the odds are a rough model; "
              "this is not investment advice.")


def money(x: float, sign: bool = True) -> str:
    """$1,234.50 style. With sign=True, positives get a leading +."""
    prefix = "-" if x < 0 else ("+" if sign else "")
    return f"{prefix}${abs(x):,.2f}"


def pct(x: float | None, places: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{places}f}%"


def days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def odds_text(e: Evaluation) -> str:
    if e.odds is None:
        return "n/a (no IV typed)" if e.c.iv is None else "n/a (IV 0 typed)"
    if e.odds_source == "delta":
        return f"{pct(e.odds)} (|delta|)"
    return pct(e.odds)


def _echo_rows(cands: list[Candidate]) -> list[tuple[str, str]]:
    rows = []
    for c in cands:
        parts = [f"type {c.kind}", f"strike {c.strike:g}", f"expiry {c.expiry}", f"premium {c.premium:g}",
                 f"price {c.price:g}", f"iv {'blank' if c.iv is None else f'{c.iv:g}%'}"]
        if c.right == "C":
            parts.append(f"cost basis {'blank' if c.cost_basis is None else f'{c.cost_basis:g}'}")
        if c.earnings is not None:
            parts.append(f"earnings {c.earnings}")
        if c.delta_typed is not None:
            parts.append(f"delta {c.delta_typed:g}")
        if c.note:
            parts.append(f"note '{c.note}'")
        rows.append((c.ticker, ", ".join(parts)))
    return rows


def _settings(rules: Rules, today: date, rate_pct: float) -> list[str]:
    out = [f"today {today}", f"risk-free rate {rate_pct:g}%", f"max DTE {rules.max_dte}",
           f"max odds {rules.max_odds_pct:g}%"]
    if rules.buying_power is not None:
        out.append(f"buying power {money(rules.buying_power, False)} (checked on puts only)")
    if rules.account is not None:
        out.append(f"account {money(rules.account, False)} with max {rules.max_pct:g}% per position")
    return out


def _earnings_line(evals: list[Evaluation], has_earnings_column: bool) -> str | None:
    if not has_earnings_column:
        return None
    missing = [e.c.ticker for e in evals if e.c.earnings is None]
    if not missing:
        return None
    return f"Earnings date not typed for {', '.join(missing)}: check it before expiry."


def _oneline(e: Evaluation) -> str:
    return (f"{e.c.ticker} {e.c.kind} {e.c.strike:g} exp {e.c.expiry}: collateral {money(e.collateral, False)}, "
            f"premium {money(e.premium_dollars, False)}, return {pct(e.ret, 2)}, annualized {pct(e.annualized)}")


def text_compare(evals: list[Evaluation], rules: Rules, today: date, rate_pct: float,
                 monthly_goal: float | None = None, has_earnings_column: bool = False,
                 warnings: list[str] = ()) -> str:
    out = [f"WHEEL PLANNER: candidates as of {today}", "=" * 72, "",
           "INPUTS YOU TYPED (check them: one wrong IV or price changes every number below)", "-" * 72]
    out += [f"{t:<7} {desc}" for t, desc in _echo_rows([e.c for e in sorted(evals, key=lambda e: e.order)])]
    out.append("Settings: " + "; ".join(_settings(rules, today, rate_pct)))
    out += ["", "RANKED (best annualized return first unless --sort says otherwise)", "-" * 72]
    head = (f"{'Ticker':<7}{'Type':<5}{'Strike':>7}{'Collateral':>12}{'Premium':>9}{'Return':>8}"
            f"{'Annual':>8}{'DTE':>5}{'$/day':>7}{'Cushion':>9}{'Brk-even':>10}{'1-sigma':>10}{'Rough odds ITM':>19}")
    out.append(head)
    for e in evals:
        cushion = pct(e.cushion)
        if e.c.right == "C":
            cushion += "^"
        out.append(f"{e.c.ticker:<7}{e.c.kind:<5}{e.c.strike:>7g}{money(e.collateral, False):>12}"
                   f"{money(e.premium_dollars, False):>9}{pct(e.ret, 2):>8}{pct(e.annualized):>8}{e.dte:>5}"
                   f"{money(e.per_day, False):>7}{cushion:>9}{'$' + format(e.break_even, ',.2f'):>10}"
                   f"{('n/a' if e.sigma_move is None else '$' + format(e.sigma_move, ',.2f')):>10}"
                   f"{odds_text(e):>19}")
    out.append("^ for a call this is the upside to the strike, not a cushion.")
    notes = [f"{e.c.ticker}: {e.collateral_note}." for e in evals if e.collateral_note]
    out += notes
    out += ["", "FLAGS (your rules, as sentences; the tool does not give advice)", "-" * 72]
    fired = [f for e in evals for f in e.flags]
    earn = _earnings_line(evals, has_earnings_column)
    if earn:
        fired.append(earn)
    out += [f"* {f}" for f in fired] or ["None of your rules fired."]
    if monthly_goal is not None:
        from .planner import income_goal_sentence
        out += ["", income_goal_sentence(monthly_goal, evals)]
    if warnings:
        out += ["", "PLEASE CHECK", "-" * 72] + [f"* {w}" for w in warnings]
    out += ["", DISCLAIMER]
    return "\n".join(out)


CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mute:#666;--line:#ddd;--pos:#0a7d33;--neg:#c0262d;--flag:#fff4e0}
@media(prefers-color-scheme:dark){:root{--bg:#16181b;--fg:#e8e8e8;--mute:#9aa;--line:#33383d;--pos:#4cc77a;--neg:#ff6b72;--flag:#3a2f1c}}
body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:16px}
h1{margin:.2em 0}h2{margin-top:1.6em;border-bottom:1px solid var(--line)}
.big{font-size:2.2em;font-weight:700}.pos{color:var(--pos)}.neg{color:var(--neg)}.mute{color:var(--mute)}
.row{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px solid var(--line)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}
.flag{background:var(--flag);padding:8px 12px;margin:6px 0;border-radius:6px}
.foot{margin-top:2em;color:var(--mute);font-size:.9em;border-top:1px solid var(--line);padding-top:8px}
"""


def _table(headers, rows) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td class='{c}'>{escape(v)}</td>" for v, c in r) + "</tr>" for r in rows)
    return f"<div class='wrap'><table><tr>{head}</tr>{body}</table></div>"


def _page(title: str, body: str, today: date) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>{CSS}</style></head><body>
<h1>{escape(title)}</h1><p class="mute">As of {today}</p>
{body}
<p class="foot">{escape(DISCLAIMER)}</p>
</body></html>"""


def html_compare(evals: list[Evaluation], rules: Rules, today: date, rate_pct: float,
                 monthly_goal: float | None = None, has_earnings_column: bool = False,
                 warnings: list[str] = ()) -> str:
    echo = _table(["Ticker", "What you typed"], [[(t, ""), (d, "")] for t, d in _echo_rows([e.c for e in sorted(evals, key=lambda e: e.order)])])
    settings = escape("; ".join(_settings(rules, today, rate_pct)))
    rows = []
    for e in evals:
        n = "num"
        rows.append([(e.c.ticker, ""), (e.c.kind, ""), (f"{e.c.strike:g}", n), (money(e.collateral, False), n),
                     (money(e.premium_dollars, False), n), (pct(e.ret, 2), n), (pct(e.annualized), n),
                     (str(e.dte), n), (money(e.per_day, False), n),
                     (pct(e.cushion) + (" (upside to strike)" if e.c.right == "C" else ""), n),
                     (f"${e.break_even:,.2f}", n),
                     ("n/a" if e.sigma_move is None else f"${e.sigma_move:,.2f}", n), (odds_text(e), n)])
    table = _table(["Ticker", "Type", "Strike", "Collateral", "Premium", "Return", "Annualized", "DTE", "$/day",
                    "Cushion", "Break-even", "1-sigma move", "Rough odds ITM"], rows)
    notes = "".join(f"<p class='mute'>{escape(e.c.ticker)}: {escape(e.collateral_note)}.</p>"
                    for e in evals if e.collateral_note)
    fired = [f for e in evals for f in e.flags]
    earn = _earnings_line(evals, has_earnings_column)
    if earn:
        fired.append(earn)
    flags = "".join(f"<div class='flag'>{escape(f)}</div>" for f in fired) or "<p>None of your rules fired.</p>"
    goal = ""
    if monthly_goal is not None:
        from .planner import income_goal_sentence
        goal = f"<h2>Income goal</h2><p>{escape(income_goal_sentence(monthly_goal, evals))}</p>"
    warn = ("<h2>Please check</h2><ul>" + "".join(f"<li>{escape(w)}</li>" for w in warnings) + "</ul>") if warnings else ""
    body = (f"<h2>Inputs you typed</h2><p class='mute'>Check them: one wrong IV or price changes every number.</p>"
            f"{echo}<p class='mute'>Settings: {settings}</p>"
            f"<h2>Ranked</h2>{table}{notes}"
            f"<h2>Flags (your rules, as sentences)</h2>{flags}{goal}{warn}")
    return _page("Wheel planner: candidates", body, today)


def text_roll(r: RollResult, old: tuple, new: tuple, price: float | None, iv_pct: float | None,
              today: date, rate_pct: float, warnings: list[str] = ()) -> str:
    os_, oe, op, bb = old
    ns, ne, nc = new
    out = [f"WHEEL PLANNER: roll check as of {today}", "=" * 72,
           f"Typed: old put strike {os_:g} expiring {oe}, premium received {op:g}, buyback {bb:g}; "
           f"new put strike {ns:g} expiring {ne}, credit {nc:g}"
           + (f"; price {price:g}" if price is not None else "")
           + (f"; IV {iv_pct:g}%" if iv_pct is not None else "") + f"; rate {rate_pct:g}%", "",
           f"Net {'credit' if r.net >= 0 else 'debit'} per share: {money(r.net)}   per contract: {money(r.net_contract)}",
           f"Days added: {r.days_added} (new contract has {days(r.new_dte)} left)",
           f"Total premium collected on this position so far: {money(r.total_collected, False)} per share "
           f"({money(r.total_collected * 100, False)} per contract)",
           f"Break-even: old ${r.old_break_even:,.2f} -> new ${r.new_break_even:,.2f}",
           f"New collateral: {money(r.new_collateral, False)}"]
    if r.annualized is not None:
        out.append(f"Annualized return of the net credit on the new collateral over the {r.days_added} added days: "
                   f"{pct(r.annualized)}")
    else:
        out.append("Annualized return of the roll: n/a (no days added)")
    if r.new_odds is not None:
        out.append(f"Rough odds the new put finishes in the money: {pct(r.new_odds)}; 1-sigma move "
                   f"${r.new_sigma:,.2f} over {days(r.new_dte)}")
    else:
        out.append("Rough odds for the new put: n/a (pass --price and --iv)")
    out += ["", r.verdict]
    if warnings:
        out += ["", "PLEASE CHECK", "-" * 72] + [f"* {w}" for w in warnings]
    out += ["", DISCLAIMER]
    return "\n".join(out)


def text_expiry(x: ExpiryCheck) -> str:
    out = [f"WHEEL PLANNER: expiry check as of {x.today}", "=" * 72]
    if x.contracts:
        out.append(f"{'Ticker':<7}{'Type':<5}{'Strike':>8}{'Expires':>12}{'Days':>6}{'Qty':>4}{'Collateral':>12}  Against your price")
        for c in x.contracts:
            out.append(f"{c.ticker:<7}{c.kind:<5}{c.strike:>8g}{str(c.expiry):>12}{c.days_left:>6}{c.qty:>4}"
                       f"{(money(c.collateral, False) if c.right == 'P' else '-'):>12}  "
                       + (f"{c.moneyness} (price {c.price:g})" if c.price is not None else c.moneyness))
    else:
        out.append("No open short puts or calls found in the export (contracts past their expiry are left out).")
    out += ["", f"Cash needed if every open put is assigned: {money(x.cash_needed, False)}",
            f"Cash on hand (typed): {'not typed' if x.cash is None else money(x.cash, False)}",
            "", x.shortfall_sentence()]
    if x.warnings:
        out += ["", "PLEASE CHECK", "-" * 72] + [f"* {w}" for w in x.warnings]
    out += ["", DISCLAIMER]
    return "\n".join(out)


def html_expiry(x: ExpiryCheck) -> str:
    rows = [[(c.ticker, ""), (c.kind, ""), (f"{c.strike:g}", "num"), (str(c.expiry), ""), (str(c.days_left), "num"),
             (str(c.qty), "num"), (money(c.collateral, False) if c.right == "P" else "-", "num"), (c.moneyness, "")]
            for c in x.contracts]
    table = _table(["Ticker", "Type", "Strike", "Expires", "Days left", "Qty", "Collateral", "Against your price"],
                   rows) if rows else "<p>No open short puts or calls found.</p>"
    cls = "neg" if (x.shortfall or 0) > 0 else "pos"
    warn = ("<h2>Please check</h2><ul>" + "".join(f"<li>{escape(w)}</li>" for w in x.warnings) + "</ul>") if x.warnings else ""
    body = (f"<h2>Open short contracts</h2>{table}"
            f"<p><b class='{cls}'>{escape(x.shortfall_sentence())}</b></p>{warn}")
    return _page("Wheel planner: expiry check", body, x.today)
