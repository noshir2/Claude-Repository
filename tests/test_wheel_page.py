"""wheel_planner/wheel.html carries a JavaScript port of wheel_tracker and wheel_planner in its
<script id="logic"> block. These tests run that block in node on the same files the Python reads and
compare every number (0.01 for money, 0.1 for percentages). If node is missing, the node tests skip.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from wheel_planner.expiry import check_expiry
from wheel_tracker.analyze import analyze
from wheel_tracker.parse import load_trades

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_wheel import SCENARIO, write_csv  # noqa: E402  (the hand-worked scenario rows)

REPO = Path(__file__).resolve().parent.parent
HTML = REPO / "wheel_planner" / "wheel.html"
SAMPLES = REPO / "samples"
NODE = shutil.which("node")

# Extra rows on top of SCENARIO so the assigned list, opening shares and prices are exercised too.
EXTRA = [
    # FFF: put with no share purchase in the file -> listed as assigned by the user (synthetic purchase)
    ("FFF250117P00050000", "Sell", 1, 1.00, "01/06/2025 10:00:00"),
    # GGG: call then shares sold with no purchase record -> covered by an opening-shares row
    ("GGG250117C00060000", "Sell", 1, 1.00, "01/06/2025 10:00:00"),
    ("GGG", "Sell", 100, 60.00, "01/17/2025 10:00:00"),
    # HHH: 2 contracts, 1 bought back, 1 expired
    ("HHH250404P00020000", "Sell", 2, 1.00, "04/01/2025 10:00:00"),
    ("HHH250404P00020000", "Buy", 1, 0.40, "04/02/2025 10:00:00"),
    # III: a long call bought and sold, then one left to expire
    ("III250404C00010000", "Buy", 2, 0.50, "03/03/2025 10:00:00"),
    ("III250404C00010000", "Sell", 1, 0.90, "03/10/2025 10:00:00"),
]

DRIVER = r"""
const fs = require("fs");
const W = require(process.argv[2]);
const spec = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
function files(list) { return list.map(p => ({ name: require("path").basename(p), text: fs.readFileSync(p, "utf8") })); }
const out = { tracker: [], expiry: [] };
for (const c of spec.tracker) {
  const loaded = W.loadTrades(files(c.files));
  const assigned = {}; (c.assigned || []).forEach(s => assigned[s] = true);
  const a = W.analyze(loaded.trades, W.parseIsoDay(c.today), assigned, c.opening || [], c.prices || {});
  const tickers = {};
  for (const name of a.ticker_order) {
    const t = a.tickers[name];
    tickers[name] = { put_pnl: t.put_pnl, call_pnl: t.call_pnl, long_pnl: t.long_pnl, stock_pnl: t.stock_pnl,
      open_premium: t.open_premium, open_shares: t.open_shares, breakeven: W.tickerBreakeven(t), realized: W.tickerRealized(t),
      unrealized: W.tickerUnrealized(t) };
  }
  out.tracker.push({
    trades: loaded.trades.length, tickers,
    legs: a.legs.map(l => [l.contract, l.outcome, Math.round(l.pnl * 100) / 100]),
    assumed_expired: a.assumed_expired.map(l => l.contract),
    warnings: loaded.warnings.length + a.warnings.length,
    realized: W.realizedTotal(a), open_premium: W.openPremiumTotal(a), win_rate: W.winRate(a),
    put_return_annualized: W.putReturnAnnualized(a), by_month: W.byMonth(a), verdict: W.verdict(a),
  });
}
for (const c of spec.expiry) {
  const x = W.checkExpiry(files(c.files), W.parseIsoDay(c.today), c.prices || {}, c.cash);
  out.expiry.push({
    contracts: x.contracts.map(k => [k.ticker, k.kind, k.strike, W.dayToIso(k.expiry), k.days_left, k.qty, k.collateral, k.moneyness]),
    cash_needed: x.cash_needed, shortfall: x.shortfall, sentence: x.sentence, warnings: x.warnings.length,
  });
}
process.stdout.write(JSON.stringify(out));
"""


def logic_block() -> str:
    m = re.search(r'<script id="logic">(.*?)</script>', HTML.read_text(encoding="utf-8"), re.S)
    assert m, "wheel.html has no <script id=\"logic\"> block"
    return m.group(1)


def run_node(tmp_path: Path, spec: dict) -> dict:
    (tmp_path / "logic.js").write_text(logic_block(), encoding="utf-8")
    (tmp_path / "driver.js").write_text(DRIVER, encoding="utf-8")
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    proc = subprocess.run([NODE, str(tmp_path / "driver.js"), str(tmp_path / "logic.js"), str(tmp_path / "spec.json")],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def close(got, want, tol=0.01):
    if want is None:
        assert got is None, f"got {got}, expected nothing"
    else:
        assert got == pytest.approx(want, abs=tol), f"got {got}, expected {want}"


def compare_tracker(js: dict, paths, today: date, assigned=frozenset(), opening=(), prices=None):
    trades, warns = load_trades(paths)
    a = analyze(trades, today, assigned, list(opening), prices or {})
    assert js["trades"] == len(trades)
    assert set(js["tickers"]) == set(a.tickers)
    for name, t in a.tickers.items():
        j = js["tickers"][name]
        for attr in ("put_pnl", "call_pnl", "long_pnl", "stock_pnl", "open_premium", "open_shares", "realized"):
            close(j[attr], getattr(t, attr), 0.01)
        close(j["breakeven"], t.breakeven, 0.01)
        close(j["unrealized"], t.unrealized, 0.01)
    want_legs = {(l.contract, l.outcome, round(l.pnl, 2)) for l in a.legs}
    assert {tuple(l) for l in js["legs"]} == want_legs
    assert len(js["legs"]) == len(a.legs)
    assert set(js["assumed_expired"]) == {l.contract for l in a.assumed_expired}
    assert js["warnings"] == len(warns) + len(a.warnings)
    close(js["realized"], a.realized)
    close(js["open_premium"], a.open_premium)
    assert tuple(js["win_rate"]) == a.win_rate()
    if a.put_return_annualized() is None:
        assert js["put_return_annualized"] is None
    else:
        close(js["put_return_annualized"] * 100, a.put_return_annualized() * 100, 0.1)
    assert [m for m, _ in js["by_month"]] == list(a.by_month())
    for (m, v) in js["by_month"]:
        close(v, a.by_month()[m])
    return a


# ---------------------------------------------------------------- the page agrees with the Python

@pytest.mark.skipif(NODE is None, reason="node is not installed, so the page's JavaScript cannot be run here")
def test_page_tracker_matches_python_on_sample_and_scenarios(tmp_path):
    scenario = write_csv(tmp_path, SCENARIO, "scenario.csv")
    extra = write_csv(tmp_path, SCENARIO + EXTRA, "extra.csv")
    overlap_a = write_csv(tmp_path, SCENARIO[:3], "a.csv")
    overlap_b = write_csv(tmp_path, SCENARIO[:5], "b.csv")
    sample = SAMPLES / "sample_webull_orders.csv"
    spec = {"tracker": [
        {"files": [str(sample)], "today": "2026-10-21"},
        {"files": [str(scenario)], "today": "2025-06-01"},
        {"files": [str(extra)], "today": "2025-06-01", "assigned": ["FFF250117P00050000"],
         "opening": [["GGG", 100, 55.0]], "prices": {"FFF": 45.0, "BBB": 110.0}},
        {"files": [str(extra)], "today": "2025-06-01"},          # same rows, nothing extra typed -> warnings
        {"files": [str(overlap_a), str(overlap_b)], "today": "2025-06-01"},   # overlapping exports, no double count
    ], "expiry": []}
    js = run_node(tmp_path, spec)["tracker"]
    a = compare_tracker(js[0], [sample], date(2026, 10, 21))
    assert a.realized == pytest.approx(1030) and "UP $1,030.00" in js[0]["verdict"]
    compare_tracker(js[1], [scenario], date(2025, 6, 1))
    a = compare_tracker(js[2], [extra], date(2025, 6, 1), frozenset({"FFF250117P00050000"}), [("GGG", 100, 55.0)],
                        {"FFF": 45.0, "BBB": 110.0})
    assert a.tickers["FFF"].unrealized == pytest.approx(-500) and js[2]["tickers"]["FFF"]["unrealized"] == pytest.approx(-500)
    a = compare_tracker(js[3], [extra], date(2025, 6, 1))
    assert js[3]["warnings"] == 1 and "no purchase record" in a.warnings[0]
    assert js[3]["tickers"]["FFF"]["open_shares"] == 0 and "FFF250117P00050000" in js[3]["assumed_expired"]
    compare_tracker(js[4], [overlap_a, overlap_b], date(2025, 6, 1))
    assert js[4]["trades"] == 5


@pytest.mark.skipif(NODE is None, reason="node is not installed, so the page's JavaScript cannot be run here")
def test_page_expiry_matches_python(tmp_path):
    sample = SAMPLES / "wheel_planner_orders.csv"
    spec = {"tracker": [], "expiry": [
        {"files": [str(sample)], "today": "2027-11-10", "prices": {"AAA": 44.10}, "cash": 2000},
        {"files": [str(sample)], "today": "2027-11-10", "prices": {}, "cash": 9000},
        {"files": [str(sample)], "today": "2027-11-10", "prices": {}, "cash": None},
    ]}
    js = run_node(tmp_path, spec)["expiry"]
    for j, prices, cash in ((js[0], {"AAA": 44.10}, 2000), (js[1], {}, 9000), (js[2], {}, None)):
        x = check_expiry([sample], date(2027, 11, 10), prices, cash)
        want = [[c.ticker, c.kind, c.strike, str(c.expiry), c.days_left, c.qty, c.collateral, c.moneyness] for c in x.contracts]
        assert j["contracts"] == want
        close(j["cash_needed"], x.cash_needed)
        close(j["shortfall"], x.shortfall)
        assert j["warnings"] == len(x.warnings)
        if cash is not None:
            assert j["sentence"] == x.shortfall_sentence()
    assert "SHORT BY $5,500.00" in js[0]["sentence"]
    assert "$1,500.00 to spare" in js[1]["sentence"]


@pytest.mark.skipif(NODE is None, reason="node is not installed, so the page's JavaScript cannot be run here")
def test_page_parser_edge_cases(tmp_path):
    """Same refusals and tolerances as parse.py: wrong columns, unfilled orders, Excel CRLF, BOM, '1/1' fills."""
    driver = r"""
const W = require(process.argv[2]);
const out = {};
try { W.parseFile("Foo,Bar\n1,2\n", "bad.csv"); out.bad = "no error"; } catch (e) { out.bad = e.message; out.missing = e.missing; }
const H = "Name,Symbol,Side,Status,Filled,Total Qty,Price,Avg Price,Time-in-Force,Placed Time,Filled Time\r\n";
const p = W.parseFile("﻿" + H + "X,AAA250117P00050000,Sell,Cancelled,0,1,@1.00,,DAY,01/06/2025 10:00:00 EST,\r\n" +
  "X,AAA250117P00050000,Sell,Filled,1/1,1,@1.00,1.00,DAY,01/06/2025 10:00:00 EST,01/06/2025 10:00:00 EST\r\n" +
  "X,\"BRK.B\",Buy,Filled,\"1,000\",1000,@$12.50,\"$12.50\",DAY,2025-01-07 09:30,2025-01-07 09:30\r\n" +
  "X,???,Buy,Filled,1,1,1,1,DAY,01/08/2025 10:00:00 EST,01/08/2025 10:00:00 EST\r\n", "o.csv");
out.trades = p.trades.map(t => [t.symbol, t.side, t.qty, t.price, W.dayToIso(Math.floor(t.when / 86400000))]);
out.warnings = p.warnings;
out.sym = W.parseOptionSymbol("AAPL250117P00180500");
process.stdout.write(JSON.stringify(out));
"""
    (tmp_path / "logic.js").write_text(logic_block(), encoding="utf-8")
    (tmp_path / "d.js").write_text(driver, encoding="utf-8")
    proc = subprocess.run([NODE, str(tmp_path / "d.js"), str(tmp_path / "logic.js")], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert "Columns found: Foo, Bar" in out["bad"] and out["missing"] == ["Symbol", "Side", "Filled", "Avg Price", "Filled Time"]
    assert out["trades"] == [["AAA250117P00050000", "sell", 1, 1.0, "2025-01-06"], ["BRK.B", "buy", 1000, 12.5, "2025-01-07"]]
    assert len(out["warnings"]) == 1 and "unknown symbol" in out["warnings"][0]
    assert out["sym"]["underlying"] == "AAPL" and out["sym"]["right"] == "P" and out["sym"]["strike"] == 180.5
    assert out["sym"]["expiry"] == (date(2025, 1, 17) - date(1970, 1, 1)).days


@pytest.mark.skipif(NODE is None, reason="node is not installed, so the page's JavaScript cannot be run here")
def test_page_roll_refuses_what_the_python_refuses(tmp_path):
    """planner.roll raises on a zero or negative strike and on negative premiums; rollCalc must too
    (a strike of 0 used to print 'Infinity%' with a 'pays you' verdict)."""
    driver = r"""
const W = require(process.argv[2]);
const base = { old_strike: 45, old_expiry: "2026-10-16", old_premium: 1.0, buyback: 2.5, new_strike: 43, new_expiry: "2026-11-13", new_credit: 3.2, price: 44.1, iv: 60 };
const out = {};
function attempt(name, patch) { try { const r = W.rollCalc(Object.assign({}, base, patch), "2026-10-14", 4); out[name] = "ok " + r.verdict; } catch (e) { out[name] = "error " + e.message; } }
attempt("good", {}); attempt("zero_new", { new_strike: 0 }); attempt("neg_new", { new_strike: -43 }); attempt("zero_old", { old_strike: 0 });
attempt("neg_premium", { old_premium: -1 }); attempt("neg_buyback", { buyback: -0.5 });
attempt("neg_iv", { iv: -60 }); attempt("neg_price", { price: -44.1 }); attempt("neg_price_no_iv", { price: -44.1, iv: null });
attempt("blank_iv", { iv: null }); attempt("zero_iv", { iv: 0 });
process.stdout.write(JSON.stringify(out));
"""
    (tmp_path / "logic.js").write_text(logic_block(), encoding="utf-8")
    (tmp_path / "d.js").write_text(driver, encoding="utf-8")
    proc = subprocess.run([NODE, str(tmp_path / "d.js"), str(tmp_path / "logic.js")], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["good"].startswith("ok This roll pays you")
    for name in ("zero_new", "neg_new", "zero_old"):
        assert out[name] == "error Both strikes must be above zero.", out[name]
    for name in ("neg_premium", "neg_buyback"):
        assert out[name].startswith("error Premiums and the buyback cost cannot be negative"), out[name]
    # planner.roll hands a negative price or IV to Black-Scholes, which raises "must all be above zero";
    # the page used to print 53.2% odds and a -$7.59 move for IV -60.
    for name in ("neg_iv", "neg_price", "neg_price_no_iv"):
        assert out[name].startswith("error The stock price and the implied volatility cannot be negative"), out[name]
    for name in ("blank_iv", "zero_iv"):   # blank or 0 skips the odds, like the Python
        assert out[name].startswith("ok This roll pays you"), out[name]


@pytest.mark.skipif(NODE is None, reason="node is not installed, so the page's JavaScript cannot be run here")
def test_page_rounds_percentages_and_money_like_python(tmp_path):
    """JS toFixed rounds an exact tie up (0.9125 -> 91.3%); Python's format rounds it to the even digit (91.2%).
    The page's fixed() helper must agree with Python on ties and on ordinary values."""
    from wheel_planner.report import money as py_money, pct as py_pct
    values = [0.9125, 0.1825, 0.27035, 0.0222, 0.29345, 0.5625, 1.0, 0.0, 0.00005, 0.123456, 2.0 / 3, 0.9135, 0.9145]
    monies = [1.125, 2.675, 1030.0, 9970.5, -9970.5, 4500.125, 0.005, 0.015, 1234567.891, 0.0, -0.001, 44.1, 27.5]
    driver = r"""
const W = require(process.argv[2]);
const spec = JSON.parse(process.argv[3]);
process.stdout.write(JSON.stringify({
  pct1: spec.values.map(v => W.pct(v)), pct2: spec.values.map(v => W.pct(v, 2)),
  money: spec.monies.map(v => W.money(v)), money_signed: spec.monies.map(v => W.money(v, true)),
}));
"""
    (tmp_path / "logic.js").write_text(logic_block(), encoding="utf-8")
    (tmp_path / "d.js").write_text(driver, encoding="utf-8")
    proc = subprocess.run([NODE, str(tmp_path / "d.js"), str(tmp_path / "logic.js"), json.dumps({"values": values, "monies": monies})],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["pct1"] == [py_pct(v) for v in values]
    assert out["pct2"] == [py_pct(v, 2) for v in values]
    assert out["money"] == [py_money(v, False) for v in monies]
    assert out["money_signed"] == [py_money(v, True) for v in monies]
    assert py_pct(0.9125) == "91.2%" and "91.2%" in out["pct1"]   # the tie the review found


# ---------------------------------------------------------------- the page itself

def test_logic_block_is_dom_free():
    block = logic_block()
    assert not re.search(r"\b(document|window|localStorage|alert|navigator)\b", block)
    assert 'module.exports = WHEEL' in block


def test_embedded_samples_are_byte_identical_to_the_files():
    html = HTML.read_bytes()
    for block_id, name in (("sample-orders", "sample_webull_orders.csv"), ("sample-expiry-orders", "wheel_planner_orders.csv")):
        m = re.search(rb'<script type="text/plain" id="' + block_id.encode() + rb'">(.*?)</script>', html, re.S)
        assert m, f"wheel.html has no {block_id} block"
        assert m.group(1) == (SAMPLES / name).read_bytes(), f"{block_id} differs from samples/{name}"


def test_page_has_the_first_time_user_essentials():
    html = HTML.read_text(encoding="utf-8")
    assert html.count("Try it with example data") >= 5
    assert "Nothing you type or choose leaves your device" in html
    assert "Back to the toolbox" in html and 'href="../index.html"' in html
    assert "Orders, then History" in html
    for phrase in ("How did my trades do?", "Should I sell this one?", "Should I roll?", "If I get assigned", "Expiry week"):
        assert phrase in html
    assert "alert(" not in html and "confirm(" not in html and "prompt(" not in html
    # example numbers are never saved as the user's own, and the 'pretend today is' date is never remembered
    for section in ("compare", "roll", "whatif", "expiry"):
        assert f'id="{section}-example" hidden' in html
    assert html.count("withoutToday(") >= 4 and "results-assign-" in html
    assert "<script src=" not in html and "https://" not in html and "http://" not in html
    assert not (REPO / "wheel_planner" / "wheel_calculator.html").exists()
