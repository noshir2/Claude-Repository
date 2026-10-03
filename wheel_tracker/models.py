from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Option:
    underlying: str
    expiry: date
    right: str  # "C" or "P"
    strike: float


@dataclass(frozen=True)
class Trade:
    when: datetime
    symbol: str
    underlying: str
    side: str  # "buy" or "sell"
    qty: float  # contracts for options, shares for stock
    price: float  # per share (options: per share, so x100 for the contract)
    option: Option | None = None
    source: str = "export"
