"""Golden tests for fantasy_helper/fantasy.html.

The page's <script id="logic"> block is a DOM-free JavaScript port of the fantasy_helper package. These tests
extract that block, run it with node on the shipped sample files (both leagues), and compare every result with
the Python package: lineup slots and players, projected and floor totals, close calls, bench, not-projected
list, matched and could-not-find lists, trade before/after this week and rest of season, waiver gains ranking,
and the scoring-mismatch warning count. They also check that the samples embedded in the page are
byte-identical to the files under fantasy_helper/samples. If node is missing the node tests are skipped.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fantasy_helper.helper import base_report, load_context, trade_report, waiver_report
from fantasy_helper.names import match_name, normalise
from fantasy_helper.parse import parse_name_list
from fantasy_helper.report import floor_differences

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "fantasy_helper" / "fantasy.html"
SAMPLES = ROOT / "fantasy_helper" / "samples"
WEEK8, ROS, LEAGUE1, LEAGUE2 = SAMPLES / "week8", SAMPLES / "ros", SAMPLES / "league1", SAMPLES / "league2"
POINTS = 0.01   # tolerance for points (money-style numbers)

SAMPLE_BLOCKS = {
    "sample-week8-QB": "week8/FantasyPros_Fantasy_Football_Projections_QB.csv",
    "sample-week8-RB": "week8/FantasyPros_Fantasy_Football_Projections_RB.csv",
    "sample-week8-WR": "week8/FantasyPros_Fantasy_Football_Projections_WR.csv",
    "sample-week8-TE": "week8/FantasyPros_Fantasy_Football_Projections_TE.csv",
    "sample-week8-K": "week8/FantasyPros_Fantasy_Football_Projections_K.csv",
    "sample-week8-DST": "week8/FantasyPros_Fantasy_Football_Projections_DST.csv",
    "sample-ros-QB": "ros/FantasyPros_Fantasy_Football_Projections_QB.csv",
    "sample-ros-RB": "ros/FantasyPros_Fantasy_Football_Projections_RB.csv",
    "sample-ros-WR": "ros/FantasyPros_Fantasy_Football_Projections_WR.csv",
    "sample-ros-TE": "ros/FantasyPros_Fantasy_Football_Projections_TE.csv",
    "sample-ros-K": "ros/FantasyPros_Fantasy_Football_Projections_K.csv",
    "sample-ros-DST": "ros/FantasyPros_Fantasy_Football_Projections_DST.csv",
    "sample-league1-league": "league1/league.txt",
    "sample-league1-roster": "league1/roster.csv",
    "sample-league2-league": "league2/league.txt",
    "sample-league2-roster": "league2/roster.csv",
    "sample-free-agents": "free_agents.txt",
}

# The harness appended to the logic block: reads the sample folders with node's fs and prints JSON.
HARNESS = r"""
var fs = require("fs"), path = require("path");
var samples = process.argv[2];
function readFolder(folder) {
  return fs.readdirSync(path.join(samples, folder)).map(function (n) {
    return { name: n, text: fs.readFileSync(path.join(samples, folder, n), "utf8") };
  });
}
var out = {};
["league1", "league2"].forEach(function (lg) {
  var fileLeague = parseLeagueText(fs.readFileSync(path.join(samples, lg, "league.txt"), "utf8"), DEFAULT_SCORING, "league.txt");
  // the page goes league.txt -> fields -> league; prove that round trip changes nothing
  var league = leagueFromSettings(settingsFromLeague(fileLeague));
  var rosterText = rosterCsvToLines(fs.readFileSync(path.join(samples, lg, "roster.csv"), "utf8"));
  var roster = parseRosterLines(rosterText).roster;
  var week = loadProjections(readFolder("week8"), positionsNeeded(league), "this week's files");
  var ros = loadProjections(readFolder("ros"), positionsNeeded(league), "the rest-of-season files");
  var ctx = loadContext(league, roster, week, "");
  var rosCtx = loadContext(league, roster, ros, "rest of season");
  var r = { fileSlots: fileLeague.slots, slots: league.slots, scoring: league.scoring, rosterText: rosterText, roster: roster,
            season: [week.season, ros.season], warningCount: ctx.warnings.length,
            players: ctx.players.map(function (p) { return [p.name, p.pos, p.proj, p.floor, p.ceil]; }),
            matches: ctx.matches.map(function (m) { return [m.query, m.projection.name, m.how]; }) };
  r.lineup = reportJson(baseReport(ctx, "lineup", 1.5));
  if (lg === "league1") {
    r.trade = reportJson(tradeReport(ctx, ["Runner Charlie"], ["Catcher Charlie"], 1.5, rosCtx));
    r.tradeNoRos = reportJson(tradeReport(ctx, ["Catcher Kilo"], ["Catcher Lima"], 1.5, null));
    var cands = parseNameList(fs.readFileSync(path.join(samples, "free_agents.txt"), "utf8"));
    r.waiver = reportJson(waiverReport(ctx, "Catcher Baker", null, cands, 1.5));
    r.waiverDrop = reportJson(waiverReport(ctx, "Catcher Baker", "Runner Delta", [], 1.5));
    // this week's files chosen as the rest-of-season files by mistake: the warning the page must show
    r.tradeWeekAsRos = reportJson(tradeReport(ctx, ["Runner Charlie"], ["Catcher Charlie"], 1.5, loadContext(league, roster, week, "rest of season")));
    // lines pasted straight from the Yahoo roster page (name, team, position, sometimes an injury tag)
    r.tidy = parseRosterLines("Passer Baker Dal - QB\nRunner Able SF - RB Q\nCatcher Able Cin - WR\nBlocker Baker Bal - TE IR\n" +
                              "Kicker Baker Dal - K\nSample City Chi - DEF\nCatcher Charlie, WR\nAJ Sample\n");
    r.tidyCtx = loadContext(league, r.tidy.roster, week, "");
    r.tidyMatches = r.tidyCtx.matches.map(function (m) { return [m.query, m.projection.name, m.how]; });
  } else {
    r.trade = reportJson(tradeReport(ctx, ["Runner Golf", "Catcher Juliet"], ["Runner Able"], 1.5, rosCtx));
    r.waiver = reportJson(waiverReport(ctx, null, null, ["Catcher Baker", "Kicker Baker", "Blocker Baker", "Sample City D/ST"], 1.5));
  }
  // every roster name against every projected player, both argument orders, as the matcher sees them
  r.ratios = roster.map(function (row) {
    var q = normalise(row[0]);
    return allProjections(week).map(function (p) { return [q, p.name, seqRatio(normalise(p.name), q), seqRatio(q, normalise(p.name))]; });
  });
  out[lg] = r;
});
process.stdout.write(JSON.stringify(out));
"""


def logic_block() -> str:
    text = PAGE.read_text(encoding="utf-8")
    m = re.search(r'<script id="logic">(.*?)</script>', text, re.S)
    assert m, "fantasy.html has no <script id=\"logic\"> block"
    block = m.group(1)
    assert "document." not in block and "window." not in block, "the logic block must stay DOM-free"
    return block


# ------------------------------------------------------------------ embedded samples

def test_page_exists_and_is_a_complete_document():
    text = PAGE.read_text(encoding="utf-8")
    assert text.lstrip().lower().startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in text and 'name="viewport"' in text
    assert "<title>Fantasy Lineup Helper</title>" in text
    assert "Try it with example data" in text
    assert "http://" not in text and "https://" not in text.replace("https://", "", 0), "no external resources"
    assert "<link" not in text and 'src="http' not in text


def test_embedded_samples_are_byte_identical_to_the_files():
    html = PAGE.read_bytes()
    for block_id, rel in SAMPLE_BLOCKS.items():
        tag = b'<script type="text/plain" id="' + block_id.encode() + b'">'
        start = html.find(tag)
        assert start >= 0, f"missing sample block {block_id}"
        start += len(tag)
        end = html.find(b"</script>", start)
        assert html[start:end] == (SAMPLES / rel).read_bytes(), f"{block_id} differs from {rel}"


# ------------------------------------------------------------------ node golden tests

@pytest.fixture(scope="module")
def js(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the JavaScript golden tests need it")
    script = tmp_path_factory.mktemp("fantasy_page") / "logic_run.js"
    script.write_text(logic_block() + "\n" + HARNESS, encoding="utf-8")
    proc = subprocess.run([node, str(script), str(SAMPLES)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def lineup_py(lu):
    return {"slots": [{"slot": e.slot, "player": e.player.name if e.player else None,
                       "proj": e.player.proj if e.player else None, "floor": e.player.floor if e.player else None}
                      for e in lu.entries],
            "projTotal": lu.proj_total, "floorTotal": lu.floor_total, "ceilTotal": lu.ceil_total}


def same_lineup(js_lu, py_lu):
    assert [(s["slot"], s["player"]) for s in js_lu["slots"]] == [(s["slot"], s["player"]) for s in py_lu["slots"]]
    for a, b in zip(js_lu["slots"], py_lu["slots"]):
        if a["player"] is not None:
            assert a["proj"] == pytest.approx(b["proj"], abs=POINTS) and a["floor"] == pytest.approx(b["floor"], abs=POINTS)
    for key in ("projTotal", "floorTotal", "ceilTotal"):
        assert js_lu[key] == pytest.approx(py_lu[key], abs=POINTS), key


def same_delta(js_d, d):
    assert js_d["before"] == pytest.approx(d.before.proj_total, abs=POINTS)
    assert js_d["after"] == pytest.approx(d.after.proj_total, abs=POINTS)
    assert js_d["change"] == pytest.approx(d.change, abs=POINTS)
    assert js_d["startersOut"] == [f"{p.name} ({d.before.slot_of(p.name)})" for p in d.starters_out()]
    assert js_d["startersIn"] == [f"{p.name} ({d.after.slot_of(p.name)})" for p in d.starters_in()]
    assert set(js_d["positionChanges"]) == set(d.position_changes())
    for k, v in d.position_changes().items():
        assert js_d["positionChanges"][k] == pytest.approx(v, abs=POINTS)


def same_sentence(js_text, py_text):
    """Verdict sentences compare exactly on Python 3.12+ (whose sum() the page reproduces); older Pythons
    add floats differently, so there the numbers are compared with tolerance instead of as text."""
    if sys.version_info >= (3, 12):
        assert js_text == py_text
    else:
        nums = re.compile(r"-?[\d,]+\.\d")
        assert nums.sub("#", js_text) == nums.sub("#", py_text)
        a = [float(x.replace(",", "")) for x in nums.findall(js_text)]
        b = [float(x.replace(",", "")) for x in nums.findall(py_text)]
        assert a == pytest.approx(b, abs=0.1)


@pytest.mark.parametrize("league, folder", [("league1", LEAGUE1), ("league2", LEAGUE2)])
def test_league_settings_and_roster_round_trip(js, league, folder):
    ctx = load_context(folder, WEEK8)
    r = js[league]
    assert [(s["label"], set(s["allowed"]), s["count"]) for s in r["slots"]] == \
           [(s.label, set(s.allowed), s.count) for s in ctx.league.slots]
    assert r["fileSlots"] == r["slots"]
    assert r["scoring"] == pytest.approx(ctx.league.scoring)
    rows = [list(x) for x in __import__("fantasy_helper.parse", fromlist=["parse_roster"]).parse_roster(folder / "roster.csv")]
    assert r["roster"] == rows
    assert r["season"] == [False, True]


@pytest.mark.parametrize("league, folder", [("league1", LEAGUE1), ("league2", LEAGUE2)])
def test_lineup_report_matches_python(js, league, folder):
    ctx = load_context(folder, WEEK8)
    rep = base_report(ctx, "lineup", 1.5)
    r = js[league]["lineup"]
    same_lineup(r["lineup"], lineup_py(rep.lineup))
    same_lineup(r["floorLineup"], lineup_py(rep.floor_lineup))
    assert r["floorDifferences"] == floor_differences(rep.lineup, rep.floor_lineup)
    assert [(c["slot"], c["starter"], c["other"]) for c in r["close"]] == [(c.slot, c.starter.name, c.other.name) for c in rep.close]
    assert [c["gap"] for c in r["close"]] == pytest.approx([c.gap for c in rep.close], abs=POINTS)
    assert [b["name"] for b in r["bench"]] == [p.name for p in rep.bench]
    assert [b["proj"] for b in r["bench"]] == pytest.approx([p.proj for p in rep.bench], abs=POINTS)
    assert [b["fpts"] for b in r["bench"]] == [p.fpts_csv for p in rep.bench]
    assert r["unmatched"] == rep.unmatched
    assert r["matchLines"] == rep.match_lines
    assert r["problems"] == rep.problems
    assert r["notes"] == rep.notes
    assert r["kindNote"] == rep.kind_note
    # scored players: same names, positions and points
    py_players = [[p.name, p.pos, p.proj, p.floor, p.ceil] for p in ctx.players]
    assert [p[:2] for p in js[league]["players"]] == [p[:2] for p in py_players]
    for a, b in zip(js[league]["players"], py_players):
        assert a[2:] == pytest.approx(b[2:], abs=POINTS)


@pytest.mark.parametrize("league, folder", [("league1", LEAGUE1), ("league2", LEAGUE2)])
def test_scoring_mismatch_warning_count_matches_python(js, league, folder):
    ctx = load_context(folder, WEEK8)
    assert js[league]["warningCount"] == len(ctx.warnings)
    assert js[league]["lineup"]["warnings"] == ctx.warnings
    if league == "league1":
        assert len(ctx.warnings) == 1 and "(K)" in ctx.warnings[0]      # kicker 3.3 vs flat 3: expected, explained


def test_name_matcher_agrees_on_every_sample_name(js):
    """The page's port of difflib must give the same ratio as Python for every roster name against every
    projected player (both argument orders), and the same match decision, including the misspelled names and
    the D/ST alias in the samples."""
    import difflib
    for league, folder in (("league1", LEAGUE1), ("league2", LEAGUE2)):
        ctx = load_context(folder, WEEK8)
        pool = ctx.proj.all()
        roster = __import__("fantasy_helper.parse", fromlist=["parse_roster"]).parse_roster(folder / "roster.csv")
        for row, js_rows in zip(roster, js[league]["ratios"]):
            q = normalise(row[0])
            assert len(js_rows) == len(pool)
            for p, (jq, jname, r1, r2) in zip(pool, js_rows):
                assert jq == q and jname == p.name
                assert r1 == difflib.SequenceMatcher(None, normalise(p.name), q).ratio()
                assert r2 == difflib.SequenceMatcher(None, q, normalise(p.name)).ratio()
        expected = []
        for name, pos in roster:
            m = match_name(name, pos, pool)
            if m.projection is not None and normalise(m.projection.name) not in {normalise(e[1]) for e in expected}:
                expected.append([name, m.projection.name, m.how])
        assert js[league]["matches"] == expected
    l1 = js["league1"]["matches"]
    assert ["Catcher Abel", "Catcher Able", "close"] in l1
    assert ["AJ Sample", "A.J. Sample Jr.", "spelling"] in l1
    assert ["Sample City D/ST", "Sample City Foxes", "team"] in l1
    assert "'Runner Zulu'" in js["league1"]["lineup"]["unmatched"][0]


def test_trade_matches_python_with_and_without_rest_of_season(js):
    ctx = load_context(LEAGUE1, WEEK8)
    ros_ctx = load_context(LEAGUE1, ROS, "rest of season")
    rep = trade_report(ctx, ["Runner Charlie"], ["Catcher Charlie"], 1.5, ros_ctx)
    t = js["league1"]["trade"]["trade"]
    same_delta(t["week"], rep.trade.week)
    same_delta(t["ros"], rep.trade.ros)
    assert t["week"]["change"] == pytest.approx(14.6 - 13.4, abs=POINTS)
    same_sentence(t["verdict"], rep.trade.verdict)
    assert t["notes"] == rep.trade.notes
    assert js["league1"]["trade"]["warnings"] == rep.warnings and js["league1"]["trade"]["notes"] == rep.notes
    rep2 = trade_report(ctx, ["Catcher Kilo"], ["Catcher Lima"], 1.5)
    t2 = js["league1"]["tradeNoRos"]["trade"]
    assert t2["ros"] is None and rep2.trade.ros is None
    same_delta(t2["week"], rep2.trade.week)
    same_sentence(t2["verdict"], rep2.trade.verdict)
    assert "no starter changes this week" in t2["verdict"]
    # league 2: a two-for-one
    ctx2 = load_context(LEAGUE2, WEEK8)
    rep3 = trade_report(ctx2, ["Runner Golf", "Catcher Juliet"], ["Runner Able"], 1.5, load_context(LEAGUE2, ROS, "rest of season"))
    t3 = js["league2"]["trade"]["trade"]
    same_delta(t3["week"], rep3.trade.week)
    same_delta(t3["ros"], rep3.trade.ros)
    same_sentence(t3["verdict"], rep3.trade.verdict)


def test_weekly_files_as_rest_of_season_give_the_same_warning_as_python(js):
    """Review finding: this week's six files chosen in the rest-of-season chooser. The logic block must produce
    the same warning the Python tool prints under PLEASE CHECK (the page then shows it in the trade tab)."""
    ctx = load_context(LEAGUE1, WEEK8)
    rep = trade_report(ctx, ["Runner Charlie"], ["Catcher Charlie"], 1.5, load_context(LEAGUE1, WEEK8, "rest of season"))
    r = js["league1"]["tradeWeekAsRos"]
    assert r["warnings"] == rep.warnings and r["notes"] == rep.notes
    assert any(w.startswith("The --ros folder look like WEEKLY numbers") for w in r["warnings"])
    same_sentence(r["trade"]["verdict"], rep.trade.verdict)


def test_lines_pasted_from_the_yahoo_roster_page_are_read_as_name_and_position(js):
    """Review finding: 'Passer Baker Dal - QB' (team and position after the name, sometimes an injury tag) must
    not come back COULD NOT FIND. The tail is dropped and reported; plain lines are untouched."""
    r = js["league1"]
    assert r["tidy"]["errors"] == []
    assert r["tidy"]["roster"] == [["Passer Baker", "QB"], ["Runner Able", "RB"], ["Catcher Able", "WR"], ["Blocker Baker", "TE"],
                                   ["Kicker Baker", "K"], ["Sample City", "DST"], ["Catcher Charlie", "WR"], ["AJ Sample", ""]]
    assert [(t["text"], t["name"], t["pos"]) for t in r["tidy"]["tidied"]] == [
        ("Passer Baker Dal - QB", "Passer Baker", "QB"), ("Runner Able SF - RB Q", "Runner Able", "RB"),
        ("Catcher Able Cin - WR", "Catcher Able", "WR"), ("Blocker Baker Bal - TE IR", "Blocker Baker", "TE"),
        ("Kicker Baker Dal - K", "Kicker Baker", "K"), ("Sample City Chi - DEF", "Sample City", "DEF")]
    assert r["tidyCtx"]["unmatched"] == []
    assert ["Sample City", "Sample City Foxes", "team"] in r["tidyMatches"]
    assert ["AJ Sample", "A.J. Sample Jr.", "spelling"] in r["tidyMatches"]
    assert len(r["tidyCtx"]["players"]) == 8


def test_waiver_ranking_matches_python(js):
    ctx = load_context(LEAGUE1, WEEK8)
    rep = waiver_report(ctx, "Catcher Baker", None, parse_name_list(SAMPLES / "free_agents.txt"), 1.5)
    w = js["league1"]["waiver"]["waiver"]
    assert [(r["name"], r["drop"], r["dropWasDefault"], r["startersOut"]) for r in w["ranked"]] == \
           [(r.add.name, r.drop.name, r.drop_was_default, [p.name for p in r.delta.starters_out()]) for r in rep.waiver.ranked]
    assert [r["gain"] for r in w["ranked"]] == pytest.approx([r.gain for r in rep.waiver.ranked], abs=POINTS)
    assert [(r["name"], round(r["gain"], 2)) for r in w["ranked"]] == \
           [("Blocker Able", 2.8), ("Catcher Baker", 2.6), ("Kicker Able", 0.96), ("Runner Echo", 0.0)]
    s, py_s = w["single"], rep.waiver.single
    assert s["name"] == py_s.add.name and s["drop"] == py_s.drop.name and s["dropWasDefault"] == py_s.drop_was_default
    assert s["gain"] == pytest.approx(py_s.gain, abs=POINTS)
    assert s["startersIn"] == [f"{p.name} starts at {py_s.delta.after.slot_of(p.name)}" for p in py_s.delta.starters_in()]
    # a named drop
    rep2 = waiver_report(ctx, "Catcher Baker", "Runner Delta", [], 1.5)
    s2 = js["league1"]["waiverDrop"]["waiver"]["single"]
    assert s2["drop"] == "Runner Delta" and not s2["dropWasDefault"]
    assert s2["gain"] == pytest.approx(rep2.waiver.single.gain, abs=POINTS)
    # league 2: a candidate who is already on the roster is listed as a problem, not ranked
    ctx2 = load_context(LEAGUE2, WEEK8)
    rep3 = waiver_report(ctx2, None, None, ["Catcher Baker", "Kicker Baker", "Blocker Baker", "Sample City D/ST"], 1.5)
    w3 = js["league2"]["waiver"]
    assert [r["name"] for r in w3["waiver"]["ranked"]] == [r.add.name for r in rep3.waiver.ranked]
    assert [r["gain"] for r in w3["waiver"]["ranked"]] == pytest.approx([r.gain for r in rep3.waiver.ranked], abs=POINTS)
    assert w3["problems"] == rep3.problems


# ------------------------------------------------------------------ leaving example mode (headless browser)

@pytest.fixture(scope="module")
def browser_page():
    """A headless Chromium page, or a skip when playwright / the browser is not available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright is not installed; the browser test needs it")
    exe = Path("/opt/pw-browsers/chromium")
    if not exe.exists():
        pytest.skip("headless chromium is not at /opt/pw-browsers/chromium")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(exe))
        ctx = browser.new_context(viewport={"width": 375, "height": 800})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(PAGE.as_uri())
        page.wait_for_timeout(200)
        yield page, errors
        browser.close()


def test_leaving_example_mode_never_saves_example_data_over_the_users_league(browser_page):
    """Review finding (high): after an example, choosing your own files or pressing a league button must
    bring back the user's own roster, league name, scoring and files, clear the example's trade and pickup
    names, and never save the example league over the user's League 1."""
    page, errors = browser_page
    week8 = sorted(str(p) for p in WEEK8.glob("*.csv"))
    page.fill("#league-name", "My real league")
    page.fill("#roster", "Passer Baker, QB\nRunner Able, RB")
    # path A: second example (full PPR, 3 WR, 6-point pass TD), then the user's own files
    page.click("#btn-example2")
    page.wait_for_timeout(400)
    assert page.input_value("#sc-rec") == "1" and page.input_value("#slot-WR") == "3"
    assert page.is_visible("#example-banner") and page.get_attribute("#tab-lineup", "aria-selected") == "true"
    page.set_input_files("#files-week", week8)
    page.wait_for_timeout(600)
    assert page.input_value("#league-name") == "My real league"
    assert page.input_value("#roster") == "Passer Baker, QB\nRunner Able, RB"
    assert page.input_value("#sc-rec") == "0.5" and page.input_value("#slot-WR") == "2" and page.input_value("#sc-pass_td") == "4"
    assert page.input_value("#get-names") == "" and page.input_value("#cand-names") == "" and page.input_value("#add-name") == ""
    assert page.is_hidden("#example-banner") and page.is_hidden("#results")
    assert page.inner_text("#status-week").count(" players)") == 6
    assert "not chosen yet" in page.inner_text("#status-ros")          # the example's rest-of-season files are gone too
    page.click("#btn-run")
    page.wait_for_timeout(400)
    body = page.evaluate("document.body.innerText")
    assert "Start these 2 players" in body and "COULD NOT FIND" not in body
    page.fill("#roster", "Passer Baker, QB\nRunner Able, RB\nCatcher Able, WR")   # a keystroke after leaving: saves the user's data
    page.wait_for_timeout(100)
    page.reload()
    page.wait_for_timeout(300)
    assert page.input_value("#league-name") == "My real league" and page.inner_text("#btn-league-0") == "My real league"
    assert page.input_value("#roster") == "Passer Baker, QB\nRunner Able, RB\nCatcher Able, WR"
    assert page.input_value("#sc-rec") == "0.5" and page.input_value("#slot-WR") == "2"
    # path B: first example, then the League 1 button
    page.click("#btn-example")
    page.wait_for_timeout(400)
    assert "126.1 points, with a floor of 94.5" in page.evaluate("document.body.innerText")
    page.click("#btn-league-0")
    page.wait_for_timeout(300)
    assert page.inner_text("#status-week").count("not chosen yet") == 6
    assert page.is_hidden("#results") and page.is_hidden("#example-banner")
    assert page.input_value("#roster").startswith("Passer Baker, QB") and page.input_value("#get-names") == ""
    assert page.get_attribute("#btn-league-0", "aria-pressed") == "true"
    # a step-3 error after a good run takes the old answer off the screen and the trade tab points at step 3
    page.click("#btn-example")
    page.wait_for_timeout(400)
    page.fill("#sc-rec", "")
    page.dispatch_event("#sc-rec", "change")
    page.wait_for_timeout(700)      # a field change recomputes a moment later, so a click in progress is not lost
    assert page.is_visible("#err-settings") and page.is_hidden("#results")
    assert "problem in step 3" in page.evaluate("(function(){document.getElementById('btn-trade').click(); return document.getElementById('err-trade').textContent})()")
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0
    assert errors == []


def test_review_round_2_findings_in_the_browser(browser_page):
    """Round-2 review findings, checked with real pointer clicks at phone width:
    1. this week's files in the rest-of-season chooser: the trade tab shows the warning;
    2. a blanked step-3 field, then ONE real click on Reset: the click is not swallowed;
    3. changing a step-3 field says under the button that the lineup was updated;
    4. season-total files chosen as this week's files: a warning sits under the verdict;
    5. the wording no longer says 'I get' / 'MY number'."""
    page, errors = browser_page
    week8 = sorted(str(p) for p in WEEK8.glob("*.csv"))
    ros = sorted(str(p) for p in ROS.glob("*.csv"))
    roster = (LEAGUE1 / "roster.csv").read_text(encoding="utf-8")
    page.click("#btn-league-0")
    page.wait_for_timeout(200)
    page.fill("#roster", roster)
    page.set_input_files("#files-week", week8)
    page.set_input_files("#files-ros", week8)
    page.wait_for_timeout(600)
    page.click("#btn-run")
    page.wait_for_timeout(400)
    page.click("#tab-trade")
    page.check("#give-list input[value='Runner Charlie']")
    page.fill("#get-names", "Catcher Charlie")
    page.click("#btn-trade")
    page.wait_for_timeout(300)
    trade = page.inner_text("#panel-trade")
    # the change beside two rounded totals is the difference of those totals (126.1 -> 127.2 reads +1.1, not the exact +1.2)
    assert "from 126.1 to 127.2 this week (+1.1)" in trade and "rest of season (+1.1)" in trade
    assert "look like one week's numbers, not season totals" in trade
    assert "I get" not in trade and "MY number" not in trade
    # the real rest-of-season files: the trade re-runs by itself and shows the rest-of-season notes
    page.set_input_files("#files-ros", ros)
    page.wait_for_timeout(600)
    trade = page.inner_text("#panel-trade")
    assert "from 1,246.3 to 1,222.7 rest of season (-23.6)" in trade and "look like one week's numbers" not in trade
    assert "Rest of season: Kicker Able" in trade and "Rest of season: Season-total file: the defense points-allowed tier was skipped" in trade
    # 2. blank a starting-spot field, then one real click on Reset
    page.click("#tab-lineup")
    page.click("#slot-QB")
    page.fill("#slot-QB", "")
    page.click("#btn-preset")       # a single pointer click: mousedown, mouseup at the same spot
    page.wait_for_timeout(600)
    assert page.input_value("#slot-QB") == "1"
    assert page.is_hidden("#err-settings") and page.is_visible("#results")
    # 3. a step-3 change says so under the button
    page.fill("#sc-rec", "1")
    page.dispatch_event("#sc-rec", "change")
    page.wait_for_timeout(700)
    note = page.inner_text("#updated-note")
    assert note.startswith("Updated:") and "139.8" in note
    lineup = page.inner_text("#panel-lineup")
    assert "139.8 points, with a floor of 105.2" in lineup
    assert "I get" not in lineup and "MY number" not in lineup and "this page gets" in lineup
    assert "instead of" in lineup and "FLEX: Runner Delta" not in lineup     # set-wise play-it-safe sentence
    page.fill("#sc-rec", "0.5")
    page.dispatch_event("#sc-rec", "change")
    page.wait_for_timeout(700)
    # 4. season totals chosen as this week's files
    page.set_input_files("#files-week", ros)
    page.wait_for_timeout(600)
    page.click("#btn-run")
    page.wait_for_timeout(400)
    assert page.is_visible("#season-warning") and "season totals, not one week" in page.inner_text("#season-warning")
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0
    assert errors == []


def test_polish_round_3_findings_in_the_browser(browser_page):
    """Round-3 polish notes, at phone width:
    1. the three result tabs are on the page from the start, greyed, with 'press Show my best lineup first';
    2. pressing the button with nothing loaded points at the example button;
    3. the 'please check' note names the other players that differ, and the not-found hint allows 'Name, POS';
    4. editing the team box after a run captions the result as out of date until the next run."""
    page, errors = browser_page
    page.reload()
    page.wait_for_timeout(300)
    page.click("#btn-league-1")
    page.wait_for_timeout(200)
    page.fill("#roster", "")
    page.click("#btn-clear-files")
    page.wait_for_timeout(200)
    assert page.is_visible("#tab-trade") and page.is_disabled("#tab-trade") and page.is_disabled("#tab-pickup")
    assert "Show my best lineup' first" in page.inner_text("#tabs-note") and page.is_hidden("#results")
    page.click("#btn-run")
    page.wait_for_timeout(300)
    assert "Try it with example data" in page.inner_text("#err-roster")
    page.click("#btn-example")
    page.wait_for_timeout(500)
    assert page.is_enabled("#tab-trade") and page.is_hidden("#tabs-note") and page.is_hidden("#stale-note")
    lineup = page.inner_text("#panel-lineup")
    assert "so do the other 4 kickers in the file: Kicker Baker, Kicker Charlie, Kicker Delta, Kicker Echo" in lineup
    assert "4 other players differ too" not in lineup
    page.click("#tab-trade")
    assert "this week (+1.1)" in page.inner_text("#trade-verdict")
    page.click("#tab-lineup")
    page.evaluate("(function(){var r=document.getElementById('roster'); r.focus(); r.setSelectionRange(r.value.length, r.value.length)})()")
    page.keyboard.type("\nZed Nobody, RB")             # keystrokes at the end of the box: no change event yet
    page.wait_for_timeout(100)
    assert page.is_visible("#stale-note") and "Out of date" in page.inner_text("#stale-note")
    page.click("#btn-run")
    page.wait_for_timeout(400)
    assert page.is_hidden("#stale-note")
    lineup = page.inner_text("#panel-lineup")
    assert "'Zed Nobody': not in any projection file (check the spelling in step 2 (a comma and the position after the name is fine)" in lineup
    assert "type only the name" not in lineup
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0
    assert errors == []
