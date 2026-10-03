from datetime import date

import pytest

from wheel_tracker.analyze import analyze
from wheel_tracker.parse import ExportFormatError, load_trades, parse_file, parse_option_symbol
from wheel_tracker.report import html_report, money, text_report

HEADER = "Name,Symbol,Side,Status,Filled,Total Qty,Price,Avg Price,Time-in-Force,Placed Time,Filled Time\n"
TODAY = date(2025, 6, 1)


def write_csv(tmp_path, rows, name="orders.csv"):
    lines = [HEADER]
    for symbol, side, qty, price, when in rows:
        lines.append(f"X,{symbol},{side},Filled,{qty},{qty},@{price},{price},DAY,{when} EST,{when} EST\n")
    path = tmp_path / name
    path.write_text("".join(lines))
    return path


# One scenario per wheel situation; every expected number below was worked out by hand.
SCENARIO = [
    # AAA: put sold for $100, expires worthless -> +100
    ("AAA250117P00050000", "Sell", 1, 1.00, "01/06/2025 10:00:00"),
    # BBB: put sold +200, assigned (100 sh bought @100), call sold +150, called away @105 (+500) -> 850
    ("BBB250221P00100000", "Sell", 1, 2.00, "02/03/2025 10:00:00"),
    ("BBB", "Buy", 100, 100.00, "02/24/2025 09:30:00"),
    ("BBB250321C00105000", "Sell", 1, 1.50, "02/25/2025 10:00:00"),
    ("BBB", "Sell", 100, 105.00, "03/24/2025 09:30:00"),
    # CCC: sold 0.50, bought back 0.20 -> +30
    ("CCC250404P00020000", "Sell", 1, 0.50, "04/01/2025 12:00:00"),
    ("CCC250404P00020000", "Buy", 1, 0.20, "04/10/2025 12:00:00"),
    # DDD: roll. Sold 1.00, bought back 2.50 (-150), new put sold 2.00 expires (+200) -> +50
    ("DDD250404P00030000", "Sell", 1, 1.00, "03/01/2025 10:00:00"),
    ("DDD250404P00030000", "Buy", 1, 2.50, "04/02/2025 10:00:00"),
    ("DDD250502P00028000", "Sell", 1, 2.00, "04/02/2025 10:00:05"),
    # EEE: still open, expires in the future -> not counted as made
    ("EEE271217P00040000", "Sell", 1, 3.00, "05/01/2025 10:00:00"),
]


@pytest.fixture
def result(tmp_path):
    trades, warns = load_trades([write_csv(tmp_path, SCENARIO)])
    assert warns == []
    return analyze(trades, TODAY)


def test_option_symbol():
    o = parse_option_symbol("AAPL250117P00180500")
    assert (o.underlying, o.expiry, o.right, o.strike) == ("AAPL", date(2025, 1, 17), "P", 180.5)
    assert parse_option_symbol("AAPL") is None


def test_ticker_totals(result):
    t = result.tickers
    assert t["AAA"].realized == pytest.approx(100)
    assert t["BBB"].put_pnl == pytest.approx(200)
    assert t["BBB"].call_pnl == pytest.approx(150)
    assert t["BBB"].stock_pnl == pytest.approx(500)
    assert t["BBB"].realized == pytest.approx(850)
    assert t["CCC"].realized == pytest.approx(30)
    assert t["DDD"].realized == pytest.approx(50)


def test_open_position_not_counted_as_made(result):
    assert result.tickers["EEE"].realized == 0
    assert result.tickers["EEE"].open_premium == pytest.approx(300)
    assert result.realized == pytest.approx(100 + 850 + 30 + 50)
    assert result.open_premium == pytest.approx(300)


def test_assignment_found_in_export_is_not_assumed_expired(result):
    outcomes = {l.contract: l.outcome for l in result.legs}
    assert outcomes["BBB250221P00100000"] == "assigned"
    assert outcomes["BBB250321C00105000"] == "assigned"
    assert outcomes["AAA250117P00050000"] == "expired"
    assumed = {l.contract for l in result.assumed_expired}
    assert "BBB250221P00100000" not in assumed and "AAA250117P00050000" in assumed


def test_win_rate_counts_buyback_loss(result):
    # legs: AAA win, BBB put win, BBB call win, CCC win, DDD buyback loss, DDD new put win
    assert result.win_rate() == (5, 6)


def test_annualized_put_return(result):
    puts = result.short_legs("P")
    cap_days = sum(l.strike * 100 * l.days for l in puts)
    assert result.put_return_annualized() == pytest.approx(sum(l.pnl for l in puts) / cap_days * 365)
    assert result.put_return_annualized() > 0


def test_assigned_file_creates_share_purchase(tmp_path):
    rows = [("FFF250117P00050000", "Sell", 1, 1.00, "01/06/2025 10:00:00")]
    trades, _ = load_trades([write_csv(tmp_path, rows)])
    r = analyze(trades, TODAY, assigned=frozenset({"FFF250117P00050000"}))
    f = r.tickers["FFF"]
    assert f.put_pnl == pytest.approx(100)
    assert f.open_shares == 100 and f.open_cost == pytest.approx(5000)
    assert f.breakeven == pytest.approx((5000 - 100) / 100)  # 49.00
    assert not r.assumed_expired


def test_unrealized_with_price(tmp_path):
    rows = [("FFF250117P00050000", "Sell", 1, 1.00, "01/06/2025 10:00:00")]
    trades, _ = load_trades([write_csv(tmp_path, rows)])
    r = analyze(trades, TODAY, frozenset({"FFF250117P00050000"}), prices={"FFF": 45.0})
    assert r.tickers["FFF"].unrealized == pytest.approx(-500)


def test_sale_without_purchase_record_warns(tmp_path):
    rows = [("GGG250117C00060000", "Sell", 1, 1.00, "01/06/2025 10:00:00"),
            ("GGG", "Sell", 100, 60.00, "01/17/2025 10:00:00")]
    trades, _ = load_trades([write_csv(tmp_path, rows)])
    r = analyze(trades, TODAY)
    assert any("GGG" in w and "no purchase record" in w for w in r.warnings)
    assert r.tickers["GGG"].stock_pnl == 0
    r2 = analyze(trades, TODAY, opening_shares=[("GGG", 100, 55.0)])
    assert r2.tickers["GGG"].stock_pnl == pytest.approx(500)
    assert not r2.warnings


def test_partial_buyback(tmp_path):
    rows = [("HHH250404P00020000", "Sell", 2, 1.00, "04/01/2025 10:00:00"),
            ("HHH250404P00020000", "Buy", 1, 0.40, "04/02/2025 10:00:00")]
    trades, _ = load_trades([write_csv(tmp_path, rows)])
    r = analyze(trades, TODAY)
    # 1 contract bought back (+60), 1 expired (+100)
    assert r.tickers["HHH"].put_pnl == pytest.approx(160)


def test_overlapping_exports_are_not_double_counted(tmp_path):
    a = write_csv(tmp_path, SCENARIO[:3], "a.csv")
    b = write_csv(tmp_path, SCENARIO[:5], "b.csv")
    trades, _ = load_trades([a, b])
    assert len(trades) == 5


def test_missing_columns_gives_clear_error(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Foo,Bar\n1,2\n")
    with pytest.raises(ExportFormatError, match="Columns found: Foo, Bar"):
        parse_file(bad)


def test_unfilled_orders_ignored(tmp_path):
    path = tmp_path / "o.csv"
    path.write_text(HEADER + "X,AAA250117P00050000,Sell,Cancelled,0,1,@1.00,,DAY,01/06/2025 10:00:00 EST,\n")
    trades, _ = parse_file(path)
    assert trades == []


def test_reports_render(result):
    text = text_report(result)
    assert "UP $1,030.00" in text and "$300.00" in text
    assert "<html" in html_report(result)
    assert money(-5) == "-$5.00" and money(5) == "+$5.00" and money(5, False) == "$5.00"
