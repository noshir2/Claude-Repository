from datetime import date
from pathlib import Path

import pytest

from pdh_log.__main__ import main
from pdh_log.log import HEADER, Entry, LogFormatError, append_entry, load_log, normalize_category
from pdh_log.report import html_report, rules_text, text_report, verdict
from pdh_log.rules import IL, UnknownStateError, get_rules, rule_lines
from pdh_log.status import apply_daily_cap, carryover_for, compute_status, period_ending, renewal_period

TODAY = date(2026, 10, 21)
SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "pdh_log_sample.csv"
HEADER_LINE = ",".join(HEADER) + "\n"


def row(d, hours, cat="elective", title="Course", provider="Example Engineering Society", cert="", line=0):
    return Entry(date.fromisoformat(d), hours, title, provider, cat, "webinar", "online", cert, "", line)


def write_log(tmp_path, lines, name="pdh_log.csv"):
    p = tmp_path / name
    p.write_text(HEADER_LINE + "".join(lines), encoding="utf-8")
    return p


# ---------------------------------------------------------------- period math (68 IAC 1380.310(a), 1380.325(a)(4))

@pytest.mark.parametrize("today, start, end", [
    # even year, before Nov 30 -> next odd year's Nov 30
    (date(2026, 10, 21), date(2025, 12, 1), date(2027, 11, 30)),
    # odd year, on the expiration day itself -> that period still
    (date(2027, 11, 30), date(2025, 12, 1), date(2027, 11, 30)),
    # odd year, the day after expiration -> new period
    (date(2027, 12, 1), date(2027, 12, 1), date(2029, 11, 30)),
    (date(2027, 12, 5), date(2027, 12, 1), date(2029, 11, 30)),
    # even year, after Nov 30 -> still the period ending next odd year
    (date(2026, 12, 15), date(2025, 12, 1), date(2027, 11, 30)),
    # first day of a period
    (date(2025, 12, 1), date(2025, 12, 1), date(2027, 11, 30)),
    # odd year, early -> that year's Nov 30
    (date(2025, 1, 2), date(2023, 12, 1), date(2025, 11, 30)),
])
def test_renewal_period(today, start, end):
    assert renewal_period(today, IL) == (start, end)


def test_period_ending_rejects_even_year():
    assert period_ending(2025, IL) == (date(2023, 12, 1), date(2025, 11, 30))
    with pytest.raises(ValueError, match="odd-numbered"):
        period_ending(2026, IL)


# ---------------------------------------------------------------- parsing

def test_load_sample_and_categories():
    entries = load_log(SAMPLE)
    assert len(entries) == 13                      # comment lines are skipped
    cats = {e.date.isoformat(): e.category for e in entries}
    assert cats["2024-05-20"] == "ethics"          # typed as "Ethics"
    assert cats["2024-09-09"] == "harassment"      # typed as "sexual harassment"
    assert cats["2026-01-20"] == "statutes_rules"  # typed as "Statutes and rules"
    assert entries[0].line == 5                    # header is line 1, three comment lines, first row is line 5


@pytest.mark.parametrize("text, want", [
    ("Ethics", "ethics"), ("professional conduct", "ethics"), ("Statutes/Rules", "statutes_rules"),
    ("Illinois statutes & rules", "statutes_rules"), ("SEXUAL HARASSMENT", "harassment"),
    ("sexual-harassment-prevention", "harassment"), ("elective", "elective"), ("", "elective"),
    # the full labels the tool prints, copied back into the category column
    ("Sexual harassment prevention training", "harassment"), ("Professional conduct / ethics", "ethics"),
    ("Illinois statutes and rules (Part 1380)", "statutes_rules"), ("IL statutes and rules", "statutes_rules"),
    # "elective" wins over any core keyword, so an elective course is never counted as a core hour
    ("elective - NEC rules", "elective"), ("Elective (code rules)", "elective"), ("general ethics reading", "elective"),
])
def test_normalize_category(text, want):
    assert normalize_category(text) == want


def test_ambiguous_category_is_refused():
    with pytest.raises(LogFormatError, match="could be ethics or harassment"):
        normalize_category("ethics and harassment")


def test_bad_category_names_line(tmp_path):
    p = write_log(tmp_path, ["2026-01-05,1,Course,Provider,elective,,,,\n",
                             "2026-01-06,1,Course,Provider,safety,,,,\n"])
    with pytest.raises(LogFormatError, match="line 3: category 'safety'"):
        load_log(p)


def test_bad_date_and_hours_name_line(tmp_path):
    p = write_log(tmp_path, ["# a comment\n", "01/05/2026,1,Course,Provider,elective,,,,\n"])
    with pytest.raises(LogFormatError, match="line 3: date '01/05/2026'"):
        load_log(p)
    p = write_log(tmp_path, ["2026-01-05,one,Course,Provider,elective,,,,\n"])
    with pytest.raises(LogFormatError, match="line 2: hours 'one'"):
        load_log(p)
    p = write_log(tmp_path, ["2026-01-05,0,Course,Provider,elective,,,,\n"])
    with pytest.raises(LogFormatError, match="line 2: hours must be more than 0"):
        load_log(p)
    for bad in ("inf", "nan"):   # float() accepts these; they must not reach the math
        p = write_log(tmp_path, [f"2026-01-05,{bad},Course,Provider,elective,,,,\n"])
        with pytest.raises(LogFormatError, match=f"line 2: hours '{bad}' is not a number"):
            load_log(p)


def test_quoted_cell_with_line_break_keeps_line_numbers(tmp_path):
    # line 2-3 is ONE row (Excel Alt+Enter inside a quoted title; the continuation starts with '#'),
    # line 4 is good, line 5 has the bad category -> the message must say line 5, not 4
    p = write_log(tmp_path, ['2026-01-05,1,"Course with\n', '# newline in title",Provider,elective,,,,\n',
                             "2026-01-06,1,Second,Provider,elective,,,,\n",
                             "2026-01-07,1,Third,Provider,badcat,,,,\n"])
    with pytest.raises(LogFormatError, match="line 5: category 'badcat'"):
        load_log(p)
    p = write_log(tmp_path, ['2026-01-05,1,"Course with\n', '# newline in title",Provider,elective,,,,\n',
                             "2026-01-06,1,Second,Provider,elective,,,,\n"])
    entries = load_log(p)
    assert [e.line for e in entries] == [2, 4]
    assert entries[0].title == "Course with\n# newline in title"   # the '#' line is not a comment


def test_excel_ansi_save_is_read(tmp_path):
    # Windows Excel 'CSV (Comma delimited)' writes cp1252: 0x96 is an en dash, invalid as UTF-8
    p = tmp_path / "pdh_log.csv"
    p.write_bytes(HEADER_LINE.encode("ascii") + b"2026-01-05,1,Arc\x96flash course,Provider,elective,,,,\n")
    entries = load_log(p)
    assert entries[0].title == "Arc\u2013flash course"
    # a UTF-8 file with Excel's BOM still works
    p.write_text(HEADER_LINE + "2026-01-05,1,Arc\u2013flash course,Provider,elective,,,,\n", encoding="utf-8-sig")
    assert load_log(p)[0].title == "Arc\u2013flash course"


def test_wrong_header_is_rejected(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Date,Hours\n2026-01-05,1\n", encoding="utf-8")
    with pytest.raises(LogFormatError, match="header must be exactly"):
        load_log(p)


def test_missing_file_message(tmp_path):
    with pytest.raises(LogFormatError, match="log file not found"):
        load_log(tmp_path / "none.csv")


# ---------------------------------------------------------------- daily cap (68 IAC 1380.325(a)(5))

def test_daily_cap_trims_elective_last_row_first():
    # 8 + 5 on one day = 13 -> cap 12, the 5-hour row (later in the file) counts 4
    e = [row("2026-03-10", 8, line=2), row("2026-03-10", 5, line=3), row("2026-03-11", 2, line=4)]
    counted, flagged = apply_daily_cap(e, 12)
    assert [c.counted for c in counted] == [8, 4, 2]
    assert flagged == [(date(2026, 3, 10), 13, 12)]


def test_daily_cap_report_names_trimmed_rows():
    # 13 hours in one ethics row: the cut comes off that core row, and the report must say so
    s = compute_status([row("2026-01-05", 13, "ethics", title="Ethics marathon", line=2)], TODAY)
    assert s.flagged_days == [(date(2026, 1, 5), 13, 12)]
    assert "came off: Ethics marathon (-1)" in text_report(s)
    assert "came off: Ethics marathon (-1)" in html_report(s)


def test_daily_cap_keeps_core_rows():
    # 1 ethics + 12 elective on one day = 13 -> the elective row is trimmed to 11, ethics keeps its 1
    e = [row("2026-03-10", 1, "ethics", line=2), row("2026-03-10", 12, line=3)]
    counted, _ = apply_daily_cap(e, 12)
    assert [c.counted for c in counted] == [1, 11]


# ---------------------------------------------------------------- carry-over (68 IAC 1380.325(a)(8))

PREV = (date(2023, 12, 1), date(2025, 11, 30))


def test_carryover_basic():
    # previous period: 3 core + 20 elective early + 9 elective in window = 32; spare 2; window 9 -> 2
    e = [row("2024-01-10", 1, "statutes_rules"), row("2024-01-11", 1, "ethics"), row("2024-01-12", 1, "harassment"),
         row("2024-06-01", 10), row("2025-01-15", 10), row("2025-08-01", 9)]
    c = carryover_for(e, *PREV, IL)
    assert (c.prev_total, c.surplus, c.window_elective, c.hours) == (32, 2, 9, 2)
    assert c.window_start == date(2025, 6, 1) and c.window_end == date(2025, 11, 30)


def test_carryover_window_filter():
    # 40 hours but all before June 1 2025 -> spare 10, window 0 -> carry 0
    e = [row("2024-02-01", 12), row("2024-03-01", 12), row("2024-04-01", 12), row("2025-05-31", 4)]
    assert carryover_for(e, *PREV, IL).hours == 0
    # same, but the last 4 fall on June 1 -> 4 can carry
    e[-1] = row("2025-06-01", 4)
    assert carryover_for(e, *PREV, IL).hours == 4


def test_carryover_excludes_core_hours():
    # 30 elective early + 1 ethics in window = 31; spare 1, but no elective in window -> 0
    e = [row("2024-02-01", 12), row("2024-03-01", 12), row("2024-04-01", 6), row("2025-09-01", 1, "ethics")]
    assert carryover_for(e, *PREV, IL).hours == 0


def test_carryover_only_hours_not_needed():
    # 28 total with 10 in window: short of 30, nothing is spare -> 0
    e = [row("2024-02-01", 12), row("2024-03-01", 6), row("2025-09-01", 10)]
    assert carryover_for(e, *PREV, IL).hours == 0
    # 31 total with 10 in window -> only 1 spare
    e.append(row("2025-10-01", 3))
    assert carryover_for(e, *PREV, IL).hours == 1


def test_carryover_chains_across_periods():
    # period ending 2023: 3 core + 12 + 12 + 3 early + 10 in window = 40 -> 10 carry into the 2025 period
    # period ending 2025: 3 core + 12 + 5 early + 10 in window = 30 own hours; with the 10 carried in,
    # only 20 own hours were needed, so 10 are spare and all 10 window hours carry on (matches the
    # --period 2025 view, which says 40 of 30)
    e = [row("2022-01-10", 1, "statutes_rules"), row("2022-01-11", 1, "ethics"), row("2022-01-12", 1, "harassment"),
         row("2022-03-01", 12), row("2022-04-01", 12), row("2022-05-01", 3), row("2023-09-01", 10),
         row("2024-01-10", 1, "statutes_rules"), row("2024-01-11", 1, "ethics"), row("2024-01-12", 1, "harassment"),
         row("2024-03-01", 12), row("2024-04-01", 5), row("2025-09-01", 10)]
    c = carryover_for(e, *PREV, IL)
    assert (c.prev_total, c.carried_in, c.surplus, c.window_elective, c.hours) == (30, 10, 10, 10, 10)
    assert "plus 10 carried into it" in c.sentence()
    past = compute_status(e, TODAY, period_year=2025)
    assert past.total == 40 and past.carryover.hours == 10
    now = compute_status(e, TODAY)
    assert now.carryover.hours == 10 and now.total == 10
    # the forward-looking line has the same chain: 4 carried in + 28 own (10 in the 2027 window) -> 2 spare
    e2 = e + [row("2026-01-10", 1, "statutes_rules"), row("2026-01-11", 1, "ethics"), row("2026-01-12", 1, "harassment"),
              row("2026-03-01", 12), row("2026-04-01", 3), row("2027-07-01", 10)]
    s2 = compute_status(e2, date(2027, 8, 1))
    assert s2.carryover.hours == 10 and s2.earned == 28
    assert s2.next_period_carryover().hours == 8       # 28 + 10 - 30 = 8, within the 10 window hours
    # no rows before the previous period -> nothing carried in (base case, no recursion)
    assert carryover_for(e[7:], *PREV, IL).carried_in == 0


def test_carryover_capped_at_15():
    # 12 + 12 + 12 early + 12 + 12 in window = 60; spare 30; window 24 -> min(15, 30, 24) = 15
    e = [row("2024-02-01", 12), row("2024-03-01", 12), row("2024-04-01", 12),
         row("2025-07-01", 12), row("2025-08-01", 12)]
    assert carryover_for(e, *PREV, IL).hours == 15


def test_carryover_uses_capped_hours():
    # one 13-hour day in the window counts 12: 12 + 12 + 12 early + 13 (->12) = 48 counted; spare 18; window 12 -> 12
    e = [row("2024-02-01", 12), row("2024-03-01", 12), row("2024-04-01", 12), row("2025-07-01", 13)]
    c = carryover_for(e, *PREV, IL)
    assert (c.prev_total, c.hours) == (48, 12)


# ---------------------------------------------------------------- status on the shipped sample

@pytest.fixture
def sample_status():
    return compute_status(load_log(SAMPLE), TODAY, SAMPLE)


def test_sample_period_and_totals(sample_status):
    s = sample_status
    assert (s.start, s.end) == (date(2025, 12, 1), date(2027, 11, 30))
    assert s.days_left == 405                      # 2026-10-21 -> 2027-11-30
    # current period rows: 1 statutes + 8 + 5 (same day, 13 -> 12) + 2 + 2 = 18 raw, 17 counted
    assert s.earned == 17
    assert s.by_category == {"elective": 16, "statutes_rules": 1, "ethics": 0, "harassment": 0}
    assert s.elective == 16
    # previous period: 1+1+1+10+4+6+8+3 = 34, spare 4; window (Jun-Nov 2025) elective 6+8+3 = 17 -> carry 4
    assert s.carryover.hours == 4
    assert s.total == 21 and s.short_by == 9


def test_sample_core_hours(sample_status):
    core = sample_status.core
    assert core["statutes_rules"] == (1, 1, True)
    assert core["ethics"] == (0, 1, False)
    assert core["harassment"] == (0, 1, False)
    assert sample_status.missing == ["9 more hours", "the ethics hour", "the harassment hour"]


def test_sample_verdict_names_period_end(sample_status):
    v = verdict(sample_status)
    assert v == ("You have 21 of 30 hours for the period ending 2027-11-30 (17 earned this period plus 4 carried "
                 "over) and still need 9 more hours, the ethics hour and the harassment hour.")


def test_sample_daily_cap_flag(sample_status):
    assert sample_status.flagged_days == [(date(2026, 3, 10), 13, 12)]
    counted = {(c.entry.date.isoformat(), c.entry.hours): c.counted for c in sample_status.rows}
    assert counted[("2026-03-10", 8)] == 8 and counted[("2026-03-10", 5)] == 4


def test_sample_record_check(sample_status):
    s = sample_status
    assert [e.date.isoformat() for e in s.missing_certificate] == ["2026-06-08"]
    assert [e.date.isoformat() for e, _ in s.certificate_not_found] == ["2026-09-22"]
    assert s.certificate_not_found[0][1] == SAMPLE.parent / "pdh_log_certs/2026-09-22-motor.pdf"


def test_past_period_option():
    s = compute_status(load_log(SAMPLE), TODAY, SAMPLE, period_year=2025)
    assert (s.start, s.end) == (date(2023, 12, 1), date(2025, 11, 30))
    assert s.earned == 34 and s.carryover.hours == 0 and s.short_by == 0
    assert all(met for _, _, met in s.core.values())
    assert s.next_period_carryover().hours == 4
    assert s.days_left == -325


def test_all_met_verdict():
    e = [row("2026-01-10", 1, "statutes_rules"), row("2026-01-11", 1, "ethics"), row("2026-01-12", 1, "harassment"),
         row("2026-02-01", 12), row("2026-03-01", 12), row("2026-04-01", 4)]
    s = compute_status(e, TODAY)
    assert s.total == 31 and s.missing == []
    assert verdict(s) == "You have 31 of 30 hours for the period ending 2027-11-30 and all three core hours; nothing is missing."


def test_short_by_one_hour_is_singular():
    e = [row("2026-01-10", 1, "statutes_rules"), row("2026-01-11", 1, "ethics"), row("2026-01-12", 1, "harassment"),
         row("2026-02-01", 12), row("2026-03-01", 12), row("2026-04-01", 2)]
    s = compute_status(e, TODAY)
    assert s.total == 29 and s.missing == ["1 more hour"]


def test_warnings_future_date_and_odd_fraction():
    # 0.25 is the IDFPR newsletter quiz credit (rules.py activity_credits) and must not be flagged
    e = [row("2027-01-10", 1, line=2), row("2026-01-10", 0.4, line=3), row("2026-01-11", 0.25, line=4)]
    s = compute_status(e, TODAY)
    assert any("line 2" in w and "after today" in w for w in s.warnings)
    assert any("line 3" in w and "0.4" in w and "multiple of 0.25" in w for w in s.warnings)
    assert not any("line 4" in w for w in s.warnings)


def test_unknown_state():
    with pytest.raises(UnknownStateError, match="only these states are shipped: IL"):
        get_rules("WI")
    assert get_rules("il") is IL


# ---------------------------------------------------------------- add

def test_append_creates_file_with_header(tmp_path):
    p = tmp_path / "data" / "pdh_log.csv"
    append_entry(p, row("2026-10-15", 1, "ethics", cert="certs/x.pdf"))
    append_entry(p, row("2026-10-16", 1.5))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ",".join(HEADER)
    assert lines[1].startswith("2026-10-15,1,Course,Example Engineering Society,ethics,webinar,online,certs/x.pdf,")
    assert lines[2].startswith("2026-10-16,1.5,")
    assert [e.hours for e in load_log(p)] == [1, 1.5]


def test_append_refuses_foreign_header(tmp_path):
    p = tmp_path / "other.csv"
    p.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(LogFormatError, match="does not start with the header"):
        append_entry(p, row("2026-10-16", 1))
    assert p.read_text(encoding="utf-8") == "foo,bar\n1,2\n"     # untouched


def test_cli_add_then_status(tmp_path, capsys):
    log = tmp_path / "pdh_log.csv"
    assert main(["add", "--log", str(log), "--date", "2026-10-15", "--hours", "1", "--title", "Ethics webinar",
                 "--provider", "Example Engineering Society", "--category", "Ethics"]) == 0
    out = capsys.readouterr().out
    assert "2026-10-15,1,Ethics webinar,Example Engineering Society,ethics" in out
    assert main(["status", "--log", str(log), "--today", "2026-10-21", "--html", str(tmp_path / "r.html")]) == 0
    out = capsys.readouterr().out
    assert "You have 1 of 30 hours for the period ending 2027-11-30" in out
    assert "the Illinois statutes/rules hour and the harassment hour" in out
    assert "Verify with IDFPR" in out                       # footer note
    assert (tmp_path / "r.html").read_text(encoding="utf-8").startswith("<!doctype html>")


def test_cli_errors_return_1(tmp_path, capsys):
    assert main(["--state", "WI", "status", "--log", str(SAMPLE), "--html", ""]) == 1
    assert "Problem: only these states are shipped" in capsys.readouterr().err
    assert main(["status", "--log", str(tmp_path / "none.csv"), "--html", ""]) == 1
    assert "Problem: log file not found" in capsys.readouterr().err
    assert main(["status", "--log", str(SAMPLE), "--period", "2026", "--html", ""]) == 1
    assert "odd-numbered" in capsys.readouterr().err
    assert main(["add", "--log", str(tmp_path / "x.csv"), "--date", "2026-1-5", "--hours", "1",
                 "--title", "t", "--provider", "p", "--category", "elective"]) == 1
    assert "Problem: date" in capsys.readouterr().err


# ---------------------------------------------------------------- reports and rules

def test_reports_render(sample_status):
    text = text_report(sample_status)
    for piece in ["21 of 30", "NOT MET", "2026-03-10: 13 PDH logged, only 12 count", "no certificate_file",
                  "not found", "f2476", "Verify with IDFPR", "at most 15"]:
        assert piece in text
    html = html_report(sample_status)
    assert "<html" in html and "prefers-color-scheme" in html and "21 / 30 PDH" in html
    assert "<script" not in html and "http" not in html    # no JS, no network


def test_rules_output_has_citations():
    text = rules_text("IL", IL)
    for cite in ["1380.310(a)", "1380.325(a)(1)", "1380.325(a)(2)(A)", "1380.325(a)(2)(B)", "1380.325(a)(3)",
                 "1380.325(a)(8)", "1380.325(a)(5)", "1380.325(d)(1)", "1380.325(j)(1)", "1380.325(b)(1)"]:
        assert cite in text
    assert "Verify with IDFPR" in text and "f2476" in text
    labels = [label for label, _, _ in rule_lines(IL)]
    assert "Daily cap" in labels and "Carry-over maximum" in labels


def test_rule_values_match_verified_facts():
    # Table 1 of the facts file
    assert (IL["period_end_month"], IL["period_end_day"], IL["period_end_year_parity"]) == (11, 30, "odd")
    assert IL["period_months"] == 24 and IL["total_hours"] == 30
    assert {k: v[0] for k, v in IL["core"].items()} == {"statutes_rules": 1, "ethics": 1, "harassment": 1}
    assert IL["carryover_max"] == 15 and (IL["carryover_window_start_month"], IL["carryover_window_start_day"]) == (6, 1)
    assert IL["daily_cap"] == 12 and IL["pdh_minutes"] == 50 and IL["record_retention_years"] == 6
