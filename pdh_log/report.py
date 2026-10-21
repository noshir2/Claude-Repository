"""Plain-English text and HTML reports."""
import textwrap
from html import escape

from .rules import VERIFY_NOTE, rule_lines
from .status import Status


def hours(x: float) -> str:
    """1, 1.5, 12 - no trailing zeros."""
    return f"{x:g}"


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def verdict(s: Status) -> str:
    need = s.rules["total_hours"]
    line = f"You have {hours(s.total)} of {need} hours for the period ending {s.end}"
    if s.carryover.hours:
        line += f" ({hours(s.earned)} earned this period plus {hours(s.carryover.hours)} carried over)"
    missing = s.missing
    if missing:
        return line + f" and still need {_join(missing)}."
    return line + " and all three core hours; nothing is missing."


def _core_rows(s: Status) -> list[tuple[str, float, float, bool, str]]:
    return [(label, s.core[key][0], s.core[key][1], s.core[key][2], cite)
            for key, (need, label, cite) in s.rules["core"].items()]


def _record_lines(s: Status) -> list[str]:
    out = []
    for e in s.missing_certificate:
        out.append(f"{e.date}  {e.title} ({e.provider}): no certificate_file")
    for e, p in s.certificate_not_found:
        out.append(f"{e.date}  {e.title} ({e.provider}): certificate_file '{e.certificate_file}' not found at {p}")
    return out


def _trimmed(s: Status, day) -> str:
    """Which rows on `day` lost hours to the daily cap, e.g. 'Grounding workshop (-1)'."""
    return ", ".join(f"{c.entry.title} (-{hours(c.entry.hours - c.counted)})"
                     for c in s.rows if c.entry.date == day and c.counted < c.entry.hours)


def text_report(s: Status) -> str:
    r = s.rules
    out = [f"PDH STATUS as of {s.today} ({r['name']})", "=" * 72, verdict(s), ""]
    left = f"{s.days_left} days left" if s.days_left >= 0 else f"ended {-s.days_left} days ago"
    out += [f"Renewal period: {s.start} to {s.end}  ({left})",
            f"Hours counted this period: {hours(s.earned)}  "
            f"(elective {hours(s.elective)} + core {hours(s.earned - s.elective)})",
            f"Carry-over from previous period: {hours(s.carryover.hours)}",
            f"Total toward the {r['total_hours']}: {hours(s.total)}  -> "
            + (f"MET ({hours(s.total - r['total_hours'])} to spare)" if s.short_by == 0
               else f"short by {hours(s.short_by)}")]

    out += ["", "CORE HOURS (required every period, counted within the 30)", "-" * 72]
    for label, have, need, met, cite in _core_rows(s):
        out.append(f"{'met' if met else 'NOT MET':<8}{label:<44}{hours(have)} of {hours(need)}")
    out.append(f"{'':8}{'Elective hours':<44}{hours(s.elective)}")

    out += ["", "CARRY-OVER", "-" * 72, s.carryover.sentence()]
    nxt = s.next_period_carryover()
    if nxt.hours:
        out.append(f"If the log stays as it is, {hours(nxt.hours)} PDH could carry into the period after this one "
                   f"(hours earned {nxt.window_start} to {nxt.window_end}, elective, beyond the {r['total_hours']}).")

    out += ["", f"DAILY CAP (max {r['daily_cap']} PDH per calendar day)", "-" * 72]
    if s.flagged_days:
        for day, raw, counted in s.flagged_days:
            out.append(f"{day}: {hours(raw)} PDH logged, only {hours(counted)} count "
                       f"(the extra {hours(raw - counted)} PDH came off: {_trimmed(s, day)})")
    else:
        out.append("No day over the cap.")

    out += ["", f"RECORD CHECK (keep a certificate plus sponsor, date, place and subject for "
                f"{r['record_retention_years']} years)", "-" * 72]
    lines = _record_lines(s)
    out += [f"* {ln}" for ln in lines] if lines else ["Every row in this period has a certificate file on disk."]

    out += ["", "EVERY ROW IN THIS PERIOD", "-" * 72,
            f"{'Date':<12}{'Hours':>6}{'Counts':>7}  {'Category':<15}{'Title':<34}Provider"]
    for c in s.rows:
        e = c.entry
        out.append(f"{e.date.isoformat():<12}{hours(e.hours):>6}{hours(c.counted):>7}  {e.category:<15}"
                   f"{e.title[:32]:<34}{e.provider}")
    if not s.rows:
        out.append("(none)")

    if s.warnings:
        out += ["", "PLEASE CHECK", "-" * 72] + [f"* {w}" for w in s.warnings]

    out += ["", f"Rules: {r['rule_version']}. {VERIFY_NOTE}",
            "Run 'python3 -m pdh_log rules' to see every rule with its citation."]
    return "\n".join(out)


def rules_text(state: str, rules: dict) -> str:
    def block(label, value, cite):
        return textwrap.fill(f"{label}: {value}  [{cite}]", width=96, subsequent_indent="    ")

    out = [f"RULES USED FOR {state.upper()}: {rules['name']}", "=" * 72,
           "Each line ends with its citation in 68 Ill. Adm. Code (Part 1380 unless noted).", ""]
    out += [block(label, value, cite) for label, value, cite in rule_lines(rules)]
    out += ["", "ACTIVITY CREDITS (how many hours to type; the tool does not convert for you)", "-" * 72]
    out += [block(label, value, cite) for label, value, cite in rules["activity_credits"]]
    out += ["", f"Source text: {rules['rule_version']}", rules["source_url"], VERIFY_NOTE]
    return "\n".join(out)


def html_report(s: Status) -> str:
    r = s.rules

    def table(headers, rows):
        head = "".join(f"<th>{escape(h)}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td class='{c}'>{escape(str(v))}</td>" for v, c in row) + "</tr>"
                       for row in rows)
        return f"<table><tr>{head}</tr>{body}</table>"

    pct = min(100, round(100 * s.total / r["total_hours"])) if r["total_hours"] else 0
    period_rows = [[("Today", ""), (str(s.today), "")],
                   [("Period start", ""), (str(s.start), "")],
                   [("Period end (license expires)", ""), (str(s.end), "")],
                   [("Days left", ""), (str(s.days_left) if s.days_left >= 0 else f"ended {-s.days_left} days ago", "num")],
                   [("Hours counted this period", ""), (hours(s.earned), "num")],
                   [("Carry-over from previous period", ""), (hours(s.carryover.hours), "num")],
                   [(f"Total toward the {r['total_hours']}", ""),
                    (hours(s.total), "pos" if s.short_by == 0 else "neg")],
                   [("Short by", ""), (hours(s.short_by), "pos" if s.short_by == 0 else "neg")]]
    core_rows = [[(label, ""), (hours(have), "num"), (hours(need), "num"),
                  ("met" if met else "NOT MET", "pos" if met else "neg"), (cite, "mute")]
                 for label, have, need, met, cite in _core_rows(s)]
    core_rows.append([("Elective hours", ""), (hours(s.elective), "num"), ("", ""), ("", ""), ("", "")])
    flagged = "".join(f"<li>{day}: {hours(raw)} PDH logged, only {hours(counted)} count "
                      f"(came off: {escape(_trimmed(s, day))}).</li>"
                      for day, raw, counted in s.flagged_days) or "<li>No day over the cap.</li>"
    records = "".join(f"<li>{escape(ln)}</li>" for ln in _record_lines(s)) or \
        "<li>Every row in this period has a certificate file on disk.</li>"
    row_rows = [[(str(c.entry.date), ""), (hours(c.entry.hours), "num"), (hours(c.counted), "num"),
                 (c.entry.category, ""), (c.entry.title, ""), (c.entry.provider, ""), (c.entry.format, ""),
                 (c.entry.certificate_file or "(none)", "" if c.entry.certificate_file else "neg")]
                for c in s.rows]
    warnings = "".join(f"<li>{escape(w)}</li>" for w in s.warnings)
    nxt = s.next_period_carryover()
    nxt_line = (f"<p>If the log stays as it is, {hours(nxt.hours)} PDH could carry into the period after this one.</p>"
                if nxt.hours else "")
    big_cls = "pos" if not s.missing else "neg"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PDH status</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mute:#666;--line:#ddd;--pos:#0a7d33;--neg:#c0262d;--bar:#e6e6e6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16181b;--fg:#e8e8e8;--mute:#9aa;--line:#33383d;--pos:#4cc77a;--neg:#ff6b72;--bar:#2a2e33}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px}}
h1{{margin:.2em 0}}h2{{margin-top:1.6em;border-bottom:1px solid var(--line)}}
.big{{font-size:2.2em;font-weight:700}}.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.mute{{color:var(--mute)}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}}
td.num,td.pos,td.neg{{text-align:right;font-variant-numeric:tabular-nums}}
.bar{{background:var(--bar);border-radius:6px;height:18px;overflow:hidden;margin:8px 0}}
.bar div{{height:100%;background:var(--pos);width:{pct}%}}
.wrap{{overflow-x:auto}}
</style></head><body>
<h1>PDH status</h1><p class="mute">As of {s.today}. {escape(r['name'])}.</p>
<p class="big {big_cls}">{hours(s.total)} / {r['total_hours']} PDH</p>
<div class="bar"><div></div></div>
<p>{escape(verdict(s))}</p>
<h2>Period</h2><div class="wrap">{table(["", ""], period_rows)}</div>
<h2>Core hours</h2><div class="wrap">{table(["Requirement", "Have", "Need", "Status", "Rule"], core_rows)}</div>
<h2>Carry-over</h2><p>{escape(s.carryover.sentence())}</p>{nxt_line}
<h2>Daily cap (max {r['daily_cap']} PDH per calendar day)</h2><ul>{flagged}</ul>
<h2>Record check</h2>
<p class="mute">Illinois wants, for each course: {escape("; ".join(r['record_must_contain']))}. Keep it {r['record_retention_years']} years. A bare log is not accepted.</p>
<ul>{records}</ul>
<h2>Every row in this period</h2><div class="wrap">{table(["Date", "Hours", "Counts", "Category", "Title", "Provider", "Format", "Certificate"], row_rows)}</div>
{"<h2>Please check</h2><ul>" + warnings + "</ul>" if warnings else ""}
<p class="mute">Rules: {escape(r['rule_version'])}. {escape(VERIFY_NOTE)}</p>
</body></html>"""
