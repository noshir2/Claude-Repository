"""Expiry-week check: every open short put and call from a Webull export, and the cash you would need
if every open put were assigned. Reuses wheel_tracker's CSV reader when it is importable."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .planner import CONTRACT_SIZE, PlannerError


def _money(x: float) -> str:
    """$1,234.50 with the sign in front of the dollar sign (same style as report.money)."""
    return ("-" if x < 0 else "") + f"${abs(x):,.2f}"


@dataclass
class OpenContract:
    ticker: str
    right: str
    strike: float
    expiry: date
    qty: int
    price: float | None
    days_left: int

    @property
    def kind(self) -> str:
        return "put" if self.right == "P" else "call"

    @property
    def collateral(self) -> float:
        return self.strike * CONTRACT_SIZE * self.qty if self.right == "P" else 0.0

    @property
    def moneyness(self) -> str:
        if self.price is None:
            return "no price typed"
        itm = self.price < self.strike if self.right == "P" else self.price > self.strike
        return "in the money" if itm else "out of the money"


@dataclass
class ExpiryCheck:
    today: date
    contracts: list[OpenContract]
    cash: float | None
    warnings: list[str]

    @property
    def cash_needed(self) -> float:
        return sum(c.collateral for c in self.contracts)

    @property
    def shortfall(self) -> float | None:
        return None if self.cash is None else self.cash_needed - self.cash

    def shortfall_sentence(self) -> str:
        need = _money(self.cash_needed)
        if self.cash is None:
            return f"If every open put is assigned you need {need}; pass --cash to compare with what you have."
        have = _money(self.cash)
        if self.shortfall > 0:
            return f"If every open put is assigned you need {need}; you have {have}; SHORT BY {_money(self.shortfall)}."
        return (f"If every open put is assigned you need {need}; you have {have}; "
                f"that covers it with {_money(-self.shortfall)} to spare.")


def load_export(paths):
    """Import wheel_tracker's reader only when needed, so the other commands work without it."""
    try:
        from wheel_tracker.parse import ExportFormatError, load_trades
    except ImportError:
        raise PlannerError("the expiry command needs the wheel_tracker folder next to wheel_planner "
                           "(run from the repo folder); it could not be imported. compare and roll still work.") from None
    try:
        return load_trades(paths)
    except ExportFormatError as e:
        raise PlannerError(str(e)) from None


def open_contracts(trades, today: date, prices: dict[str, float]) -> tuple[list[OpenContract], list[str]]:
    """Net short contracts per option symbol (sells minus buys) that have not expired yet."""
    net: dict[str, int] = defaultdict(int)
    info = {}
    for t in trades:
        if t.option is None:
            continue
        net[t.symbol] += t.qty if t.side == "sell" else -t.qty
        info[t.symbol] = t.option
    out, warnings = [], []
    for symbol, qty in net.items():
        o = info[symbol]
        if o.expiry < today:
            continue
        if qty < 0:
            warnings.append(f"{symbol}: you are long {-qty} contract(s); long options are not part of this check.")
            continue
        if qty == 0:
            continue
        out.append(OpenContract(o.underlying, o.right, o.strike, o.expiry, qty, prices.get(o.underlying),
                                (o.expiry - today).days))
    out.sort(key=lambda c: (c.expiry, c.ticker, c.right))
    return out, warnings


def check_expiry(paths, today: date, prices: dict[str, float], cash: float | None) -> ExpiryCheck:
    trades, warnings = load_export(paths)
    contracts, more = open_contracts(trades, today, prices)
    return ExpiryCheck(today, contracts, cash, warnings + more)
