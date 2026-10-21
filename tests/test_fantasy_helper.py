from pathlib import Path

import pytest

from fantasy_helper.helper import (base_report, load_context, mismatch_warnings, trade_report, trade_verdict,
                                   waiver_report)
from fantasy_helper.lineup import (Delta, Player, align, apply_trade, apply_waiver, bench, best_lineup, close_calls,
                                   make_player, rank_candidates)
from fantasy_helper.names import match_name, normalise
from fantasy_helper.parse import (EXPECTED_HEADERS, ExportFormatError, Projection, ProjectionSet, _number,
                                  load_projections, parse_league_text, parse_projection_file, parse_roster)
from fantasy_helper.report import html_report, text_report
from fantasy_helper.scoring import DEFAULT_SCORING, FANTASYPROS_HALF_PPR, points_allowed_tier, score

SAMPLES = Path(__file__).resolve().parent.parent / "fantasy_helper" / "samples"
WEEK8, ROS, LEAGUE1, LEAGUE2 = SAMPLES / "week8", SAMPLES / "ros", SAMPLES / "league1", SAMPLES / "league2"

LEAGUE1_RULES = parse_league_text((LEAGUE1 / "league.txt").read_text(encoding="utf-8"), DEFAULT_SCORING).scoring
LEAGUE2_RULES = parse_league_text((LEAGUE2 / "league.txt").read_text(encoding="utf-8"), DEFAULT_SCORING).scoring
SLOTS = parse_league_text("", DEFAULT_SCORING).slots   # Yahoo default: QB, RB x2, WR x2, TE, FLEX, K, DEF


# ------------------------------------------------------------------ (1) parser on the shipped samples

def test_parser_reads_each_sample_position_file():
    ps = load_projections(WEEK8)
    assert {pos: len(rows) for pos, rows in ps.by_pos.items()} == {
        "QB": 10, "RB": 11, "WR": 12, "TE": 10, "K": 10, "DST": 10}
    qb = {p.name: p for p in ps.by_pos["QB"]}
    able = qb["Passer Able"]
    # row: 36.0,24.0,275.0,2.0,0.7,5.0,25.0,0.3,0.2 -> passing first, rushing second
    assert able.stats == {"pass_att": 36.0, "pass_cmp": 24.0, "pass_yds": 275.0, "pass_td": 2.0, "pass_int": 0.7,
                          "rush_att": 5.0, "rush_yds": 25.0, "rush_td": 0.3, "fumble_lost": 0.2}
    assert able.fpts == 22.2
    assert able.high is not None and able.low is not None          # the one QB with a 'high' row
    assert able.low["pass_yds"] == 225.5 and able.high["pass_yds"] == 324.5
    assert qb["Passer Baker"].high is None and qb["Passer Baker"].low is not None
    assert all(p.low is not None for p in ps.all())                # every player has a low row
    assert all(p.team == "" for p in ps.by_pos["DST"])             # DST Team cell is empty
    assert ps.by_pos["DST"][0].name == "Sample City Foxes"
    assert ps.by_pos["WR"][0].stats["rec"] == 7.0                 # WR: receiving first
    assert ps.by_pos["RB"][0].stats["rush_att"] == 20.0           # RB: rushing first
    assert not ps.season and "WEEKLY" in ps.kind_note


def test_high_and_low_rows_in_either_order_and_junk_row(tmp_path):
    f = tmp_path / "proj_te.csv"
    f.write_text('"Player","Team","REC","YDS","TDS","FL","FPTS"\n'
                 '" ","",""\n'                                   # junk second row, fewer fields than the header
                 '"Blocker One","KC","6.0","70.0","0.6","0.0","13.6"\n'
                 '"","low","4.0","50.0","0.3","0.0","8.8"\n'      # low BEFORE high this time
                 '"","high","7.0","90.0","0.9","0.0","17.9"\n'
                 '"Blocker Two","BAL","5.0","55.0","0.5","0.1","10.8"\n', encoding="utf-8")
    rows = parse_projection_file(f, "TE")
    assert [r.name for r in rows] == ["Blocker One", "Blocker Two"]
    assert rows[0].low["rec_yds"] == 50.0 and rows[0].high["rec_yds"] == 90.0 and rows[0].high_fpts == 17.9
    assert rows[1].low is None and rows[1].high is None


# ------------------------------------------------------------------ (2)(3) scoring by hand

def test_qb_points_under_league1_and_league2():
    stats = {"pass_yds": 250, "pass_td": 2, "pass_int": 1, "rush_yds": 20}
    # league1: 250/25 = 10, 2 x 4 = 8, 1 x -1, 20/10 = 2  -> 19.0
    assert score("QB", stats, LEAGUE1_RULES) == pytest.approx(19.0)
    # league2: 6-point passing TD and -2 per INT: 10 + 12 - 2 + 2 -> 22.0
    assert score("QB", stats, LEAGUE2_RULES) == pytest.approx(22.0)


def test_sample_qb_row_matches_hand_worked_half_ppr():
    ps = load_projections(WEEK8)
    able = next(p for p in ps.by_pos["QB"] if p.name == "Passer Able")
    # 275 x 0.04 = 11.0; 2.0 x 4 = 8.0; 0.7 x -1 = -0.7; 25 x 0.1 = 2.5; 0.3 x 6 = 1.8; 0.2 x -2 = -0.4 -> 22.2
    assert score("QB", able.stats, LEAGUE1_RULES) == pytest.approx(22.2)
    assert able.fpts == pytest.approx(22.2)


def test_rb_full_ppr_vs_half_ppr():
    stats = {"rush_att": 20, "rush_yds": 95, "rush_td": 0.8, "rec": 3, "rec_yds": 22, "rec_td": 0.1, "fumble_lost": 0.1}
    # half: 9.5 + 4.8 + 1.5 + 2.2 + 0.6 - 0.2 = 18.4 ; full PPR adds 0.5 x 3 = 1.5 -> 19.9
    assert score("RB", stats, LEAGUE1_RULES) == pytest.approx(18.4)
    assert score("RB", stats, LEAGUE2_RULES) == pytest.approx(19.9)


def test_kicker_and_dst_scoring():
    # K: 2.2 FG x 3.3 = 7.26, 2.8 XPT x 1 = 2.8 -> 10.06 (league1, no miss penalty)
    assert score("K", {"fg": 2.2, "fga": 2.5, "xpt": 2.8}, LEAGUE1_RULES) == pytest.approx(10.06)
    # league2: 3 per FG, -1 per miss (2.5 - 2.2 = 0.3 misses): 6.6 + 2.8 - 0.3 = 9.1
    assert score("K", {"fg": 2.2, "fga": 2.5, "xpt": 2.8}, LEAGUE2_RULES) == pytest.approx(9.1)
    # FantasyPros' own K number: flat 3 -> 6.6 + 2.8 = 9.4
    assert score("K", {"fg": 2.2, "fga": 2.5, "xpt": 2.8}, FANTASYPROS_HALF_PPR) == pytest.approx(9.4)
    dst = {"dst_sack": 3.2, "dst_int": 1.0, "dst_fr": 0.7, "dst_ff": 1.1, "dst_td": 0.2, "dst_safety": 0.1,
           "dst_pa": 17.0, "dst_yds_agn": 320.0}
    # 3.2 + 2.0 + 1.4 + 1.2 + 0.2 + points-allowed 17 -> tier 14-20 = 1 -> 9.0 ; FF and yards not scored
    assert score("DST", dst, LEAGUE1_RULES) == pytest.approx(9.0)
    assert score("DST", dst, LEAGUE1_RULES, pa_tier=False) == pytest.approx(8.0)   # season file: tier skipped


def test_points_allowed_tiers():
    r = DEFAULT_SCORING
    assert [points_allowed_tier(x, r) for x in (0, 0.9, 1, 6.9, 7, 13.5, 14, 20.9, 21, 27, 28, 34.9, 35, 50)] == \
        [10, 10, 7, 7, 4, 4, 1, 1, 0, 0, -1, -1, -4, -4]


# ------------------------------------------------------------------ (4) mismatch warning

def _projset(*projs, season=False):
    by_pos = {}
    for p in projs:
        by_pos.setdefault(p.pos, []).append(p)
    return ProjectionSet(Path("x"), by_pos, season, "test")


def test_mismatch_warning_fires_only_above_half_a_point():
    stats = {"rec": 4, "rec_yds": 50, "rec_td": 0.5, "fumble_lost": 0}
    # half-PPR: 2 + 5 + 3 = 10.0
    fine = Projection("Blocker A", "KC", "TE", stats, 10.4)      # 0.4 off: no warning
    off = Projection("Blocker B", "KC", "TE", stats, 10.6)       # 0.6 off: warning
    assert mismatch_warnings(_projset(fine), LEAGUE1_RULES) == []
    w = mismatch_warnings(_projset(fine, off), LEAGUE1_RULES)
    assert len(w) == 1 and "Blocker B" in w[0] and "10.0" in w[0] and "10.6" in w[0] and "league.txt" in w[0]


def test_kicker_only_mismatch_is_explained_not_blamed_on_league_txt():
    k = Projection("Kicker A", "DAL", "K", {"fg": 2.2, "fga": 2.5, "xpt": 2.8}, 9.4)   # 10.06 vs 9.4
    w = mismatch_warnings(_projset(k), LEAGUE1_RULES)
    assert len(w) == 1 and "expected" in w[0] and "3.3" in w[0]
    assert mismatch_warnings(_projset(k), LEAGUE2_RULES) == []    # league2 pays 3 - 1 per miss = 9.1, within 0.5


# ------------------------------------------------------------------ (5) wrong header

def test_wrong_header_shows_found_and_expected(tmp_path):
    bad = tmp_path / "FantasyPros_Fantasy_Football_Projections_QB.csv"
    bad.write_text('"RK","PLAYER NAME",TEAM,"OPP"\n"1","Someone",KC,"at DEN"\n', encoding="utf-8")
    with pytest.raises(ExportFormatError) as e:
        parse_projection_file(bad, "QB")
    msg = str(e.value)
    assert "Header found:    RK,PLAYER NAME,TEAM,OPP" in msg
    assert "Header expected: " + ",".join(EXPECTED_HEADERS["QB"]) in msg
    assert bad.name in msg


def test_missing_position_file_is_a_clear_error(tmp_path):
    (tmp_path / "FantasyPros_Fantasy_Football_Projections_QB.csv").write_text(
        ",".join(EXPECTED_HEADERS["QB"]) + "\n", encoding="utf-8")
    with pytest.raises(ExportFormatError, match="no projection file for RB, WR, TE, K, DST"):
        load_projections(tmp_path)


# ------------------------------------------------------------------ (6) names

def test_name_normalisation_and_aliases():
    assert normalise("A.J. Sample Jr.") == normalise("AJ Sample") == "aj sample"
    assert normalise("Runner O'Neil III") == "runner oneil"
    pool = [Projection("Sample City Foxes", "", "DST", {}, 9.0), Projection("Chicago Bears", "", "DST", {}, 8.0),
            Projection("A.J. Sample Jr.", "PHI", "QB", {}, 20.0), Projection("Catcher Able", "CIN", "WR", {}, 17.0)]
    assert match_name("Sample City D/ST", "DST", pool).projection.name == "Sample City Foxes"
    assert match_name("Sample City", "", pool).projection.name == "Sample City Foxes"   # bare city, no position
    assert match_name("Bears D/ST", "DST", pool).projection.name == "Chicago Bears"
    assert match_name("CHI", "DST", pool).projection.name == "Chicago Bears"          # abbreviation table
    assert match_name("Chicago", "DST", pool).projection.name == "Chicago Bears"
    m = match_name("AJ Sample", "QB", pool)
    assert m.projection.name == "A.J. Sample Jr." and m.how == "spelling" and "I matched 'AJ Sample'" in m.line
    assert match_name("Catcher Able", "", pool).how == "exact"
    assert match_name("Catcher Abel", "WR", pool).how == "close"
    assert match_name("Catcher Able", "QB", pool).projection is None                  # wrong position given
    assert match_name("Nobody Here", "", pool).projection is None


def test_sample_roster_match_list_and_could_not_find():
    ctx = load_context(LEAGUE1, WEEK8)
    rep = base_report(ctx, "lineup", 1.5)
    text = text_report(rep)
    assert "I matched 'Catcher Abel' to 'Catcher Able'" in text
    assert "I matched 'AJ Sample' to 'A.J. Sample Jr.'" in text
    assert "I matched 'Sample City D/ST' to 'Sample City Foxes'" in text
    assert "COULD NOT FIND: 'Runner Zulu'" in text
    assert "NOT PROJECTED THIS WEEK (bye or out?)\n" + "-" * 78 + "\n'Runner Zulu'" in text
    names = [p.name for p in ctx.players]
    assert "Runner Zulu" not in names and len(names) == 14          # 15 on roster, 1 not projected
    assert all(p.proj > 0 for p in ctx.players)                     # nobody silently scored 0


# ------------------------------------------------------------------ (7) lineup optimiser

def P(name, pos, proj, floor=None, ceil=None):
    floor = proj - 3 if floor is None else floor
    return Player(name, pos, proj, floor, ceil if ceil is not None else proj + (proj - floor))


TINY = [P("QB1", "QB", 20, 15), P("QB2", "QB", 18, 16),
        P("RB A", "RB", 15, 10), P("RB B", "RB", 12, 11), P("RB C", "RB", 11.5, 11.4),
        P("WR X", "WR", 14, 9), P("WR Y", "WR", 10, 8), P("WR Z", "WR", 9.5, 9.2),
        P("TE T", "TE", 8, 6), P("TE U", "TE", 7.9, 6.5),
        P("K", "K", 8, 6), P("DEF", "DST", 7, 5)]


def test_best_lineup_is_the_known_best_set_and_flex_is_the_right_player():
    lu = best_lineup(TINY, SLOTS)
    # QB1 20 + RB A 15 + RB B 12 + WR X 14 + WR Y 10 + TE T 8 + FLEX RB C 11.5 + K 8 + DEF 7 = 105.5
    assert lu.proj_total == pytest.approx(105.5)
    assert lu.names() == {"QB1", "RB A", "RB B", "WR X", "WR Y", "TE T", "RB C", "K", "DEF"}
    assert lu.slot_of("RB C") == "FLEX"
    assert [p.name for p in bench(TINY, lu)] == ["QB2", "WR Z", "TE U"]


def test_floor_lineup_differs_where_designed():
    fl = best_lineup(TINY, SLOTS, "floor", "proj")
    # floors: QB2 16, RB C 11.4, RB B 11, WR Z 9.2, WR X 9, TE U 6.5, FLEX RB A 10, K 6, DEF 5 = 84.1
    assert fl.floor_total == pytest.approx(84.1)
    assert fl.names() == {"QB2", "RB C", "RB B", "WR Z", "WR X", "TE U", "RB A", "K", "DEF"}
    aligned = align(fl, best_lineup(TINY, SLOTS))
    assert aligned.names() == fl.names()
    # shared players keep the slot they have in the best lineup: RB C stays at FLEX, RB A/B at RB
    assert aligned.slot_of("RB C") == "FLEX" and aligned.slot_of("RB A") == "RB"


def test_ties_broken_by_floor():
    players = [P("QB", "QB", 20), P("RB1", "RB", 10), P("RB2", "RB", 10), P("WR1", "WR", 10), P("WR2", "WR", 10),
               P("TE", "TE", 5), P("K", "K", 5), P("DEF", "DST", 5),
               P("WR lowfloor", "WR", 9, 4), P("WR highfloor", "WR", 9, 7)]
    lu = best_lineup(players, SLOTS)
    assert lu.slot_of("WR highfloor") == "FLEX" and lu.slot_of("WR lowfloor") is None


def test_empty_slot_when_roster_is_short():
    lu = best_lineup([P("QB", "QB", 20), P("RB", "RB", 10)], SLOTS)
    assert lu.proj_total == pytest.approx(30) and sum(e.player is None for e in lu.entries) == 7


# ------------------------------------------------------------------ (8) close calls

def test_close_calls_at_the_threshold():
    starters = [P("QB", "QB", 20), P("RB1", "RB", 10.0), P("RB2", "RB", 15), P("WR1", "WR", 12), P("WR2", "WR", 12),
                P("TE", "TE", 9), P("K", "K", 5), P("DEF", "DST", 5), P("WR3", "WR", 11)]
    close_rb = P("RB close", "RB", 8.5)      # 1.5 below RB1: a close call (<= 1.5)
    far_rb = P("RB far", "RB", 8.4)          # 1.6 below: not
    players = starters + [close_rb, far_rb]
    lu = best_lineup(players, SLOTS)
    calls = close_calls(lu, bench(players, lu), 1.5)
    assert [(c.slot, c.starter.name, c.other.name) for c in calls] == [("RB", "RB1", "RB close")]
    assert calls[0].gap == pytest.approx(1.5)
    assert close_calls(lu, bench(players, lu), 1.4) == []


# ------------------------------------------------------------------ (9) trade

def test_trade_delta_is_difference_of_best_lineups():
    give = [P("RB C", "RB", 11.5, 11.4)]
    get = [P("WR W", "WR", 13, 9)]
    d = apply_trade(TINY, give, get, SLOTS)
    # after: QB1 20 + RB A 15 + RB B 12 + WR X 14 + WR W 13 + TE T 8 + FLEX WR Y 10 + K 8 + DEF 7 = 107.0
    assert d.before.proj_total == pytest.approx(105.5) and d.after.proj_total == pytest.approx(107.0)
    assert d.change == pytest.approx(1.5)
    assert [p.name for p in d.starters_out()] == ["RB C"] and [p.name for p in d.starters_in()] == ["WR W"]
    # starters by position: RB 38.5 -> 27.0 (-11.5), WR 24 -> 37 (+13)
    assert d.position_changes() == {"RB": pytest.approx(-11.5), "WR": pytest.approx(13.0)}
    v = trade_verdict(d, None, [])
    assert v == "Your starting lineup goes from 105.5 to 107.0 this week (+1.5); the gain is at WR, the loss is at RB."


def test_trade_that_only_changes_the_bench_reports_zero():
    give = [P("WR Z", "WR", 9.5, 9.2)]
    get = [P("WR V", "WR", 9.6, 5)]
    d = apply_trade(TINY, give, get, SLOTS)
    assert d.change == pytest.approx(0.0) and d.starters_in() == [] and d.starters_out() == []
    v = trade_verdict(d, None, give)
    assert "(+0.0)" in v and "no starter changes this week" in v and "the loss is WR depth (bench)" in v


def test_trade_with_rest_of_season_in_verdict():
    week = apply_trade(TINY, [P("RB C", "RB", 11.5, 11.4)], [P("WR W", "WR", 13, 9)], SLOTS)
    ros_players = [P(p.name, p.pos, p.proj * 10, p.floor * 10) for p in TINY]
    ros = apply_trade(ros_players, [P("RB C", "RB", 115, 114)], [P("WR W", "WR", 100, 90)], SLOTS)
    # ROS after: FLEX is WR Y 100 vs WR W 100 (tie), WR slots X 140 + 100 -> total 1055 - 115 + 100 = 1,040
    assert ros.change == pytest.approx(-15.0)
    v = trade_verdict(week, ros, [])
    assert "from 1,055.0 to 1,040.0 rest of season (-15.0)" in v


def test_trade_command_on_samples():
    ctx = load_context(LEAGUE1, WEEK8)
    rep = trade_report(ctx, ["Runner Charlie"], ["Catcher Charlie"], 1.5, load_context(LEAGUE1, ROS, "rest of season"))
    t = rep.trade
    # week: best 126.05 -> Catcher Charlie 14.6 at FLEX replaces Runner Charlie 13.4 at RB (Runner Delta slides
    # from FLEX to RB): 126.05 - 13.4 + 14.6 = 127.25 -> +1.2
    assert t.week.change == pytest.approx(14.6 - 13.4)
    assert "the gain is at WR, the loss is at RB" in t.verdict and "rest of season" in t.verdict
    assert t.ros is not None and t.ros.before.proj_total > 1000     # season-style totals
    assert ctx.proj.season is False and load_context(LEAGUE1, ROS).proj.season is True
    with pytest.raises(ExportFormatError, match="not on your roster"):
        trade_report(ctx, ["Runner Baker"], ["Catcher Charlie"], 1.5)
    with pytest.raises(ExportFormatError, match="COULD NOT FIND 'Nobody'"):
        trade_report(ctx, ["Runner Charlie"], ["Nobody"], 1.5)


# ------------------------------------------------------------------ (10) waiver

def test_waiver_ranking_on_sample_candidates():
    ctx = load_context(LEAGUE1, WEEK8)
    names = ["Catcher Baker", "Runner Echo", "Blocker Able", "Kicker Able"]
    rep = waiver_report(ctx, None, None, names, 1.5)
    ranked = [(r.add.name, round(r.gain, 2)) for r in rep.waiver.ranked]
    # Blocker Able 3.0 + 7.0 + 3.6 = 13.6 replaces Blocker Baker 2.5 + 5.5 + 3.0 - 0.2 = 10.8 -> +2.8
    # Catcher Baker 3.25 + 8.5 + 3.6 - 0.2 = 15.15 replaces Catcher Delta 2.75 + 7 + 3 - 0.2 = 12.55 -> +2.6
    # Kicker Able 2.2 x 3.3 + 2.8 = 10.06 replaces Kicker Baker 2.0 x 3.3 + 2.5 = 9.1 -> +0.96
    # Runner Echo 10.5 sits behind Runner Charlie 13.4 and Runner Delta 13.6 -> +0.0 (ranked last, not by points)
    assert ranked == [("Blocker Able", 2.8), ("Catcher Baker", 2.6), ("Kicker Able", 0.96), ("Runner Echo", 0.0)]
    assert rep.waiver.ranked[0].drop.name == "Catcher Kilo"       # weakest bench player (6.5) by default


def test_waiver_add_and_drop():
    add = P("WR W", "WR", 13, 9)
    r = apply_waiver(TINY, add, None, SLOTS)
    # WR W 13 takes WR2 from WR Y 10; WR Y 10 cannot beat RB C 11.5 at FLEX -> gain 3.0; dropped: TE U (7.9, weakest bench)
    assert r.gain == pytest.approx(3.0) and r.drop.name == "TE U" and r.drop_was_default
    r2 = apply_waiver(TINY, add, P("RB C", "RB", 11.5, 11.4), SLOTS)
    # dropping the FLEX starter RB C: FLEX becomes WR Y 10 -> 105.5 - 11.5 + 13 - 10 + 10 = 107.0 -> +1.5
    assert r2.gain == pytest.approx(1.5) and not r2.drop_was_default


# ------------------------------------------------------------------ (11) numbers, (12) reports, (13) league.txt

def test_thousands_comma_parsing():
    assert _number("3,904.1") == 3904.1 and _number("-0.9") == -0.9 and _number("") == 0.0
    ros = load_projections(ROS)
    able = next(p for p in ros.by_pos["QB"] if p.name == "Passer Able")
    assert able.stats["pass_yds"] == 2750.0                       # written as "2,750.0" in the file
    assert ros.season and "SEASON" in ros.kind_note


def test_reports_render_without_nan(tmp_path):
    ctx = load_context(LEAGUE1, WEEK8)
    rep = base_report(ctx, "lineup", 1.5)
    text, html = text_report(rep), html_report(rep)
    assert "nan" not in text.lower().replace("fantasy", "") and "nan" not in html.lower().replace("fantasy", "")
    assert "<html" in html and "Lineup card" in html and "only ranks them under your scoring" in html
    assert "TOTAL" in text and "126.1" in text                   # hand check: see test_trade_command_on_samples
    assert "<script" not in html and "http" not in html          # self-contained, no network


def test_league2_recomputes_differently_and_warns():
    ctx = load_context(LEAGUE2, WEEK8)
    rep = base_report(ctx, "lineup", 1.5)
    assert [(s.label, s.count) for s in ctx.league.slots] == [("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1),
                                                                ("FLEX", 1), ("K", 1), ("DEF", 1)]
    assert any("league.txt may not match" in w for w in rep.warnings)   # full PPR vs the half-PPR FPTS column
    able = next(p for p in ctx.players if p.name == "Passer Able")
    # 11.0 + 2.0 x 6 = 12.0 - 0.7 x 2 = -1.4 + 2.5 + 1.8 - 0.4 -> 25.5
    assert able.proj == pytest.approx(25.5)


def test_league_text_parser():
    lg = parse_league_text("# comment\n\nQB = 2  # two QBs\nrec = 1\nFLEX_FROM = WR, RB\nDEF = 0\n", DEFAULT_SCORING)
    assert lg.scoring["rec"] == 1 and lg.scoring["pass_td"] == 4
    labels = [(s.label, s.count, s.allowed) for s in lg.slots]
    assert ("QB", 2, ("QB",)) in labels and ("FLEX", 1, ("WR", "RB")) in labels
    assert not any(s.label == "DEF" for s in lg.slots)
    with pytest.raises(ExportFormatError, match="unknown setting 'rec_bonus'"):
        parse_league_text("rec_bonus = 1\n", DEFAULT_SCORING)
    with pytest.raises(ExportFormatError, match="line 1"):
        parse_league_text("QB = two\n", DEFAULT_SCORING)
    # a second flex type (nice-to-have): SUPERFLEX = 1 with SUPERFLEX_FROM = QB,WR,RB,TE
    lg2 = parse_league_text("SUPERFLEX = 1\nSUPERFLEX_FROM = QB,WR,RB,TE\n", DEFAULT_SCORING)
    assert ("SUPERFLEX", 1, ("QB", "WR", "RB", "TE")) in [(s.label, s.count, s.allowed) for s in lg2.slots]
    lu = best_lineup(TINY, lg2.slots)
    assert lu.slot_of("QB2") == "SUPERFLEX"


def test_roster_parser(tmp_path):
    f = tmp_path / "roster.csv"
    f.write_text("player,position\nSomeone,qb\nOther,\nTeam X D/ST,D/ST\n", encoding="utf-8")
    assert parse_roster(f) == [("Someone", "QB"), ("Other", ""), ("Team X D/ST", "DST")]
    f.write_text("name\nSomeone\n", encoding="utf-8")
    with pytest.raises(ExportFormatError, match="found: name"):
        parse_roster(f)


def test_make_player_ceiling_rules():
    p = Projection("X", "KC", "TE", {"rec": 4, "rec_yds": 50, "rec_td": 0.5}, 10.0,
                   low={"rec": 2, "rec_yds": 30, "rec_td": 0.2})
    pl = make_player(p, LEAGUE1_RULES)
    # proj 2 + 5 + 3 = 10.0 ; floor 1 + 3 + 1.2 = 5.2 ; no high row -> ceiling 10 + (10 - 5.2) = 14.8
    assert (pl.proj, pl.floor, pl.ceil, pl.ceil_estimated) == (pytest.approx(10.0), pytest.approx(5.2),
                                                               pytest.approx(14.8), True)
    p.high = {"rec": 6, "rec_yds": 80, "rec_td": 1}
    pl = make_player(p, LEAGUE1_RULES)
    assert pl.ceil == pytest.approx(3 + 8 + 6) and not pl.ceil_estimated
    p.low = None
    assert make_player(p, LEAGUE1_RULES).floor == pytest.approx(10.0)   # no low row: floor = projection


# ------------------------------------------------------------------ review fixes

def test_equal_totals_still_tie_break_on_floor_despite_float_order():
    # Two lineups both sum to 103.1 but add the one-decimal numbers in a different order, so the raw float
    # sums differ by a rounding crumb. Rounding first lets the floor decide: FLEX should be RBx (floor 9)
    # with WRx at WR, not WR2 (floor 3) at WR with WRx at FLEX. Floors: 52 vs 46.
    players = [P("QB", "QB", 20.3, 10), P("RB1", "RB", 12.7, 5), P("WR1", "WR", 11.1, 5), P("TE", "TE", 8.4, 4),
               P("K", "K", 7.9, 4), P("DEF", "DST", 6.6, 3), P("RB2", "RB", 13.4, 3), P("WR2", "WR", 9.3, 3),
               P("RBx", "RB", 9.3, 9), P("WRx", "WR", 13.4, 9), P("FLEXc", "TE", 5.5, 2)]
    lu = best_lineup(players, SLOTS)
    assert lu.proj_total == pytest.approx(103.1) and lu.floor_total == pytest.approx(52)
    assert lu.slot_of("RBx") == "FLEX" and lu.slot_of("WR2") is None


def test_give_and_drop_accept_roster_spelling_and_bye_players():
    ctx = load_context(LEAGUE1, WEEK8)
    # roster.csv says 'Catcher Abel'; the projection file says 'Catcher Able' (17.3): both spellings work
    rep = trade_report(ctx, ["Catcher Abel"], ["Catcher Charlie"], 1.5)
    assert rep.trade.give[0].name == "Catcher Able" and rep.trade.week.change == pytest.approx(14.6 - 17.3)
    # 'Runner Zulu' is on the roster but in no file: counted as 0.0, the trade still runs, and the ROS
    # number is still printed. Catcher Charlie 14.6 takes WR2 from Catcher Delta 12.55 -> +2.05
    ros = load_context(LEAGUE1, ROS, "rest of season")
    rep = trade_report(ctx, ["Runner Zulu"], ["Catcher Charlie"], 1.5, ros)
    assert rep.trade.give[0].proj == 0.0 and rep.trade.week.change == pytest.approx(14.6 - 12.55)
    assert rep.trade.ros is not None and "rest of season" in rep.trade.verdict
    assert any("Runner Zulu is not projected this week" in n for n in rep.trade.notes)
    text = text_report(rep)
    assert "Give: Runner Zulu (RB, 0.0)" in text and "counts as 0.0 this week" in text
    w = waiver_report(ctx, "Catcher Baker", "Runner Zulu", [], 1.5)
    assert w.waiver.single.drop.name == "Runner Zulu" and w.waiver.single.gain == pytest.approx(2.6)
    assert any("dropping him costs 0.0" in n for n in w.waiver.notes)


def test_unusable_candidates_and_duplicates_are_listed_separately(tmp_path):
    ctx = load_context(LEAGUE1, WEEK8)
    rep = waiver_report(ctx, None, None, ["Catcher Able", "Nobody Real", "Runner Echo"], 1.5)
    text = text_report(rep)
    assert [r.add.name for r in rep.waiver.ranked] == ["Runner Echo"]
    assert "NAMES I COULD NOT USE" in text and "Skipped candidate: 'Catcher Able' is already on your roster." in text
    assert "COULD NOT FIND: COULD NOT FIND" not in text and "COULD NOT FIND: 'Runner Zulu'" in text
    assert text.count("already on your roster") == 1           # not repeated under NOT PROJECTED
    lg = tmp_path / "lg"
    lg.mkdir()
    (lg / "league.txt").write_text((LEAGUE1 / "league.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (lg / "roster.csv").write_text((LEAGUE1 / "roster.csv").read_text(encoding="utf-8") + "Runner Able,RB\n",
                                   encoding="utf-8")
    ctx2 = load_context(lg, WEEK8)
    assert ctx2.problems == ["Duplicate in roster.csv: 'Runner Able' is listed twice; the second row is skipped."]
    assert len(ctx2.players) == 14 and not any("Runner Able" in u for u in ctx2.unmatched)


def test_league_and_candidate_files_with_a_byte_order_mark(tmp_path):
    from fantasy_helper.parse import parse_league, parse_name_list
    lg = tmp_path / "league.txt"
    lg.write_bytes(b"\xef\xbb\xbfQB = 2\n")
    assert parse_league(lg, DEFAULT_SCORING).slots[0].count == 2
    assert parse_league_text("﻿QB = 2\n", DEFAULT_SCORING).slots[0].count == 2
    fa = tmp_path / "fa.txt"
    fa.write_bytes(b"\xef\xbb\xbfCatcher Baker\r\nRunner Echo\r\n")
    assert parse_name_list(fa) == ["Catcher Baker", "Runner Echo"]


def test_flex_slot_without_from_line_is_an_error():
    with pytest.raises(ExportFormatError, match="SUPERFLEX_FROM"):
        parse_league_text("SUPERFLEX = 1\n", DEFAULT_SCORING)
    assert [s.label for s in parse_league_text("SUPERFLEX = 0\n", DEFAULT_SCORING).slots] == \
        ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF"]


def test_kicker_mismatch_names_the_miss_penalty_when_fg_is_already_3():
    k = Projection("Kicker Q", "DAL", "K", {"fg": 2.0, "fga": 3.5, "xpt": 2.0}, 8.0)   # league2: 6 + 2 - 1.5 = 6.5
    w = mismatch_warnings(_projset(k), LEAGUE2_RULES)
    assert len(w) == 1 and "expected" in w[0] and "missed field goal" in w[0] and "Standard" not in w[0]


def test_command_line_exit_codes_and_html(tmp_path, capsys):
    from fantasy_helper.__main__ import main
    html = tmp_path / "out.html"
    assert main(["lineup", "--league", str(LEAGUE1), "--proj", str(WEEK8), "--html", str(html)]) == 0
    out = capsys.readouterr().out
    assert "126.1" in out and html.exists() and "Lineup card" in html.read_text(encoding="utf-8")
    assert main(["lineup", "--league", str(LEAGUE1), "--proj", str(tmp_path / "nonexistent"), "--html", ""]) == 1
    assert "Problem:" in capsys.readouterr().err
    assert main(["lineup", "--league", str(LEAGUE1), "--proj", str(WEEK8),
                 "--html", str(tmp_path / "no_such_dir" / "x.html")]) == 1
    assert "Problem: could not write" in capsys.readouterr().err
    with pytest.raises(SystemExit):                              # --give and --get are required on trade
        main(["trade", "--league", str(LEAGUE1), "--proj", str(WEEK8)])
    with pytest.raises(SystemExit):                              # --opponent-total exists only on lineup
        main(["waiver", "--league", str(LEAGUE1), "--proj", str(WEEK8), "--add", "X", "--opponent-total", "1"])


# ------------------------------------------------------------------ round-2 review fixes

def test_ros_is_not_computed_when_the_player_you_get_is_missing_from_the_ros_files(tmp_path):
    # Copy the ROS folder without Catcher Charlie's rows: the rest-of-season number would then be a
    # one-sided trade (give Runner Charlie, get nobody, -28.0), which is not the trade asked about.
    ros2 = tmp_path / "ros2"
    ros2.mkdir()
    for f in ROS.iterdir():
        lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
        keep, skip = [], False
        for line in lines:
            if line.startswith('"Catcher Charlie"'):
                skip = True
                continue
            if skip and line.startswith('"","low"'):
                skip = False
                continue
            keep.append(line)
        (ros2 / f.name).write_text("".join(keep), encoding="utf-8")
    ctx = load_context(LEAGUE1, WEEK8)
    rep = trade_report(ctx, ["Runner Charlie"], ["Catcher Charlie"], 1.5, load_context(LEAGUE1, ros2, "rest of season"))
    assert rep.trade.ros is None and "rest of season" not in rep.trade.verdict
    assert rep.trade.week.change == pytest.approx(14.6 - 13.4)
    assert any("not computed: Catcher Charlie is not in the --ros files" in n for n in rep.trade.notes)
    assert any("Skipped trade target" in x for x in rep.problems)
    text = text_report(rep)
    assert "Rest of season: best lineup" not in text and "-28.0" not in text


def test_pruned_lineup_search_is_exact_and_fast():
    import itertools
    import time

    def plain_brute_force(players, slots, key, tiebreak):
        """The pre-pruning search, kept here as the reference answer."""
        groups = [(s, [p for p in players if p.pos in s.allowed]) for s in slots]
        best = [None]

        def search(i, used, val, tb):
            if i == len(groups):
                kv = (round(val, 6), round(tb, 6))
                if best[0] is None or kv > best[0]:
                    best[0] = kv
                return
            slot, elig = groups[i]
            free = [p for p in elig if p not in used]
            for combo in itertools.combinations(free, min(slot.count, len(free))):
                search(i + 1, used | frozenset(combo), val + sum(getattr(p, key) for p in combo),
                       tb + sum(getattr(p, tiebreak) for p in combo))
        search(0, frozenset(), 0.0, 0.0)
        return best[0]

    import random
    rnd = random.Random(3)
    superflex = parse_league_text("FLEX = 2\nSUPERFLEX = 1\nSUPERFLEX_FROM = QB,WR,RB,TE\n", DEFAULT_SCORING).slots
    small_superflex = parse_league_text("SUPERFLEX = 1\nSUPERFLEX_FROM = QB,WR,RB,TE\n", DEFAULT_SCORING).slots
    for trial in range(12):   # small rosters: the plain search is the slow one
        players = []
        for pos, n in (("QB", 2), ("RB", 4), ("WR", 4), ("TE", 2), ("K", 1), ("DST", 1)):
            for i in range(n):
                pr = rnd.choice([5, 8, 10, 10, 12, 12.5, 15])            # plenty of exact ties
                players.append(P(f"{pos}{i}", pos, pr, pr - rnd.choice([1, 2, 3, 3])))
        for slots in (SLOTS, small_superflex):
            for key, tb in (("proj", "floor"), ("floor", "proj")):
                lu = best_lineup(players, slots, key, tb)
                assert (round(lu.total(key), 6), round(lu.total(tb), 6)) == plain_brute_force(players, slots, key, tb)
    # 25-man dynasty roster, FLEX = 2 plus a superflex: the unpruned search ran for minutes.
    big = [P(f"{pos}{i}", pos, 25 - i * 0.7 - rnd.random(), 20 - i) for pos, n in
           (("QB", 3), ("RB", 8), ("WR", 9), ("TE", 3), ("K", 1), ("DST", 1)) for i in range(n)]
    t = time.perf_counter()
    lu = best_lineup(big, superflex)
    align(best_lineup(big, superflex, "floor", "proj"), lu)
    assert time.perf_counter() - t < 1.0
    assert len(lu.starters()) == 11 and lu.slot_of("QB1") == "SUPERFLEX"   # 1+2+2+1+2+1+1+1 slots


def test_wrong_position_in_roster_csv_says_which_file_the_player_is_in(tmp_path):
    lg = tmp_path / "lg"
    lg.mkdir()
    (lg / "league.txt").write_text((LEAGUE1 / "league.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (lg / "roster.csv").write_text("player,position\nBlocker Able,WR\nSample City D/ST,WR\nNobody Real,WR\n",
                                   encoding="utf-8")
    ctx = load_context(lg, WEEK8)
    assert ctx.players == []                                       # still not used: the position is wrong
    assert ctx.unmatched[0] == ("'Blocker Able': roster.csv says WR but 'Blocker Able' is in the TE file; "
                                "change the position in roster.csv (or leave it blank)")
    assert "is in the DEF file" in ctx.unmatched[1]
    assert ctx.unmatched[2].endswith("not in any projection file (typo in roster.csv, or on bye / injured / not projected)")


def test_repeated_command_line_names_are_counted_once():
    ctx = load_context(LEAGUE1, WEEK8)
    rep = trade_report(ctx, ["Runner Charlie", "runner charlie"], ["Catcher Charlie", "Catcher Charlie"], 1.5)
    assert len(rep.trade.give) == 1 and len(rep.trade.get) == 1
    assert rep.trade.week.change == pytest.approx(14.6 - 13.4)   # was +3.2 with Catcher Charlie at WR and FLEX
    assert rep.problems == ["'runner charlie' was given twice with --give; counted once.",
                            "'Catcher Charlie' was given twice with --get; counted once."]
    w = waiver_report(ctx, None, None, ["Runner Echo", "Runner Echo"], 1.5)
    assert [r.add.name for r in w.waiver.ranked] == ["Runner Echo"] and "given twice" in w.problems[0]


def test_league_text_rejects_negative_repeated_and_all_zero_slots():
    with pytest.raises(ExportFormatError, match="line 1: RB = -1 is below 0"):
        parse_league_text("RB = -1\n", DEFAULT_SCORING)
    with pytest.raises(ExportFormatError, match="line 2: 'rec' was already set on line 1"):
        parse_league_text("rec = 0.5\nrec = 1\n", DEFAULT_SCORING)
    with pytest.raises(ExportFormatError, match="'DEF' was already set"):
        parse_league_text("DST = 1\nDEF = 1\n", DEFAULT_SCORING)
    with pytest.raises(ExportFormatError, match="every starting slot is 0"):
        parse_league_text("QB = 0\nRB = 0\nWR = 0\nTE = 0\nFLEX = 0\nK = 0\nDEF = 0\n", DEFAULT_SCORING)
