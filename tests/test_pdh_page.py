"""pdh_log/pdh.html: the JavaScript logic block must agree with the Python package, and the embedded
example list must be byte-identical to samples/pdh_log_sample.csv."""
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from pdh_log.log import LogFormatError, load_log, parse_hours
from pdh_log.status import compute_status

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "pdh_log" / "pdh.html"
SAMPLE = ROOT / "samples" / "pdh_log_sample.csv"

# several "today" values: an ordinary day, the expiration day itself, the day after (new period),
# the end of the previous period and the first day of the current one
TODAYS = ["2026-10-21", "2027-11-30", "2027-12-01", "2025-11-30", "2025-12-01"]

RUNNER = """
const PDH = require(process.argv[2]);
const fs = require("fs");
const csv = fs.readFileSync(process.argv[3], "utf8");
const todays = JSON.parse(process.argv[4]);
const entries = PDH.parseCSV(csv);
function pack(s) {
  return {start: s.start, end: s.end, days_left: s.daysLeft, by_category: s.byCategory,
          core_met: Object.fromEntries(Object.entries(s.core).map(([k, v]) => [k, v.met])),
          core_have: Object.fromEntries(Object.entries(s.core).map(([k, v]) => [k, v.have])),
          carryover: s.carryover.hours, carry_detail: [s.carryover.prevTotal, s.carryover.carriedIn, s.carryover.surplus, s.carryover.windowElective],
          earned: s.earned, elective: s.elective, total: s.total, short_by: s.shortBy,
          flagged: s.flaggedDays.map(f => [f.day, f.raw, f.cap]),
          counted: s.rows.map(c => [c.entry.date, c.entry.hours, c.counted]),
          missing_cert: s.missingCertificate.map(e => e.date), missing: s.missing,
          next_carry: s.nextCarryover.hours, warnings: s.warnings.length,
          carry_sentence: PDH.carryoverSentence(s.carryover)};
}
const out = {entries: entries.map(e => [e.date, e.hours, e.category, e.line, e.certificate_file]), views: {}};
for (const t of todays) {
  const cur = pack(PDH.computeStatus(entries, t));
  const prevYear = +cur.end.slice(0, 4) - 2;
  out.views[t] = {current: cur, previous: pack(PDH.computeStatus(entries, t, {periodYear: prevYear}))};
}
out.verdict = PDH.verdict(PDH.computeStatus(entries, "2026-10-21"));
out.roundtrip = PDH.parseCSV(PDH.toCSV(entries)).map(e => [e.date, e.hours, e.title, e.category, e.certificate_file, e.notes]);
out.csv_quoting = PDH.toCSV([PDH.makeEntry({date: "2026-01-05", hours: "1.5", title: 'Arc, "flash"', provider: "P", category: "Ethics", notes: "a\\nb"}, 2)]);
out.categories = ["Ethics", "professional conduct", "Statutes/Rules", "Illinois statutes & rules", "SEXUAL HARASSMENT",
                  "sexual-harassment-prevention", "elective", "", "Sexual harassment prevention training",
                  "Professional conduct / ethics", "Illinois statutes and rules (Part 1380)", "IL statutes and rules",
                  "elective - NEC rules", "Elective (code rules)", "general ethics reading"].map(t => PDH.normalizeCategory(t));
out.bad = [];
for (const t of ["ethics and harassment", "safety"]) { try { PDH.normalizeCategory(t); out.bad.push("ok"); } catch (e) { out.bad.push(e.message); } }
for (const h of ["one", "0", "inf", "nan", "", "0x10", "0b11", "0o7", "1,5", "1e"]) { try { PDH.parseHours(h); out.bad.push("ok"); } catch (e) { out.bad.push(e.message); } }
out.hours_ok = ["1_000", " 1.5 ", ".5", "5.", "1e1", "+2", "1e1_0", "-0.25"].map(h => { try { return PDH.parseHours(h); } catch (e) { return e.message; } });
for (const d of ["01/05/2026", "2026-1-5", "2026-02-30"]) { try { PDH.parseDate(d); out.bad.push("ok"); } catch (e) { out.bad.push(e.message); } }
out.cap = (() => {   // 8 + 5 on one day -> the later row counts 4; 1 ethics + 12 elective -> elective trimmed to 11
  const mk = (d, h, cat, line) => PDH.makeEntry({date: d, hours: h, title: "t", provider: "p", category: cat}, line);
  const a = PDH.applyDailyCap([mk("2026-03-10", 8, "elective", 2), mk("2026-03-10", 5, "elective", 3), mk("2026-03-11", 2, "elective", 4)], 12);
  const b = PDH.applyDailyCap([mk("2026-03-10", 1, "ethics", 2), mk("2026-03-10", 12, "elective", 3)], 12);
  return [a.rows.map(c => c.counted), a.flagged, b.rows.map(c => c.counted)];
})();
out.periods = ["2026-10-21", "2027-11-30", "2027-12-01", "2027-12-05", "2026-12-15", "2025-12-01", "2025-01-02"].map(t => PDH.renewalPeriod(t, PDH.IL));
out.quoted = PDH.parseCSV('date,hours,title,provider,category,format,location,certificate_file,notes\\n2026-01-05,1,"Course with\\n# newline in title",Provider,elective,,,,\\n2026-01-06,1,Second,Provider,elective,,,,\\n').map(e => [e.line, e.title]);
console.log(JSON.stringify(out));
"""


def _pack(s):
    return {"start": s.start.isoformat(), "end": s.end.isoformat(), "days_left": s.days_left,
            "by_category": s.by_category,
            "core_met": {k: v[2] for k, v in s.core.items()}, "core_have": {k: v[0] for k, v in s.core.items()},
            "carryover": s.carryover.hours,
            "carry_detail": [s.carryover.prev_total, s.carryover.carried_in, s.carryover.surplus, s.carryover.window_elective],
            "earned": s.earned, "elective": s.elective, "total": s.total, "short_by": s.short_by,
            "flagged": [[d.isoformat(), raw, cap] for d, raw, cap in s.flagged_days],
            "counted": [[c.entry.date.isoformat(), c.entry.hours, c.counted] for c in s.rows],
            "missing_cert": [e.date.isoformat() for e in s.missing_certificate], "missing": s.missing,
            "next_carry": s.next_period_carryover().hours, "warnings": len(s.warnings),
            "carry_sentence": s.carryover.sentence()}


def test_embedded_sample_is_byte_identical():
    html = HTML.read_bytes()
    m = re.search(rb'<script type="text/plain" id="sample-pdh">(.*?)</script>', html, re.S)
    assert m, "no sample-pdh block in pdh.html"
    assert m.group(1) == SAMPLE.read_bytes()


def test_page_has_no_external_resources_or_popups():
    html = HTML.read_text(encoding="utf-8")
    assert "<script id=\"logic\">" in html
    assert not re.search(r'<(script|link|img)[^>]+(src|href)="https?://', html)
    assert not re.search(r"\b(alert|confirm|prompt)\(", html)
    assert "Try it with example data" in html and "Back to the toolbox" in html


def test_page_has_the_novice_routes_and_wording():
    """Round-2 review: a paste box next to the file chooser, a 'Mark as saved' button, no 'licence', no rule
    citations in the status card's required-hour rows (they live in the rules table)."""
    html = HTML.read_text(encoding="utf-8")
    for needle in ['id="f-paste"', 'id="btn-paste-import"', '"Mark as saved"', 'id="load-note"', "Brought in ",
                   "Added: ", "Save As", "Notepad", 'el("span", "inline-btns")']:
        assert needle in html, needle
    assert "licence" not in html.lower().replace("licensure", "")
    assert '", rule " + c.cite' not in html


@pytest.fixture(scope="module")
def js():
    if shutil.which("node") is None:
        pytest.skip("node is not installed, so the JavaScript twin cannot be checked")
    tmp = Path(__file__).resolve().parent / "__pycache__" / "pdh_page_js"
    tmp.mkdir(parents=True, exist_ok=True)
    html = HTML.read_text(encoding="utf-8")
    logic = re.search(r'<script id="logic">(.*?)</script>', html, re.S).group(1)
    assert not re.search(r"\b(document|window|localStorage|navigator)\.[A-Za-z_]", logic), "the logic block must be DOM-free"
    (tmp / "logic.js").write_text(logic, encoding="utf-8")
    (tmp / "run.js").write_text(RUNNER, encoding="utf-8")
    res = subprocess.run(["node", str(tmp / "run.js"), str(tmp / "logic.js"), str(SAMPLE), json.dumps(TODAYS)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_js_reads_sample_like_python(js):
    entries = load_log(SAMPLE)
    assert js["entries"] == [[e.date.isoformat(), e.hours, e.category, e.line, e.certificate_file] for e in entries]
    assert js["roundtrip"] == [[e.date.isoformat(), e.hours, e.title, e.category, e.certificate_file, e.notes] for e in entries]
    assert js["quoted"] == [[2, "Course with\n# newline in title"], [4, "Second"]]
    assert '"Arc, ""flash"""' in js["csv_quoting"]


@pytest.mark.parametrize("today", TODAYS)
def test_js_status_matches_python(js, today):
    entries = load_log(SAMPLE)
    t = date.fromisoformat(today)
    cur = compute_status(entries, t, SAMPLE)
    assert js["views"][today]["current"] == _pack(cur)
    prev = compute_status(entries, t, SAMPLE, period_year=cur.end.year - 2)
    assert js["views"][today]["previous"] == _pack(prev)


def test_js_sample_numbers_are_the_known_ones(js):
    # hand-worked in tests/test_pdh_log.py: 17 earned + 4 carried = 21, short by 9, one day over the cap
    v = js["views"]["2026-10-21"]["current"]
    assert (v["start"], v["end"], v["days_left"]) == ("2025-12-01", "2027-11-30", 405)
    assert v["by_category"] == {"elective": 16, "statutes_rules": 1, "ethics": 0, "harassment": 0}
    assert v["core_met"] == {"statutes_rules": True, "ethics": False, "harassment": False}
    assert (v["carryover"], v["total"], v["short_by"]) == (4, 21, 9)
    assert v["flagged"] == [["2026-03-10", 13, 12]]
    assert v["missing_cert"] == ["2026-06-08"]
    assert js["verdict"] == ("You have 21 of 30 hours for the period ending 30 November 2027 (17 earned this period plus "
                             "4 carried over) and still need 9 more hours, the ethics hour and the harassment hour.")
    p = js["views"]["2026-10-21"]["previous"]
    assert (p["earned"], p["carryover"], p["short_by"], p["days_left"], p["next_carry"]) == (34, 0, 0, -325, 4)


def test_js_parsing_and_cap_rules(js):
    assert js["categories"] == ["ethics", "ethics", "statutes_rules", "statutes_rules", "harassment", "harassment",
                                "elective", "elective", "harassment", "ethics", "statutes_rules", "statutes_rules",
                                "elective", "elective", "elective"]
    assert "could be ethics or harassment" in js["bad"][0] and "is not one of" in js["bad"][1]
    # hours: everything Python's float() refuses (words, hex, binary, octal, a comma, a bare exponent) is refused
    # here too, and everything it accepts (underscores, spaces around, .5, 5., exponents, a sign) gives the same value
    assert [b.split(" ")[0] for b in js["bad"][2:12]] == ["hours"] * 10
    for text, got in zip(["one", "0", "inf", "nan", "", "0x10", "0b11", "0o7", "1,5", "1e"], js["bad"][2:12]):
        with pytest.raises(LogFormatError) as ex:
            parse_hours(text)
        assert got == str(ex.value)
    for text, got in zip(["1_000", " 1.5 ", ".5", "5.", "1e1", "+2", "1e1_0", "-0.25"], js["hours_ok"]):
        try:
            want = parse_hours(text)
        except LogFormatError as e:
            want = str(e)
        assert got == want, text
    assert all("is not YYYY-MM-DD" in b for b in js["bad"][12:])
    assert js["cap"] == [[8, 4, 2], [{"day": "2026-03-10", "raw": 13, "cap": 12}], [1, 11]]
    assert js["periods"] == [{"start": "2025-12-01", "end": "2027-11-30"}, {"start": "2025-12-01", "end": "2027-11-30"},
                             {"start": "2027-12-01", "end": "2029-11-30"}, {"start": "2027-12-01", "end": "2029-11-30"},
                             {"start": "2025-12-01", "end": "2027-11-30"}, {"start": "2025-12-01", "end": "2027-11-30"},
                             {"start": "2023-12-01", "end": "2025-11-30"}]
