import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from frc_shop_card import calc, card, report
from frc_shop_card.__main__ import main

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "frc_shop_card"
HTML = FOLDER / "frc_shop_card.html"


@pytest.fixture(scope="module")
def data():
    return card.load_card_data(HTML)


# --- 1. AWG table from the formula -----------------------------------------------------------
# Published solid-copper values (ohm per 1000 ft at 20 C, Wikipedia / PowerStream), which the
# formula d = 0.127 x 92^((36-n)/39) and rho = 1.724e-8 ohm-m must reproduce within 2%.
PUBLISHED_OHM_PER_1000FT = {6: 0.3951, 8: 0.6282, 10: 0.9989, 12: 1.588, 14: 2.525, 16: 4.016,
                            18: 6.385, 20: 10.15, 22: 16.14, 24: 25.67}


def test_awg_formula_matches_published_table():
    # 6 AWG by hand: d = 0.127 x 92^(30/39) = 4.115 mm; area = pi x 2.0575^2 = 13.30 mm2
    # R/m = 1.724e-8 / 13.30e-6 = 1.296e-3 ohm/m; x 0.3048 = 0.3951 mohm/ft
    assert calc.awg_diameter_mm(6) == pytest.approx(4.115, rel=1e-3)
    assert calc.awg_area_mm2(6) == pytest.approx(13.30, rel=1e-3)
    assert calc.awg_mohm_per_ft(6) == pytest.approx(0.3951, rel=1e-3)
    for n, want in PUBLISHED_OHM_PER_1000FT.items():
        assert calc.awg_mohm_per_ft(n) == pytest.approx(want, rel=0.02), n
    # every 3 gauge numbers the resistance doubles: 92^(6/39) = 2.005
    assert calc.awg_mohm_per_ft(9) / calc.awg_mohm_per_ft(6) == pytest.approx(2.005, rel=1e-3)


def test_awg_table_in_html_matches_formula(data):
    rows = {r["awg"]: r for r in data["awg_table"]}
    assert sorted(rows) == list(range(6, 25))
    for n, r in rows.items():
        assert r["mohm_per_ft"] == pytest.approx(calc.awg_mohm_per_ft(n), rel=0.02)
        assert r["tag"] == "physics" and "formula" in r["source"]
    assert rows[6]["mohm_per_ft"] == pytest.approx(0.395, rel=0.02)
    assert rows[10]["mohm_per_ft"] == pytest.approx(1.0, rel=0.02)
    assert rows[12]["mohm_per_ft"] == pytest.approx(1.59, rel=0.02)
    assert rows[22]["mohm_per_ft"] == pytest.approx(16.1, rel=0.02)


def test_awg_range_enforced():
    with pytest.raises(ValueError, match="6 to 24"):
        calc.vdrop(30, 10, 10)
    with pytest.raises(ValueError, match="6 to 24"):
        calc.vdrop(6.5, 10, 10)


# --- 2-5. the golden examples, worked by hand ---------------------------------------------------
def test_vdrop_golden():
    # 10 ft one way = 20 ft of wire; 20 x 0.3951 mohm = 7.90 mohm
    # 120 A x 0.00790 ohm = 0.948 V; 0.948 / 12 = 7.9%; 120^2 x 0.00790 = 113.8 W
    r = calc.vdrop(6, 120, 10)
    assert r["round_trip_ft"] == 20
    assert r["mohm"] == pytest.approx(7.90, rel=0.01)
    assert r["volts"] == pytest.approx(0.948, rel=0.01)
    assert r["pct"] == pytest.approx(7.9, rel=0.01)
    assert r["watts"] == pytest.approx(113.8, rel=0.01)
    assert report.vdrop_sentence(r) == ("At 120 A through 10 ft of 6 AWG (20 ft round trip, 7.9 mohm) you lose "
                                        "0.95 V, about 7.9% of 12 V; the wire dissipates 114 W.")


def test_brownout_golden_forward_and_inverse():
    # total = 15 + 8 = 23 mohm; 12.6 - 300 x 0.023 = 12.6 - 6.9 = 5.7 V
    # inverse: (12.6 - 6.8) / 0.023 = 5.8 / 0.023 = 252.2 A
    r = calc.brownout(15, 8, amps=300, threshold=6.8)
    assert r["total_mohm"] == 23
    assert r["bus_v"] == pytest.approx(5.7)
    assert r["amps_at_threshold"] == pytest.approx(252.17, rel=1e-3)
    lines = report.brownout_sentences(r)
    assert lines[0].endswith("the 12.6 V battery sags to 5.70 V on the bus.")
    assert lines[1] == "To pull that 12.6 V battery down to 6.8 V through 23 mohm takes about 252 A."
    # only one side asked for
    assert "amps_at_threshold" not in calc.brownout(15, 8, amps=100)
    assert "bus_v" not in calc.brownout(15, 8, threshold=6.75)
    with pytest.raises(ValueError, match="amps"):
        calc.brownout(15, 8)
    with pytest.raises(ValueError, match="below the open-circuit"):
        calc.brownout(15, 8, threshold=13)


def test_battery_r_golden():
    # (12.6 - 11.9) / 50 = 0.7 / 50 = 0.014 ohm = 14 mohm
    r = calc.battery_r(12.6, 11.9, 50)
    assert r["mohm"] == pytest.approx(14.0)
    assert report.battery_r_sentence(r).startswith("Open-circuit 12.6 V, 11.9 V under 50 A: internal resistance about 14.0 mohm")
    with pytest.raises(ValueError, match="swap"):
        calc.battery_r(11.9, 12.6, 50)


def test_short_golden():
    # 12 + 3 = 15 mohm; 12.6 / 0.015 = 840 A; 840^2 x 0.012 = 8467 W; 12.6 x 840 = 10,584 W
    r = calc.short_circuit(12, 3)
    assert r["amps"] == pytest.approx(840)
    assert r["battery_w"] == pytest.approx(8467.2)
    assert r["total_w"] == pytest.approx(10584)
    s = report.short_sentence(r)
    assert "drives about 840 A" in s and "about 8.5 kW" in s and "whole loop at 10.6 kW" in s


def test_ohms_law_and_i2t():
    # 12 V / 4 ohm = 3 A, 36 W;  60 A for 2 s = 3600 x 2 = 7200 A^2 s
    assert calc.ohms_law(volts=12, ohms=4) == {"volts": 12, "amps": 3, "ohms": 4, "watts": 36}
    assert calc.ohms_law(amps=2, ohms=5)["volts"] == 10
    assert calc.ohms_law(volts=10, amps=4)["ohms"] == 2.5
    with pytest.raises(ValueError, match="two of the three"):
        calc.ohms_law(volts=1)
    assert calc.i2t(60, 2)["i2t"] == 7200
    assert report.i2t_sentence(calc.i2t(60, 2)).startswith("60 A for 2 s: I^2t = 7,200 A^2-s.")


# --- 6. gauge lookup reads the rule table ----------------------------------------------------
def test_gauge_lookup(data):
    # 2026 Game Manual R622 Table 8-4: 31-40 A breaker 12 AWG; 21-30 A 14 AWG; 6-20 A breaker 18 AWG;
    # 11-20 A fuse 18 AWG; <= 5 A breaker 22 AWG; <= 10 A fuse 22 AWG; <= 2 A fuse 24 AWG; <= 1 A fuse 26 AWG
    rules = data["rule_table"]
    for amps, kind, want in [(40, "breaker", 12), (30, "breaker", 14), (20, "breaker", 18), (10, "breaker", 18),
                             (5, "breaker", 22), (20, "fuse", 18), (10, "fuse", 22), (2, "fuse", 24), (1, "fuse", 26),
                             (0.5, "fuse", 26), (35, "breaker", 12)]:
        row = calc.gauge_for(rules, amps, kind)
        assert row is not None and row["min_awg"] == want, (amps, kind)
        assert row["season"] and "R622" in row["source"]
    assert calc.gauge_for(rules, 41, "breaker") is None
    assert calc.gauge_for(rules, 25, "fuse") is None
    # the 120 A main breaker is a breaker: the lookup reads the main-path row instead of 'not in the table'
    main_row = calc.gauge_for(rules, 120, "breaker")
    assert main_row["id"] == "main" and main_row["min_awg"] == 6
    assert report.gauge_sentence(120, "breaker", main_row).startswith("A 120 A breaker is the main breaker: ")
    assert calc.gauge_for(rules, 120, "fuse") is None and calc.gauge_for(rules, 119, "breaker") is None
    # limits typed as text ("31") are read as numbers, like the page does; junk limits are skipped
    typed = json.loads(json.dumps(rules))
    typed[1]["amps_min"], typed[1]["amps_max"] = "31", "40"
    assert calc.gauge_for(typed, 40, "breaker")["min_awg"] == 12
    typed[1]["amps_min"] = "thirty-one"
    assert calc.gauge_for(typed, 40, "breaker") is None
    assert report.gauge_sentence(41, "breaker", None) == "41 A breaker: not in the table, see the manual."
    s = report.gauge_sentence(40, "breaker", calc.gauge_for(rules, 40, "breaker"))
    assert s.startswith("A 40 A breaker needs at least 12 AWG (") and "verify against the current season's manual" in s


# --- 7. the checker on the real HTML -----------------------------------------------------------
def test_checker_passes_on_shipped_html(data):
    problems, counts = card.check_card(data)
    assert problems == []
    assert counts["cards"] >= 50 and counts["generated"] >= 10
    assert "all sourced" in report.check_text(problems, counts)


def test_every_row_sourced_and_tagged(data):
    for name, rows in card.tables(data).items():
        for r in rows:
            assert r["source"].strip(), (name, r)
            assert r["tag"] in card.TAGS, (name, r)
            if r["tag"] == "rule":
                assert r.get("season"), (name, r)
    assert all(r["season"] for r in data["rule_table"])
    assert all("EXAMPLE" in r["source"] for r in data["team_standards_example"])


def test_cards_cover_every_week_and_reference_real_rows(data):
    cards = data["cards"]
    assert 50 <= len(cards) <= 70
    per_week = {w: 0 for w in range(11)}
    tbl = card.tables(data)
    for c in cards:
        assert c["week"] in per_week
        per_week[c["week"]] += 1
        assert c["kind"] in card.KINDS
        if "from_table" in c:
            assert card.find_row(tbl[c["from_table"]], c["row"]) is not None, c
        else:
            assert c["front"] and c["back"] and c["source"]
    assert min(per_week.values()) >= 3, per_week
    expanded = card.expand_cards(data)
    assert len(expanded) == len(cards)
    assert len({c["id"] for c in expanded}) == len(cards)        # ids are unique
    by_id = {c["id"]: c for c in expanded}
    # a number card reads the live row: the 31-40 A breaker row says 12 AWG
    assert "12 AWG" in by_id["n:rule_table:b12"]["back"] and "season 2026" in by_id["n:rule_table:b12"]["source"]
    assert by_id["n:connectors:sl_amps"]["back"].startswith("3 A per contact")


def test_checker_reports_problems(data):
    bad = json.loads(json.dumps(data))
    bad["rule_table"][1]["source"] = ""
    del bad["rule_table"][2]["season"]
    bad["cards"][0]["week"] = 11
    bad["cards"][-1]["back"] = ""
    bad["awg_table"][0]["mohm_per_ft"] *= 1.05          # 5% off: must be caught (limit is 2%)
    bad["golden"][0]["out"]["volts"] = 2.0
    bad["cards"].append({"week": 3, "kind": "number", "from_table": "rule_table", "row": "nope", "template": "x"})
    problems, _ = card.check_card(bad)
    text = "\n".join(problems)
    assert "no source" in text and "without a season" in text and "week must be 0-10" in text
    assert "no back" in text and "differs from the formula" in text
    assert "volts expected 2.0" in text and "row 'nope' not found" in text


def test_checker_flags_duplicates_and_bad_shapes(data):
    bad = json.loads(json.dumps(data))
    bad["rule_table"].append(dict(bad["rule_table"][1], min_awg=10))      # a stray second "b12" saying 10 AWG
    bad["cards"].append(dict(bad["cards"][0]))                            # the same written card twice
    bad["cards"][6]["answer"] = None                                      # Notepad typo: null instead of "{value}"
    problems, _ = card.check_card(bad)
    text = "\n".join(problems)
    assert "duplicate id 'b12'" in text and "duplicate card (week" in text and "answer must be text" in text
    for section, value in [("cards", 5), ("rule_table", {"id": "b12"}), ("golden", "x")]:
        shape = json.loads(json.dumps(data))
        shape[section] = value
        problems, _ = card.check_card(shape)
        assert any(f"section '{section}' must be a list" in p for p in problems)
    tbl = json.loads(json.dumps(data))
    tbl["reference_tables"][0]["rows"] = 5
    assert any("must be a list of rows" in p for p in card.check_card(tbl)[0])


def test_row_without_source_is_dropped_from_cards_and_prints(data):
    # the spec's guardrail: a row with no source does not render, and that includes the flashcard
    # generated from it and the printed cheat sheet
    bad = json.loads(json.dumps(data))
    for rows, rid in [(card.tables(bad)["connectors"], "sl_amps"), (bad["rule_table"], "b12")]:
        card.find_row(rows, rid)["source"] = ""
    ids = {c["id"] for c in card.expand_cards(bad)}
    assert "n:connectors:sl_amps" not in ids and "n:rule_table:b12" not in ids
    assert len(ids) == len(card.expand_cards(data)) - 2
    assert all(c["source"] for c in card.expand_cards(bad) if c["kind"] == "number")
    assert card.check_card(bad)[0]                                        # and the checker says so
    html = HTML.read_text(encoding="utf-8")
    sheet = html[html.index("function cheatSheet()"):html.index("function quizSheet(")]
    assert "(DATA.safety || []).map" not in sheet and "sourced(DATA.safety)" in sheet
    for name in ("team_standards_example", "battery"):
        assert f"sourced(DATA.{name})" in sheet, name
    assert "sourced(tbl.connectors)" in sheet and "sourced(tbl.brownout)" in sheet


# --- 8. golden block agrees with the Python calculators ----------------------------------------
def test_golden_block_agrees_with_python(data):
    assert card.check_golden(data["golden"]) == []
    kinds = {g["calc"] for g in data["golden"]}
    assert {"vdrop", "brownout", "battery_r", "short"} <= kinds


# --- 9. banner and disclaimers ------------------------------------------------------------------
def test_html_has_banner_and_is_self_contained():
    html = HTML.read_text(encoding="utf-8")
    banner = ("Rule rows are from the FRC Game Manual for the season tagged; the manual is re-issued every January "
              "and the control system is changing (SystemCore replacing roboRIO). Verify against the current season's "
              "manual before teaching or wiring. This card is not a substitute for your team's safety training.")
    assert banner in html and "not a substitute" in html
    assert "<script id=\"card-data\" type=\"application/json\">" in html
    assert "prefers-color-scheme" in html and "@media print" in html
    assert not re.search(r"<script[^>]+src=", html) and "<link" not in html     # no CDN, no network
    assert "https://" not in html and "http://" not in html


# --- 10. nothing that identifies a team, school, person or place ----------------------------
DENYLIST = [r"\bTeam\s*#?\s*\d{3,5}\b", r"\bFRC\s+Team\b", r"\bHigh School\b", r"\bHS\b",
            r"[\w.+-]+@[\w-]+\.[\w.]+", r"\bMentor:\s*[A-Z]", r"\b(Mr|Mrs|Ms|Dr)\.\s+[A-Z]",
            r"\b[A-Z][a-z]+,\s*[A-Z]{2}\s+\d{5}\b", r"\b\d{5}(-\d{4})?\b(?=.*\b(Ave|St|Rd|Blvd)\b)"]   # a city-state-ZIP line; a street name followed by a ZIP


def test_no_team_or_person_identifiers():
    files = list(FOLDER.glob("*")) + [Path(__file__)]
    for f in files:
        if f.suffix not in (".py", ".html", ".md", ".json", ".csv", ".txt"):
            continue
        text = f.read_text(encoding="utf-8")
        for pat in DENYLIST:
            assert not re.search(pat, text), (f.name, pat)


# --- 11. warm-up generator ------------------------------------------------------------------
def test_warmup_rule_three_plus_two_and_deterministic(data):
    w = card.warmup(data, 5, 7)
    weeks = [c["week"] for c in w["questions"]]
    assert len(weeks) == 5 and weeks[:3] == [5, 5, 5] and all(x < 5 for x in weeks[3:])
    assert card.warmup(data, 5, 7)["questions"] == w["questions"]            # same seed, same quiz
    assert card.warmup(data, 5, 8)["questions"] != w["questions"]            # a different seed differs
    assert len({c["id"] for c in w["questions"]}) == 5                       # no repeats
    w0 = card.warmup(data, 0, 3)
    assert [c["week"] for c in w0["questions"]] == [0] * 5                   # nothing earlier than week 0
    with pytest.raises(ValueError, match="0-10"):
        card.warmup(data, 11, 1)
    text = report.warmup_text(w)
    assert "ANSWER KEY" in text and "EXIT TICKET" in text and "SL connector current limit" in text


def test_lcg_is_the_published_sequence():
    # s1 = (1 x 1664525 + 1013904223) mod 2^32 = 1015568748 -> 1015568748 / 2^32 = 0.23646
    rand = card.lcg(1)
    assert rand() == pytest.approx(1015568748 / 4294967296)
    assert card.shuffle([1, 2, 3, 4], card.lcg(5)) != [1, 2, 3, 4] or card.shuffle([1, 2, 3, 4], card.lcg(6)) != [1, 2, 3, 4]
    assert sorted(card.shuffle(list(range(10)), card.lcg(9))) == list(range(10))


# --- formatting shared with the page -----------------------------------------------------------
def test_number_formatting():
    assert report.num(1234.5, 1) == "1,234.5" and report.num(1e6) == "1,000,000"
    assert report.num(0.125, 2) == "0.13" and report.num(-3.7) == "-4"      # half rounds up, like the page
    assert report.g(120.0) == "120" and report.g(7.5) == "7.5" and report.g(0.0079) == "0.01"


def test_dump_block_round_trips(data):
    text = card.dump_block(data)
    assert json.loads(text) == data
    html = '<html><script id="card-data" type="application/json">\n{}\n</script></html>'
    assert json.loads(card.extract_block(card.replace_block(html, {"a": [1]}))) == {"a": [1]}
    with pytest.raises(card.CardDataError, match="not valid JSON"):
        card.load_card_data(_write(Path(HTML.parent), html.replace("{}", "{oops")))


def _write(folder, text):
    import tempfile
    p = Path(tempfile.mkdtemp()) / "x.html"
    p.write_text(text, encoding="utf-8")
    return p


# --- the command line ------------------------------------------------------------------------
def test_cli_prints_the_same_sentences(capsys):
    assert main(["vdrop", "--awg", "6", "--amps", "120", "--feet", "10"]) == 0
    assert capsys.readouterr().out.strip() == report.vdrop_sentence(calc.vdrop(6, 120, 10))
    assert main(["brownout", "--battery-mohm", "15", "--path-mohm", "8", "--amps", "300", "--threshold", "6.8"]) == 0
    assert "5.70 V" in capsys.readouterr().out
    assert main(["gauge", "--breaker", "40"]) == 0 and "12 AWG" in capsys.readouterr().out
    assert main(["check"]) == 0 and "card data OK" in capsys.readouterr().out
    assert main(["warmup", "--week", "2", "--seed", "7"]) == 0 and "ANSWER KEY" in capsys.readouterr().out
    assert main(["awg-table"]) == 0 and "0.395" in capsys.readouterr().out


def test_cli_reports_problems_plainly(capsys):
    assert main(["vdrop", "--awg", "99", "--amps", "1", "--feet", "1"]) == 1
    assert capsys.readouterr().err.startswith("Problem: AWG must be a whole number")
    assert main(["gauge"]) == 1 and "Problem:" in capsys.readouterr().err
    assert main(["--html", "/nonexistent/card.html", "check"]) == 1
    assert "Problem:" in capsys.readouterr().err
    assert main(["vdrop", "--awg", "6", "--amps", "inf", "--feet", "10"]) == 1
    assert capsys.readouterr().err.startswith("Problem: amps must be a finite number")
    assert main(["brownout", "--battery-mohm", "nan", "--path-mohm", "8", "--amps", "300"]) == 1
    assert "finite" in capsys.readouterr().err


def test_cli_never_tracebacks_on_a_notepad_edit(tmp_path, capsys, data):
    # whatever is typed into the block, every command prints 'Problem: ...' or a sentence, never a traceback
    def with_edit(edit):
        d = json.loads(json.dumps(data))
        edit(d)
        p = tmp_path / "edited.html"
        p.write_text(card.replace_block(HTML.read_text(encoding="utf-8"), d), encoding="utf-8")
        return str(p)
    # "answer": null on a number card: check flags it, warmup still prints the quiz with {value}
    def null_answer(d):
        d["cards"][6]["answer"] = None
    p = with_edit(null_answer)
    assert main(["--html", p, "check"]) == 1 and "answer must be text" in capsys.readouterr().out
    assert main(["--html", p, "warmup", "--week", "1"]) == 0 and "ANSWER KEY" in capsys.readouterr().out
    # a section that is not a list
    def cards_int(d):
        d["cards"] = 5
    p = with_edit(cards_int)
    assert main(["--html", p, "check"]) == 1 and "must be a list" in capsys.readouterr().out
    assert main(["--html", p, "warmup", "--week", "1"]) == 1 and "Problem:" in capsys.readouterr().err
    # amps limits in quotes: check reports it, gauge still answers (coerced like the page)
    def quoted(d):
        d["rule_table"][1]["amps_min"] = "31"
    p = with_edit(quoted)
    assert main(["--html", p, "check"]) == 1 and "numeric amps_min" in capsys.readouterr().out
    assert main(["--html", p, "gauge", "--breaker", "40"]) == 0 and "12 AWG" in capsys.readouterr().out
    # a rule row that is not an object
    def row_is_text(d):
        d["rule_table"][1] = "b12"
    p = with_edit(row_is_text)
    assert main(["--html", p, "check"]) == 1 and "not an object" in capsys.readouterr().out
    assert main(["--html", p, "gauge", "--breaker", "40"]) == 0 and "not in the table" in capsys.readouterr().out


def test_regen_awg_rewrites_in_place(tmp_path, capsys):
    copy = tmp_path / "card.html"
    shutil.copy(HTML, copy)
    assert main(["--html", str(copy), "regen-awg"]) == 0
    assert "rewritten" in capsys.readouterr().out
    assert card.load_card_data(copy)["awg_table"] == card.load_card_data(HTML)["awg_table"]
    assert main(["--html", str(copy), "check"]) == 0


# --- the JavaScript twin, run in Node when available -----------------------------------------
@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_logic_agrees_with_python(tmp_path, data):
    html = HTML.read_text(encoding="utf-8")
    logic = re.search(r'<script id="card-logic">(.*?)</script>', html, re.S).group(1)
    (tmp_path / "logic.js").write_text(logic, encoding="utf-8")
    (tmp_path / "data.json").write_text(json.dumps(data), encoding="utf-8")
    runner = """
    const FRC = require(process.argv[2]); const data = require(process.argv[3]);
    const out = {golden: data.golden.map(ex => FRC.goldenSentences(ex)), warm: {}, cards: FRC.expandCards(data).map(c => [c.id, c.front, c.back]),
                 gauge: [[40,'breaker'],[10,'breaker'],[10,'fuse'],[41,'breaker'],[120,'breaker'],[120,'fuse']].map(([a,k]) => FRC.gaugeSentence(a, k, FRC.gaugeFor(data.rule_table, a, k))),
                 nosrc: (() => { const d = JSON.parse(JSON.stringify(data)); d.rule_table[1].source = ""; d.cards[6].answer = null; return FRC.expandCards(d).map(c => [c.id, c.back]); })(),
                 fmt: [FRC.num(1234.5,1), FRC.num(0.125,2), FRC.g(7.5), FRC.num(1e6)]};
    for (let w = 0; w <= 10; w++) for (const s of [1, 7, 42]) out.warm[w + ':' + s] = FRC.warmup(data, w, s).questions.map(c => c.id);
    console.log(JSON.stringify(out));
    """
    (tmp_path / "run.js").write_text(runner, encoding="utf-8")
    res = subprocess.run(["node", str(tmp_path / "run.js"), str(tmp_path / "logic.js"), str(tmp_path / "data.json")],
                         capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)

    def py_sentences(ex):
        r = card.run_golden(ex)
        return {"vdrop": lambda: [report.vdrop_sentence(r)], "brownout": lambda: report.brownout_sentences(r),
                "battery_r": lambda: [report.battery_r_sentence(r)], "short": lambda: [report.short_sentence(r)],
                "ohm": lambda: [report.ohm_sentence(r)], "i2t": lambda: [report.i2t_sentence(r)]}[ex["calc"]]()
    assert js["golden"] == [py_sentences(ex) for ex in data["golden"]]
    for key, ids in js["warm"].items():
        w, s = map(int, key.split(":"))
        assert [c["id"] for c in card.warmup(data, w, s)["questions"]] == ids, key
    assert js["cards"] == [[c["id"], c["front"], c["back"]] for c in card.expand_cards(data)]
    assert js["gauge"] == [report.gauge_sentence(a, k, calc.gauge_for(data["rule_table"], a, k))
                           for a, k in [(40, "breaker"), (10, "breaker"), (10, "fuse"), (41, "breaker"), (120, "breaker"), (120, "fuse")]]
    nosrc = json.loads(json.dumps(data))
    nosrc["rule_table"][1]["source"] = ""
    nosrc["cards"][6]["answer"] = None
    assert js["nosrc"] == [[c["id"], c["back"]] for c in card.expand_cards(nosrc)]
    assert len(js["nosrc"]) == len(js["cards"]) - 1
    assert js["fmt"] == [report.num(1234.5, 1), report.num(0.125, 2), report.g(7.5), report.num(1e6)]


# --- first-time-user contract: no browser pop-ups, back link, privacy line, theme blocks --------
def test_page_meets_first_time_user_contract():
    html = HTML.read_text(encoding="utf-8")
    assert not re.search(r"\b(alert|confirm|prompt)\(", html)           # confirmations live on the page
    assert 'href="../index.html"' in html and "Back to the toolbox" in html
    assert "Nothing you type or choose leaves your device." in html
    assert re.search(r":root\s*\{[^}]*--bg:", html)                                           # light tokens
    assert re.search(r'@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{[^}]*color-scheme:\s*dark', html)
    assert re.search(r':root\[data-theme="dark"\]\s*\{[^}]*color-scheme:\s*dark', html)
    assert re.search(r"body\s*\{[^}]*background:\s*var\(--bg\)", html) or re.search(r"html,\s*body\s*\{[^}]*background:\s*var\(--bg\)", html)
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", html)
    assert "env(safe-area-inset-left, 0px)" in html and "env(safe-area-inset-right, 0px)" in html
    assert 'id="hdr-example"' in html and 'id="calc-example"' in html                           # first click shows a result
    assert "If nothing happens, you are using the online copy" in html
    assert 'id="pr-copy-cheat"' in html and 'id="pr-copy-quiz"' in html and "navigator.clipboard.writeText" in html
    # round-3 review: 'week' explained where it sits, ids on the tab and rate buttons, a tab bar that steps aside on short screens
    assert html.count("preseason week 0") >= 2 and "&middot; preseason week " in html
    for cid in ("tab-btn-safety", "tab-btn-rules", "tab-btn-reference", "tab-btn-calc", "tab-btn-cards", "tab-btn-print",
                "fc-rate-1", "fc-rate-2", "fc-rate-3"):
        assert f'id="{cid}"' in html, cid
    assert re.search(r"@media screen and \(max-height:700px\)\{nav\.tabs\{position:static\}", html)


# --- review fixes: wording a first-time user sees, and the import that must not break a later rating --------
def test_review_fixes_in_the_page_text():
    html = HTML.read_text(encoding="utf-8")
    assert "Robotics electrical card: cheat sheet" in html and "FRC Electrical Shop Card: cheat sheet" not in html   # one name on screen and on paper
    assert "Show cards you marked" in html                                       # the Leitner 'Box' filter explained where it sits
    assert "Swipe the table sideways" in html                                     # wide tables on a phone
    assert "<th>Circuit</th><th>Minimum wire</th>" in html                        # the answer column comes second
    assert "function cleanProgress" in html and "matched cards on this page" in html


@pytest.fixture(scope="module")
def frc_page():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            try:
                browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            except Exception as e:
                pytest.skip(f"no headless Chromium: {e}")

        def make(width=375):
            ctx = browser.new_context(viewport={"width": width, "height": 800})
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto((ROOT / "frc_shop_card" / "frc_shop_card.html").as_uri())
            page.wait_for_timeout(200)
            return page, errors

        yield make
        browser.close()


def test_import_keeps_only_well_formed_progress_and_rating_never_throws(frc_page):
    page, errors = frc_page(375)
    page.click('nav.tabs button[data-tab="cards"]')
    page.evaluate("document.querySelector('#tab-cards details').open = true")
    cid = page.evaluate("FRC.expandCards(JSON.parse(document.getElementById('card-data').textContent))[0].id")
    # a number where a record should be, and a key that is not a card: refused with a plain message, progress unchanged
    for bad in (json.dumps({cid: 5}), json.dumps({"card_that_does_not_exist": {"box": 2, "misses": 0, "seen": 1}})):
        page.fill("#fc-io", bad)
        page.click("#fc-import")
        assert page.text_content("#fc-io-msg").startswith("Nothing imported")
        assert "unseen: 69" in page.text_content("#fc-stats")
    # a BOM in front (some editors add one) and one stray entry: the good entry is taken, the count is honest
    page.fill("#fc-io", "﻿" + json.dumps({cid: {"box": 2, "misses": 1, "seen": 3}, "x": 1}))
    page.click("#fc-import")
    assert "Imported: 1 of 2" in page.text_content("#fc-io-msg")
    assert "box 2 hard: 1" in page.text_content("#fc-stats")
    # a malformed record already in storage (from an older copy of the page) must not break rating
    page.evaluate(f"localStorage.setItem('frc_shop_card.progress', JSON.stringify({{'{cid}': 5}}))")
    page.reload()
    page.wait_for_timeout(200)
    page.click('nav.tabs button[data-tab="cards"]')
    page.click("#fc-flip")
    page.click('#fc-rate button[data-box="3"]')
    assert "box 3 got it: 1" in page.text_content("#fc-stats")
    assert errors == []


def test_every_control_has_an_id_and_the_tab_bar_is_short_on_a_phone(frc_page):
    page, errors = frc_page(375)
    assert page.evaluate("[...document.querySelectorAll('input,select,textarea,button')].filter(e => !e.id).length") == 0
    nav = page.evaluate("(n => [n.getBoundingClientRect().height, getComputedStyle(n).position])(document.querySelector('nav.tabs'))")
    assert nav[1] == "sticky" and nav[0] <= 106, nav                     # two rows of pills at 375x800 (was 111)
    page.click("#tab-btn-cards")
    assert "preseason week 0" in page.text_content("#fc-card")
    assert page.evaluate("document.querySelector('label[for], #fc-week').closest('label').textContent").startswith("Weekpreseason week 0")
    page.click("#hdr-example")
    page.wait_for_timeout(300)
    assert page.text_content("#vd-out").startswith("At 120 A through 10 ft of 6 AWG")
    assert errors == []


def test_rule_table_answer_column_is_on_screen_at_phone_width(frc_page):
    page, errors = frc_page(375)
    page.click('nav.tabs button[data-tab="rules"]')
    right = page.evaluate("[...document.querySelectorAll('#rule-table th')].find(t => t.textContent === 'Minimum wire').getBoundingClientRect().right")
    assert right <= 375                                                         # the answer is visible without swiping
    # polish round: on a phone the rule table fits its box (Rating and Source columns hidden, the source as a line under the
    # circuit), so it needs no swipe hint; the wider reference tables still get one
    assert page.evaluate("(w => w.scrollWidth <= w.clientWidth)(document.querySelector('#tab-rules .wrap'))")
    assert page.evaluate("document.querySelector('#tab-rules .swipe').hidden") is True
    assert page.evaluate("getComputedStyle(document.querySelector('#rule-table td:nth-child(3)')).display") == "none"
    assert page.evaluate("getComputedStyle(document.querySelector('#rule-table .phone-src')).display") == "block"
    assert "REBUILT is the 2026 game's name" in page.text_content("#rules-season") and "Team Update 22" in page.text_content("#rules-season")
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    page.click('nav.tabs button[data-tab="reference"]')
    assert page.evaluate("document.querySelector('#tab-reference .swipe').hidden") is False
    assert errors == []


def test_deep_link_scrolls_to_the_panel_and_ohms_law_starts_blank(frc_page):
    page, errors = frc_page(375)
    page.click("#tab-btn-calc")
    assert page.evaluate("document.getElementById('stall-box').hidden") is True      # no cited motor rows shipped: no empty heading
    assert page.text_content("#ol-out") == "" and page.input_value("#ol-v") == ""    # Ohm's law waits for two numbers
    page.fill("#ol-v", "12")
    assert page.text_content("#ol-out") == ""
    page.fill("#ol-r", "4")
    assert page.text_content("#ol-out").startswith("V = 12 V, I = 3 A")
    page.goto(page.url.split("#")[0] + "#cards")
    page.reload()                                                                        # a fresh load with the hash, as a hub link gives
    page.wait_for_timeout(200)
    assert page.evaluate("document.querySelector('#tab-cards').classList.contains('active')")
    assert page.evaluate("window.pageYOffset") > 100                                   # the header is scrolled past
    assert page.evaluate("document.getElementById('fc-card').getBoundingClientRect().top") < 600
    assert page.evaluate("document.getElementById('fc-card').compareDocumentPosition(document.getElementById('fc-reset')) & Node.DOCUMENT_POSITION_FOLLOWING") != 0
    assert errors == []
