"""Read Webull order-history CSV exports into Trade objects."""
import csv
import re
from datetime import date, datetime
from pathlib import Path

from .models import Option, Trade

OPTION_RE = re.compile(r"^([A-Z][A-Z.]{0,5}?)(\d{6})([CP])(\d{8})$")
STOCK_RE = re.compile(r"^[A-Z][A-Z.\-]{0,5}$")
TZ_SUFFIX_RE = re.compile(r"\s+[A-Za-z]{2,5}$")
TIME_FORMATS = (
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y",
    "%Y-%m-%d",
)


class ExportFormatError(ValueError):
    pass


def parse_option_symbol(symbol: str) -> Option | None:
    m = OPTION_RE.match(symbol)
    if not m:
        return None
    underlying, ymd, right, strike = m.groups()
    expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:]))
    return Option(underlying, expiry, right, int(strike) / 1000)


def _number(text: str) -> float | None:
    cleaned = text.strip().lstrip("@").replace("$", "").replace(",", "")
    if not cleaned:
        return None
    if "/" in cleaned:  # "1/1" style filled/total
        cleaned = cleaned.split("/")[0]
    return float(cleaned)


def _time(text: str) -> datetime:
    text = text.strip()
    m = TZ_SUFFIX_RE.search(text)
    if m and m.group().strip().upper() not in ("AM", "PM"):
        text = text[: m.start()]
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ExportFormatError(f"Could not understand the date/time {text!r}") from None


def _column(headers: dict[str, str], *names: str) -> str | None:
    for name in names:
        if name in headers:
            return headers[name]
    return None


def parse_file(path: str | Path) -> tuple[list[Trade], list[str]]:
    """Return (trades, warnings) for one Webull order-history CSV."""
    trades: list[Trade] = []
    warnings: list[str] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        c_symbol = _column(headers, "symbol")
        c_side = _column(headers, "side")
        c_qty = _column(headers, "filled", "filled qty", "total qty")
        c_price = _column(headers, "avg price", "price")
        c_time = _column(headers, "filled time", "placed time")
        c_status = _column(headers, "status")
        missing = [n for n, c in (("Symbol", c_symbol), ("Side", c_side), ("Filled", c_qty),
                                  ("Avg Price", c_price), ("Filled Time", c_time)) if c is None]
        if missing:
            raise ExportFormatError(
                f"{Path(path).name}: missing column(s) {', '.join(missing)}. "
                f"Columns found: {', '.join(reader.fieldnames or [])}"
            )
        for line_no, row in enumerate(reader, start=2):
            status = (row.get(c_status) or "").strip().lower() if c_status else ""
            qty = _number(row.get(c_qty) or "")
            when_text = (row.get(c_time) or "").strip()
            if status in ("failed", "rejected") or not qty or not when_text:
                continue  # never filled
            symbol = (row.get(c_symbol) or "").strip().upper()
            side_text = (row.get(c_side) or "").strip().lower()
            side = "buy" if side_text.startswith("buy") else "sell" if side_text.startswith("sell") else None
            price = _number(row.get(c_price) or "")
            if side is None or price is None:
                warnings.append(f"{Path(path).name} line {line_no}: skipped (unreadable side or price)")
                continue
            option = parse_option_symbol(symbol)
            if option:
                trades.append(Trade(_time(when_text), symbol, option.underlying, side,
                                    int(round(qty)), price, option))
            elif STOCK_RE.match(symbol):
                trades.append(Trade(_time(when_text), symbol, symbol, side, qty, price))
            else:
                warnings.append(f"{Path(path).name} line {line_no}: skipped unknown symbol {symbol!r}")
    return trades, warnings


def load_trades(paths) -> tuple[list[Trade], list[str]]:
    """Load several exports. Fills repeated in an earlier file are dropped (overlapping date ranges)."""
    all_trades: list[Trade] = []
    warnings: list[str] = []
    seen: set = set()
    for path in paths:
        trades, warns = parse_file(path)
        warnings += warns
        fresh = [t for t in trades if (t.when, t.symbol, t.side, t.qty, t.price) not in seen]
        seen |= {(t.when, t.symbol, t.side, t.qty, t.price) for t in trades}
        all_trades += fresh
    all_trades.sort(key=lambda t: t.when)
    return all_trades, warnings
