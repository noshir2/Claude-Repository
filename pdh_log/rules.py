"""Renewal rules, one dict per state. Illinois (IL) is the only state shipped.

Every value below comes from the verified facts file for this tool: 68 Ill. Adm. Code 1380.310 and
1380.325 as amended 49 Ill. Reg. 10161, effective July 23, 2025 (checked against the official ILGA
text on 2026-10-21), the IDFPR "Professional Engineer License Renewal PDH Requirement" sheet (April
2026) and IDFPR carry-over form f2476. The citation for each entry is in the comment above it and is
printed by `python3 -m pdh_log rules`.

To add another state, copy the IL dict, change the values, and cite that state's rule for each one.
Never guess a value: if a state's rule is not known, leave the state out.
"""

IL = {
    "name": "Illinois Professional Engineer (PE)",
    "rule_version": ("68 Ill. Adm. Code 1380.310 and 1380.325, as amended 49 Ill. Reg. 10161, "
                     "effective July 23, 2025"),
    "source_url": "https://ilga.gov/commission/jcar/admincode/068/068013800003250R.html",

    # Licenses expire November 30 of each odd-numbered year.            68 IAC 1380.310(a)
    "period_end_month": 11,
    "period_end_day": 30,
    "period_end_year_parity": "odd",
    # The pre-renewal period is the 24 months before that date.         68 IAC 1380.325(a)(4)
    "period_months": 24,

    # 30 PDH per renewal (IDFPR: 3 core + 27 elective).                 68 IAC 1380.325(a)(1); IDFPR PDH sheet
    "total_hours": 30,
    # Core hours, required every renewal, counted WITHIN the 30.
    # key: (minimum hours, plain-English label, citation)
    "core": {
        # min 1 PDH on Illinois statutes and Part 1380.                68 IAC 1380.325(a)(2)(A)
        "statutes_rules": (1, "Illinois statutes and rules (Part 1380)", "1380.325(a)(2)(A)"),
        # min 1 PDH professional conduct and/or ethics.                68 IAC 1380.325(a)(2)(B)
        "ethics": (1, "Professional conduct / ethics", "1380.325(a)(2)(B)"),
        # 1 PDH sexual harassment prevention training.                 68 IAC 1380.325(a)(3); 1130.400
        "harassment": (1, "Sexual harassment prevention training", "1380.325(a)(3); 1130.400"),
    },

    # Carry-over into the next period: max 15 PDH.                      68 IAC 1380.325(a)(8)
    "carryover_max": 15,
    # Only hours earned in the six months before the deadline, which IDFPR phrases as
    # June 1 through November 30 of the renewal year.                   68 IAC 1380.325(a)(8); IDFPR PDH sheet
    "carryover_window_start_month": 6,
    "carryover_window_start_day": 1,
    # Only hours not needed for that period's own 30; core hours never carry.  68 IAC 1380.325(a)(8)
    # Document carried hours on this form and keep it with your records.       68 IAC 1380.325(a)(8); form f2476
    "carryover_form": "IDFPR form f2476 (PE-CO)",

    # One PDH = at least 50 minutes of instruction or participation.    68 IAC 1380.325(a)(5)
    "pdh_minutes": 50,
    # Max 12 PDH in any 24-hour period (midnight to midnight).           68 IAC 1380.325(a)(5)
    "daily_cap": 12,

    # Keep records for 6 years.                                          68 IAC 1380.325(d)(1)
    "record_retention_years": 6,
    # What the record must contain (a bare log is NOT accepted).         68 IAC 1380.325(d)(1)(A),(B); (d)(2)
    "record_must_contain": [
        "name and address of the sponsor/provider",
        "number of PDHs for each program",
        "date and place",
        "a certificate of attendance",
        "a brief statement of the subject matter",
        "program schedule, registration receipt or other proof of participation "
        "(or a transcript kept by an acceptable provider)",
    ],
    # First renewal after initial Illinois licensure: no hours to report (fee still due).  68 IAC 1380.325(j)(1)
    "first_renewal_exempt": True,

    # Activity credits and conversions, for typing the right number of hours. Display only;
    # the tool does not convert for you.                                 68 IAC 1380.325(b)
    "activity_credits": [
        ("College/university course", "15 PDH per semester hour; 10 PDH per quarter hour", "1380.325(b)(1)"),
        ("Course, seminar, webinar, in-house or online course", "1 PDH per 50-minute hour", "1380.325(b)(2)"),
        ("Self-study", "counts only with an exam graded by the sponsor", "1380.325(b)(3)"),
        ("Program presentation at a society meeting", "actual presentation time", "1380.325(b)(4)"),
        ("Teaching a PE course or presentation", "3 PDH per hour presented, first time only", "1380.325(b)(5)"),
        ("Authoring a paper/article or presenting it", "10 PDH per paper or presentation, not both", "1380.325(b)(6)"),
        ("Patent received in the period", "10 PDH per patent", "1380.325(b)(7)"),
        ("PE board/committee membership or society office", "2 PDH each, max 8 PDH per period", "1380.325(b)(8)"),
        ("1 CEU", "10 PDH", "1380.325(a)(5)"),
        ("IDFPR Design newsletter quiz (70%+)", "0.25 PDH toward the statutes/rules hour", "IDFPR newsletter 34"),
    ],
}

STATES = {"IL": IL}

VERIFY_NOTE = ("Verify with IDFPR before relying on this; the rules changed in 2025 and can change again. "
               "This is a bookkeeping aid, not legal advice.")


class UnknownStateError(ValueError):
    pass


def get_rules(state: str) -> dict:
    key = (state or "").strip().upper()
    if key not in STATES:
        raise UnknownStateError(
            f"only these states are shipped: {', '.join(sorted(STATES))}. '{state}' is not one of them. "
            "Rules for another state must be added to pdh_log/rules.py with their citations.")
    return STATES[key]


def rule_lines(rules: dict) -> list[tuple[str, str, str]]:
    """(rule, value, citation) rows for the `rules` command and the README, built from the dict."""
    months = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December"]
    end = f"{months[rules['period_end_month']]} {rules['period_end_day']}"
    win = f"{months[rules['carryover_window_start_month']]} {rules['carryover_window_start_day']}"
    lines = [
        ("License expires", f"{end} of each {rules['period_end_year_parity']}-numbered year", "1380.310(a)"),
        ("Renewal period", f"the {rules['period_months']} months ending on that date", "1380.325(a)(4)"),
        ("Total PDH per renewal", f"{rules['total_hours']} PDH", "1380.325(a)(1)"),
    ]
    for _, (hours, label, cite) in rules["core"].items():
        lines.append((f"Core hour: {label}", f"min {hours:g} PDH each renewal, within the {rules['total_hours']}", cite))
    lines += [
        ("Carry-over maximum", f"{rules['carryover_max']} PDH", "1380.325(a)(8)"),
        ("Carry-over window", f"hours earned {win} - {end} of the renewal year and not needed for that period",
         "1380.325(a)(8); IDFPR PDH sheet"),
        ("Carry-over exclusions", "statutes/rules, ethics and harassment hours never carry; re-earn them each period",
         "1380.325(a)(8)"),
        ("Carry-over paperwork", f"document on {rules['carryover_form']} and keep it with your records",
         "1380.325(a)(8); form f2476"),
        ("1 PDH equals", f"at least {rules['pdh_minutes']} minutes of instruction or participation", "1380.325(a)(5)"),
        ("Daily cap", f"max {rules['daily_cap']} PDH in any 24-hour period (midnight to midnight)", "1380.325(a)(5)"),
        ("Record retention", f"{rules['record_retention_years']} years", "1380.325(d)(1)"),
        ("Record must contain", "; ".join(rules["record_must_contain"]) + ". A bare log is not accepted.",
         "1380.325(d)(1)(A),(B); (d)(2)"),
        ("First renewal after initial licensure", "no hours to report (fee still due; claim the waiver)",
         "1380.325(j)(1)"),
    ]
    return lines
