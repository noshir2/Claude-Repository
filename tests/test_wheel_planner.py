"""Tests for wheel_planner. Every expected number is worked out by hand in a comment next to it.

Conventions under test (see wheel_planner/README.md):
  collateral = strike x 100 (put) or cost basis x 100 (call); return = premium / collateral;
  annualized = return x 365 / DTE (calendar days, min 1); odds = N(-d2) put / N(d2) call with r = 4%.
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from wheel_planner.__main__ import main
from wheel_planner.candidates import load_candidates, load_leveraged, load_notes, parse_one_liner
from wheel_planner.expiry import check_expiry
from wheel_planner.planner import (VERDICT_CREDIT, VERDICT_DEBIT, VERDICT_WORSE, Candidate, PlannerError, Rules,
                                   assignment_whatif, delta, evaluate, expected_move, income_goal_sentence,
                                   norm_cdf, prob_itm, rank, roll)
from wheel_planner.report import html_compare, money, odds_text, text_compare, text_expiry, text_roll

REPO = Path(__file__).resolve().parent.parent
SAMPLES = REPO / "samples"
HTML = REPO / "wheel_planner" / "wheel_calculator.html"
TODAY = date(2026, 10, 21)
RATE = 4.0


def cand(**kw) -> Candidate:
    base = dict(ticker="AAA", right="P", strike=45.0, expiry=date(2026, 11, 20), premium=1.00, price=50.0, iv=60.0)
    base.update(kw)
    return Candidate(**base)


# ---------------------------------------------------------------- (1) golden A, a plain put

def test_golden_a_plain_put():
    # price 50, strike 45, premium 1.00, 30 DTE (2026-10-21 -> 2026-11-20), IV 60%, r 4%
    e = evaluate(cand(), TODAY, RATE)
    assert e.dte == 30
    assert e.collateral == 4500                       # 45 x 100
    assert e.premium_dollars == 100                   # 1.00 x 100
    assert e.ret == pytest.approx(100 / 4500)         # 2.222%
    assert e.annualized == pytest.approx(100 / 4500 * 365 / 30)   # 27.04%
    assert e.per_day == pytest.approx(100 / 30)       # $3.33
    assert e.cushion == pytest.approx(0.10)           # (50 - 45) / 50
    assert e.break_even == pytest.approx(44.00)       # 45 - 1.00
    assert e.sigma_move == pytest.approx(8.60, abs=0.005)   # 50 x 0.60 x sqrt(30/365) = 8.6007
    # d1 = [ln(50/45) + (0.04 + 0.18) x 0.08219] / (0.60 x 0.28669) = (0.10536 + 0.01808) / 0.17201 = 0.7176
    # d2 = 0.7176 - 0.1720 = 0.5456 ; N(-0.5456) = 0.2927
    assert e.odds == pytest.approx(0.2927, abs=0.0005)
    assert e.odds_source == "iv"


def test_facts_file_worked_example():
    # From the verified facts: S=40, K=37.5, IV 60%, 30 DTE, r 4% -> P(put ITM) 0.379, put delta -0.316, EM 6.88
    assert prob_itm(40, 37.5, 0.60, 30, 0.04, "P") == pytest.approx(0.379, abs=0.0005)
    assert delta(40, 37.5, 0.60, 30, 0.04, "P") == pytest.approx(-0.316, abs=0.0005)
    assert expected_move(40, 0.60, 30) == pytest.approx(6.88, abs=0.005)
    # call side is the complement: P(call ITM) = N(d2) = 1 - 0.379
    assert prob_itm(40, 37.5, 0.60, 30, 0.04, "C") == pytest.approx(1 - 0.379, abs=0.0005)


# ---------------------------------------------------------------- (2) golden B, a roll

def test_golden_b_roll_for_credit():
    # old 45 put exp 2026-10-16, received 1.00, buyback 2.50; new 43 put exp 2026-11-13, credit 3.20; today 2026-10-14
    r = roll(45, date(2026, 10, 16), 1.00, 2.50, 43, date(2026, 11, 13), 3.20,
             today=date(2026, 10, 14), price=44.10, iv_pct=60, rate_pct=RATE)
    assert r.net == pytest.approx(0.70)               # 3.20 - 2.50
    assert r.net_contract == pytest.approx(70)
    assert r.days_added == 28                         # Oct 16 -> Nov 13
    assert r.new_dte == 30                            # Oct 14 -> Nov 13
    assert r.total_collected == pytest.approx(1.70)   # 1.00 + 3.20 - 2.50
    assert r.old_break_even == pytest.approx(44.00)   # 45 - 1.00
    assert r.new_break_even == pytest.approx(41.30)   # 43 - 1.70
    assert r.new_collateral == 4300
    assert r.annualized == pytest.approx(0.70 / 43 * 365 / 28)   # 21.2%
    assert r.verdict == VERDICT_CREDIT
    assert "pays you for the extra time" in r.verdict
    # odds for the new 43 put at price 44.10, IV 60, 30 DTE: d2 = [ln(44.1/43) + (0.04-0.18)x0.08219]/0.17201 = 0.0799 -> N(-0.08) = 0.468
    assert r.new_odds == pytest.approx(0.468, abs=0.001)


def test_roll_sign_rules():
    # debit: buyback 4.00, new credit 3.20 -> net -0.80
    r = roll(45, date(2026, 10, 16), 1.00, 4.00, 43, date(2026, 11, 13), 3.20, today=date(2026, 10, 14))
    assert r.net == pytest.approx(-0.80) and r.verdict == VERDICT_DEBIT
    # credit but worse break-even: roll UP to 50 for 3.00 -> net +0.50, total 1.50, new BE 48.50 > old 44.00
    r = roll(45, date(2026, 10, 16), 1.00, 2.50, 50, date(2026, 11, 13), 3.00, today=date(2026, 10, 14))
    assert r.net == pytest.approx(0.50) and r.new_break_even == pytest.approx(48.50) and r.verdict == VERDICT_WORSE
    # facts-file check: sold 100P @5.00, BTC 3.00, STO 98P @3.50 -> net +0.50, total 5.50, new BE 92.50
    r = roll(100, date(2026, 10, 16), 5.00, 3.00, 98, date(2026, 11, 20), 3.50, today=date(2026, 10, 14))
    assert r.net == pytest.approx(0.50) and r.total_collected == pytest.approx(5.50)
    assert r.old_break_even == pytest.approx(95.00) and r.new_break_even == pytest.approx(92.50)
    assert r.new_odds is None  # no price/IV given
    assert "n/a" in text_roll(r, (100, date(2026, 10, 16), 5.00, 3.00), (98, date(2026, 11, 20), 3.50),
                              None, None, date(2026, 10, 14), RATE)


# ---------------------------------------------------------------- (3) golden C, covered call below cost basis

def test_golden_c_covered_call_below_basis():
    # price 50, strike 51, premium 0.80, cost basis 52, IV 25%, 10 DTE
    c = cand(ticker="CCC", right="C", strike=51.0, expiry=TODAY + timedelta(days=10), premium=0.80, iv=25.0,
             cost_basis=52.0)
    e = evaluate(c, TODAY, RATE)
    assert e.collateral == 5200                       # cost basis 52 x 100, not price
    assert e.premium_dollars == 80
    assert e.ret == pytest.approx(80 / 5200)          # 1.538%
    assert e.annualized == pytest.approx(80 / 5200 * 365 / 10)   # 56.2%
    assert e.break_even == pytest.approx(51.20)       # 52 - 0.80
    assert e.cushion == pytest.approx(0.02)           # (51 - 50) / 50, 'upside to strike'
    # odds a call finishes ITM = N(d2); d2 = [ln(50/51) + (0.04 - 0.03125) x 0.0274] / (0.25 x 0.1655) = -0.473 -> 0.318
    assert e.odds == pytest.approx(0.318, abs=0.001)
    flags = rank([e], Rules())[0].flags
    # locked-in loss = (52 - 51) x 100 - 80 premium = $20
    assert any("lock in a loss of $20.00" in f for f in flags)
    assert e.collateral_note == ""


def test_below_basis_flag_when_premium_covers_the_gap():
    # basis 52, strike 51: the gap is $100; premium 1.50 = $150 > gap, so being called away nets +$50, not a loss
    c = cand(ticker="CCC", right="C", strike=51.0, expiry=TODAY + timedelta(days=10), premium=1.50, iv=25.0,
             cost_basis=52.0)
    flags = rank([evaluate(c, TODAY, RATE)], Rules())[0].flags
    f = next(f for f in flags if "below your cost basis" in f)
    assert "$150.00 premium covers the $100.00 gap" in f and "+$50.00" in f and "loss of $-" not in f
    # the what-if keeps the same arithmetic: (52 - 51) x 100 - 150 = -50 (a gain, see WhatIf.locked_loss)
    assert assignment_whatif(53, 1.00, 1, 51, 1.50).locked_loss == pytest.approx(-50)


def test_buying_power_rule_is_for_puts_only():
    # a covered call is written against shares already owned, so its $5,200 'collateral' uses no buying power
    e = evaluate(cand(right="C", strike=55.0, cost_basis=52.0), TODAY, RATE)
    assert not any("buying power" in f for f in rank([e], Rules(buying_power=1000))[0].flags)
    e = evaluate(cand(), TODAY, RATE)   # put: 4500 > 1000 fires
    assert any("more than your buying power of $1,000.00" in f for f in rank([e], Rules(buying_power=1000))[0].flags)


def test_covered_call_without_cost_basis_uses_price_and_says_so():
    e = evaluate(cand(right="C", strike=55.0, cost_basis=None), TODAY, RATE)
    assert e.collateral == 5000 and "no cost basis typed" in e.collateral_note
    assert not any("lock in a loss" in f for f in rank([e], Rules())[0].flags)


# ---------------------------------------------------------------- (4) normal CDF

def test_norm_cdf_known_values():
    assert norm_cdf(0) == pytest.approx(0.5, abs=1e-4)
    assert norm_cdf(1.96) == pytest.approx(0.975, abs=1e-4)
    assert norm_cdf(-1.96) == pytest.approx(0.025, abs=1e-4)


# ---------------------------------------------------------------- (5) every flag fires on the row built for it

@pytest.fixture
def sample_ranked():
    cands, has_earnings = load_candidates(SAMPLES / "wheel_planner_candidates.csv")
    rules = Rules(buying_power=6000, account=20000, leveraged=load_leveraged(),
                  notes=load_notes(SAMPLES / "wheel_planner_flags.txt"))
    return rank([evaluate(c, TODAY, RATE) for c in cands], rules), rules, has_earnings


def _who(evals, phrase):
    return {e.c.ticker for e in evals if any(phrase in f for f in e.flags)}


def test_each_flag_fires_only_where_designed(sample_ranked):
    evals, _, has_earnings = sample_ranked
    assert has_earnings
    assert {e.c.ticker for e in evals} == {"AAA", "BBB", "CCC", "DDD", "SOXL", "FFF"}
    assert _who(evals, "leveraged-ETF list") == {"SOXL"}
    assert _who(evals, "-day limit (--max-dte 45)") == {"DDD"}          # 60 DTE
    assert _who(evals, "lock in a loss") == {"CCC"}
    assert _who(evals, "more than your buying power of $6,000.00") == {"DDD"}   # 8000 > 6000; CCC 5200 is under
    assert _who(evals, "above your 25% limit") == {"CCC", "DDD"}        # 5200 = 26%, 8000 = 40% of 20000
    assert _who(evals, "rough odds of finishing in the money") == {"BBB"}   # 43.8% > 35%
    assert _who(evals, "your note says 'biotech, binary event risk'") == {"BBB"}
    assert _who(evals, "crosses the earnings date") == {"BBB"}
    assert _who(evals, "lock in a loss") == {"CCC"}
    aaa = next(e for e in evals if e.c.ticker == "AAA")
    assert aaa.flags == []


def test_flags_quote_threshold_and_never_judge(sample_ranked):
    evals, rules, has_earnings = sample_ranked
    text = text_compare(evals, rules, TODAY, RATE, 500, has_earnings)
    for f in (f for e in evals for f in e.flags):
        assert f.endswith(".") and "PASS" not in f and "NO " not in f
    assert "--max-odds 35" in text and "--buying-power 6000" in text and "--account 20000 --max-pct 25" in text
    assert "Earnings date not typed for" in text and "BBB" not in text.split("Earnings date not typed for")[1].split("\n")[0]


def test_ranking_and_sort(sample_ranked):
    evals, rules, _ = sample_ranked
    assert [e.c.ticker for e in evals] == ["BBB", "CCC", "SOXL", "FFF", "AAA", "DDD"]   # by annualized, desc
    by_cushion = rank(evals, rules, "cushion")
    assert by_cushion[0].c.ticker == "SOXL"            # 16.7% is the widest cushion
    by_odds = rank(evals, rules, "odds")
    assert by_odds[-1].c.ticker == "FFF"               # no IV -> sorted last
    assert by_odds[0].c.ticker == "DDD"                # 21.0% lowest odds


# ---------------------------------------------------------------- (6) missing IV

def test_missing_iv_gives_na_and_no_crash():
    e = evaluate(cand(ticker="FFF", iv=None), TODAY, RATE)
    assert e.odds is None and e.sigma_move is None
    assert odds_text(e) == "n/a (no IV typed)"
    assert not any("rough odds" in f for f in rank([e], Rules())[0].flags)
    text = text_compare([e], Rules(), TODAY, RATE)
    assert "n/a (no IV typed)" in text


def test_delta_as_fallback_for_odds():
    e = evaluate(cand(iv=None, delta_typed=-0.30), TODAY, RATE)
    assert e.odds == pytest.approx(0.30) and e.odds_source == "delta"
    assert "|delta|" in odds_text(e)


# ---------------------------------------------------------------- (7) bad CSV header

def test_notes_keep_a_hash_inside_the_note(tmp_path):
    p = tmp_path / "flags.txt"
    p.write_text("# a comment line\nBBB: see #2 in the notebook\n", encoding="utf-8")
    assert load_notes(p) == {"BBB": "see #2 in the notebook"}


def test_wrong_header_lists_columns_found(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(PlannerError, match=r"missing column\(s\) .*Columns found: foo, bar"):
        load_candidates(bad)


def test_csv_saved_by_excel_with_crlf_and_us_dates(tmp_path):
    # README step 2 edits the file in Excel: CRLF line ends and the expiry rewritten as 11/20/2026
    p = tmp_path / "x.csv"
    p.write_bytes(b"ticker,type,strike,expiry,premium,price,iv,cost_basis,note\r\nBBB,P,20,11/20/2026,1.50,22,110,,y\r\n")
    cands, _ = load_candidates(p)
    assert cands[0].expiry == date(2026, 11, 20)
    assert main(["compare", str(p), "--today", "2026-10-21", "--html", ""]) == 0


def test_csv_accepts_put_call_words_and_comments(tmp_path):
    p = tmp_path / "c.csv"
    p.write_text("# a comment\nticker,type,strike,expiry,premium,price,iv,cost_basis,note\n"
                 "aaa,put,45,2026-11-20,1.00,50,,,\n\nbbb,Call,55,2026-11-20,0.50,50,30,48,x\n", encoding="utf-8")
    cands, has_earnings = load_candidates(p)
    assert not has_earnings
    assert [c.ticker for c in cands] == ["AAA", "BBB"] and cands[0].right == "P" and cands[1].right == "C"
    assert cands[0].iv is None and cands[1].cost_basis == 48


# ---------------------------------------------------------------- (8) one-liner

def test_one_liner_with_and_without_optional_fields():
    c = parse_one_liner("AAA,P,45,2026-11-20,1.00,50,60")
    assert (c.ticker, c.right, c.strike, c.expiry, c.premium, c.price, c.iv, c.cost_basis) == \
           ("AAA", "P", 45.0, date(2026, 11, 20), 1.0, 50.0, 60.0, None)
    c = parse_one_liner("aaa, put ,45,2026-11-20,1.00,50")
    assert c.right == "P" and c.iv is None and c.cost_basis is None
    c = parse_one_liner("CCC,call,51,2026-10-31,0.80,50,25,52")
    assert c.right == "C" and c.cost_basis == 52.0
    with pytest.raises(PlannerError, match="6 to 8 values"):
        parse_one_liner("AAA,P,45")
    # Excel on a US Windows machine rewrites an ISO date cell as 11/20/2026 when the CSV is saved: accept it
    assert parse_one_liner("AAA,P,45,11/20/2026,1.00,50").expiry == date(2026, 11, 20)
    assert parse_one_liner("AAA,P,45,11/20/26,1.00,50").expiry == date(2026, 11, 20)
    with pytest.raises(PlannerError, match="YYYY-MM-DD"):
        parse_one_liner("AAA,P,45,20.11.2026,1.00,50")
    with pytest.raises(PlannerError, match="type must be"):
        parse_one_liner("AAA,X,45,2026-11-20,1.00,50")


# ---------------------------------------------------------------- (9) expiry command on the sample export

def test_expiry_sample_cash_and_shortfall():
    # open: AAA 45 put, BBB 30 put, CCC 55 call. DDD expired 2027-09-17; EEE was bought back (net 0).
    x = check_expiry([SAMPLES / "wheel_planner_orders.csv"], date(2027, 11, 10), {"AAA": 44.0}, 1400)
    assert [(c.ticker, c.kind, c.strike) for c in x.contracts] == [("AAA", "put", 45.0), ("BBB", "put", 30.0),
                                                                    ("CCC", "call", 55.0)]
    assert x.cash_needed == pytest.approx(7500)        # 45 x 100 + 30 x 100
    assert x.shortfall == pytest.approx(6100)          # 7500 - 1400
    assert x.contracts[0].moneyness == "in the money"  # 44 < 45
    assert x.contracts[1].moneyness == "no price typed"
    assert x.contracts[0].days_left == 9               # Nov 10 -> Nov 19
    assert "you need $7,500.00; you have $1,400.00; SHORT BY $6,100.00" in x.shortfall_sentence()
    assert "SHORT BY" in text_expiry(x)
    x2 = check_expiry([SAMPLES / "wheel_planner_orders.csv"], date(2027, 11, 10), {}, 9000)
    assert "to spare" in x2.shortfall_sentence() and "$1,500.00" in x2.shortfall_sentence()


# ---------------------------------------------------------------- (10) wheel_tracker missing

def test_expiry_polite_error_without_wheel_tracker(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "wheel_tracker.parse", None)   # makes the import raise ImportError
    with pytest.raises(PlannerError, match="could not be imported"):
        check_expiry([SAMPLES / "wheel_planner_orders.csv"], TODAY, {}, None)
    assert main(["expiry", str(SAMPLES / "wheel_planner_orders.csv")]) == 1
    assert capsys.readouterr().err.startswith("Problem:")
    # the other commands still run
    assert main(["compare", "--candidate", "AAA,P,45,2026-11-20,1.00,50,60", "--today", "2026-10-21", "--html", ""]) == 0


# ---------------------------------------------------------------- (11) HTML golden block == Python

def _golden():
    m = re.search(r'<script id="golden" type="application/json">(.*?)</script>', HTML.read_text(encoding="utf-8"),
                  re.S)
    assert m, "wheel_calculator.html has no golden block"
    return json.loads(m.group(1))


def _close(got, want, tol):
    assert got == pytest.approx(want, abs=tol), f"got {got}, expected {want}"


def test_html_golden_matches_python():
    g = _golden()
    rate = g["rate_pct"]
    ids = set()
    for ex in g["examples"]:
        ids.add(ex["id"])
        i, want = ex["input"], ex["expected"]
        if ex["kind"] == "candidate":
            c = Candidate(i["ticker"], i["type"], i["strike"], TODAY + timedelta(days=i["dte"]), i["premium"],
                          i["price"], i.get("iv"), i.get("cost_basis"))
            e = evaluate(c, TODAY, rate)
            _close(e.collateral, want["collateral"], 0.01)
            _close(e.premium_dollars, want["premium_dollars"], 0.01)
            _close(e.ret * 100, want["return_pct"], 0.1)
            _close(e.annualized * 100, want["annualized_pct"], 0.1)
            _close(e.per_day, want["per_day"], 0.01)
            _close(e.cushion * 100, want["cushion_pct"], 0.1)
            _close(e.break_even, want["break_even"], 0.01)
            _close(e.sigma_move, want["sigma_move"], 0.01)
            _close(e.odds * 100, want["odds_pct"], 0.1)
            if "locked_loss" in want:
                flags = rank([e], Rules())[0].flags
                assert any(f"lock in a loss of ${want['locked_loss']:,.2f}" in f for f in flags)
        elif ex["kind"] == "roll":
            today = date.fromisoformat(i["today"])
            r = roll(i["old_strike"], date.fromisoformat(i["old_expiry"]), i["old_premium"], i["buyback"],
                     i["new_strike"], date.fromisoformat(i["new_expiry"]), i["new_credit"], today,
                     i.get("price"), i.get("iv"), rate)
            _close(r.net, want["net"], 0.01)
            _close(r.net_contract, want["net_contract"], 0.01)
            assert r.days_added == want["days_added"]
            _close(r.total_collected, want["total_collected"], 0.01)
            _close(r.old_break_even, want["old_break_even"], 0.01)
            _close(r.new_break_even, want["new_break_even"], 0.01)
            _close(r.annualized * 100, want["annualized_pct"], 0.1)
            _close(r.new_odds * 100, want["new_odds_pct"], 0.1)
            assert want["verdict"] in r.verdict
        elif ex["kind"] == "bs":
            _close(prob_itm(i["price"], i["strike"], i["iv"] / 100, i["dte"], rate / 100, "P") * 100,
                   want["put_odds_pct"], 0.1)
            _close(delta(i["price"], i["strike"], i["iv"] / 100, i["dte"], rate / 100, "P"), want["put_delta"], 0.001)
            _close(expected_move(i["price"], i["iv"] / 100, i["dte"]), want["sigma_move"], 0.01)
        elif ex["kind"] == "whatif":
            w = assignment_whatif(i["strike"], i["put_credits"], i["contracts"], i["call_strike"], i["call_premium"])
            assert w.shares == want["shares"]
            _close(w.cost, want["cost"], 0.01)
            _close(w.premium_kept, want["premium_kept"], 0.01)
            _close(w.basis_per_share, want["basis_per_share"], 0.01)
            _close(w.call_premium, want["call_premium"], 0.01)
            _close(w.call_return * 100, want["call_return_pct"], 0.1)
            _close(w.if_called, want["if_called"], 0.01)
        else:
            raise AssertionError(f"unknown golden kind {ex['kind']}")
    assert {"A", "B", "C"} <= ids


def test_html_leveraged_list_matches_text_file():
    m = re.search(r'<script id="leveraged-etfs" type="application/json">(.*?)</script>',
                  HTML.read_text(encoding="utf-8"), re.S)
    assert m and set(json.loads(m.group(1))) == set(load_leveraged())
    assert "TQQQ" in load_leveraged() and "SOXL" in load_leveraged()


def test_html_calculator_is_self_contained():
    html = HTML.read_text(encoding="utf-8")
    assert "<script src=" not in html and "http://" not in html and "https://" not in html
    assert "fetch(" not in html and "@import" not in html
    assert "wheel_planner." in html and "localStorage" in html
    assert "not investment advice" in html


# ---------------------------------------------------------------- (12) report wording

def test_report_html_says_rough_and_never_advises(sample_ranked):
    evals, rules, has_earnings = sample_ranked
    html = html_compare(evals, rules, TODAY, RATE, 500, has_earnings)
    text = text_compare(evals, rules, TODAY, RATE, 500, has_earnings)
    assert "Rough odds ITM" in html and "Rough odds ITM" in text
    for out in (html, text):
        low = out.lower()
        assert "you should" not in low and "pass" not in low.split("flags")[1][:2000]
        assert "not investment advice" in out
    assert "<html" in html and "AAA" in html


# ---------------------------------------------------------------- (13) no nan / inf

def test_text_report_has_no_nan_or_inf(sample_ranked):
    evals, rules, has_earnings = sample_ranked
    text = text_compare(evals, rules, TODAY, RATE, 500, has_earnings)
    assert not re.search(r"\b(nan|inf)\b", text, re.I)
    # expiry day: DTE is clamped to 1, nothing divides by zero
    e = evaluate(cand(expiry=TODAY), TODAY, RATE)
    assert e.dte == 1 and e.annualized == pytest.approx(100 / 4500 * 365)
    assert evaluate(cand(expiry=TODAY - timedelta(days=5)), TODAY, RATE).dte == 1


# ---------------------------------------------------------------- the rest

def test_income_goal_sentence():
    e = evaluate(cand(), TODAY, RATE)   # 27.04% annualized
    s = income_goal_sentence(500, [e])
    # 500 x 12 / 0.27037 = 22,192
    assert s == ("To make $500.00 a month at the best annualized rate in this table (27.0%) you would need about "
                 "$22,192 of collateral working all month.")


def test_assignment_whatif():
    # 45 put, 1.00 credit, 1 contract -> 100 shares cost 4500, kept 100, basis 44.00
    w = assignment_whatif(45, 1.00, 1, 46, 0.90)
    assert (w.shares, w.cost, w.premium_kept, w.basis_per_share) == (100, 4500, 100, 44.0)
    assert w.call_premium == 90 and w.call_return == pytest.approx(0.90 / 44)   # 2.05%
    assert w.if_called == pytest.approx((46 - 44 + 0.90) * 100)                 # $290
    assert w.locked_loss is None
    # a 43 call is below the 44 basis: (44 - 43) x 100 - 90 = $10 locked in
    assert assignment_whatif(45, 1.00, 1, 43, 0.90).locked_loss == pytest.approx(10)


def test_cli_compare_writes_html_and_echoes_inputs(tmp_path, capsys):
    out = tmp_path / "r.html"
    rc = main(["compare", "--candidate", "AAA,P,45,2026-11-20,1.00,50,60", "--today", "2026-10-21",
               "--html", str(out), "--monthly-goal", "500"])
    assert rc == 0 and out.exists()
    text = capsys.readouterr().out
    assert "iv 60%" in text and "27.0%" in text and "$22,192" in text and "29.3%" in text
    assert main(["compare", "--today", "2026-10-21"]) == 1
    assert "Problem:" in capsys.readouterr().err


def test_cli_roll_golden_b(capsys):
    rc = main(["roll", "--old", "45,2026-10-16,1.00,2.50", "--new", "43,2026-11-13,3.20", "--price", "44.10",
               "--iv", "60", "--today", "2026-10-14"])
    text = capsys.readouterr().out
    assert rc == 0 and "+$0.70" in text and "+$70.00" in text and "$44.00 -> new $41.30" in text
    assert "21.2%" in text and VERDICT_CREDIT in text


def test_roll_today_and_price_errors_name_the_field(capsys):
    assert main(["roll", "--old", "45,2026-16-10,1.00,2.50", "--new", "43,2026-11-13,3.20", "--today", "2026-10-14"]) == 1
    assert "--old: expiry must be YYYY-MM-DD" in capsys.readouterr().err
    assert main(["roll", "--old", "45,2026-10-16,abc,2.50", "--new", "43,2026-11-13,3.20"]) == 1
    assert "--old: premium received should be a number" in capsys.readouterr().err
    assert main(["compare", "--candidate", "AAA,P,45,2026-11-20,1.00,50,60", "--today", "21/10/2026", "--html", ""]) == 1
    assert "--today: date must be YYYY-MM-DD" in capsys.readouterr().err
    assert main(["expiry", str(SAMPLES / "wheel_planner_orders.csv"), "--price", "AAA=abc"]) == 1
    assert "--price: price for AAA should be a number" in capsys.readouterr().err


def test_nonsense_inputs_are_refused(capsys):
    with pytest.raises(PlannerError, match="after the old expiry"):   # new expiry before the old one
        roll(45, date(2026, 11, 13), 1.00, 2.50, 43, date(2026, 10, 16), 3.20, today=date(2026, 10, 14))
    with pytest.raises(PlannerError, match="IV cannot be negative"):
        evaluate(cand(iv=-60), TODAY, RATE)
    assert main(["compare", "--candidate", "AAA,P,45,2026-11-20,1.00,50,60", "--today", "2026-10-21", "--html", "",
                 "--monthly-goal", "-5"]) == 1
    assert "--monthly-goal must be above zero" in capsys.readouterr().err
    # negative money is refused everywhere, not formatted as '$-5.00'
    with pytest.raises(PlannerError, match="cannot be negative"):
        roll(45, date(2026, 10, 16), 1.00, -2.50, 43, date(2026, 11, 13), 3.20, today=date(2026, 10, 14))
    assert main(["expiry", str(SAMPLES / "wheel_planner_orders.csv"), "--cash", "-5", "--today", "2027-11-10"]) == 1
    assert "--cash cannot be negative" in capsys.readouterr().err


def test_roll_on_or_after_new_expiry_warns_and_says_one_day(capsys):
    rc = main(["roll", "--old", "45,2026-10-16,1.00,2.50", "--new", "43,2026-11-13,3.20", "--price", "44.10",
               "--iv", "60", "--today", "2026-11-13"])
    text = capsys.readouterr().out
    assert rc == 0 and "has 1 day left" in text and "over 1 day\n" in text and "1 days" not in text
    assert "PLEASE CHECK" in text and "on or before today (2026-11-13); treated as 1 day left" in text
    # compare says the same thing for an expiry that has passed
    main(["compare", "--candidate", "OLD,P,45,2026-01-20,1.00,50,60", "--today", "2026-10-21", "--html", ""])
    assert "OLD: expiry 2026-01-20 is on or before today (2026-10-21); treated as 1 day left." in capsys.readouterr().out


def test_zero_iv_and_zero_cost_basis_notes_agree_with_the_echo():
    e = evaluate(cand(iv=0.0), TODAY, RATE)
    assert e.odds is None and odds_text(e) == "n/a (IV 0 typed)"
    e = evaluate(cand(right="C", strike=55.0, cost_basis=0.0), TODAY, RATE)
    assert e.collateral == 5000 and e.collateral_note.startswith("cost basis 0 typed")


def test_money_helper_matches_wheel_tracker_style():
    assert money(1234.5, False) == "$1,234.50" and money(-5) == "-$5.00" and money(5) == "+$5.00"
