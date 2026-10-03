"""Turn a list of trades into wheel results.

Money rules (all cash-based, nothing is estimated):
  * A short option's premium counts as "made" only once the contract is finished:
    bought back, expired, or assigned. Premium on contracts still open is shown separately.
  * Buying back an option costs money and is subtracted (that is how rolls show up).
  * When a put is assigned you buy shares at the strike; no profit or loss exists on those
    shares until you sell them (called away by a covered call, or sold yourself).
  * Stock gains/losses pair each sale with the oldest shares you still hold (FIFO).
"""
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, time

from .models import Option, Trade

CONTRACT_SIZE = 100
ASSIGNMENT_WINDOW_DAYS = 4  # shares from an assignment can post a few days after expiry


@dataclass
class OptionLeg:
    """One finished option position (or part of one)."""
    contract: str
    underlying: str
    right: str
    strike: float
    expiry: date
    direction: str  # "short" (you sold it) or "long" (you bought it)
    qty: int
    opened: date
    closed: date
    open_price: float
    close_price: float
    outcome: str  # "bought back" / "sold" / "expired" / "assigned"
    pnl: float

    @property
    def collateral(self) -> float:
        return self.strike * CONTRACT_SIZE * self.qty

    @property
    def days(self) -> int:
        return max(1, (self.closed - self.opened).days)


@dataclass
class OpenOption:
    contract: str
    underlying: str
    right: str
    strike: float
    expiry: date
    direction: str
    qty: int
    opened: date
    open_price: float

    @property
    def premium(self) -> float:
        return self.open_price * CONTRACT_SIZE * self.qty


@dataclass
class StockSale:
    underlying: str
    date: date
    qty: float
    sell_price: float
    cost_price: float

    @property
    def pnl(self) -> float:
        return (self.sell_price - self.cost_price) * self.qty


@dataclass
class TickerSummary:
    underlying: str
    put_pnl: float = 0.0
    call_pnl: float = 0.0
    long_pnl: float = 0.0
    stock_pnl: float = 0.0
    open_premium: float = 0.0
    open_shares: float = 0.0
    open_cost: float = 0.0
    price: float | None = None  # current share price, only if the user supplied it

    @property
    def realized(self) -> float:
        return self.put_pnl + self.call_pnl + self.long_pnl + self.stock_pnl

    @property
    def breakeven(self) -> float | None:
        """Share price at which this ticker's total result (made so far + shares held) is zero."""
        if self.open_shares <= 0:
            return None
        return (self.open_cost - self.realized) / self.open_shares

    @property
    def unrealized(self) -> float | None:
        if self.open_shares <= 0 or self.price is None:
            return None
        return self.price * self.open_shares - self.open_cost


@dataclass
class Analysis:
    today: date
    legs: list[OptionLeg] = field(default_factory=list)
    open_options: list[OpenOption] = field(default_factory=list)
    stock_sales: list[StockSale] = field(default_factory=list)
    tickers: dict[str, TickerSummary] = field(default_factory=dict)
    assumed_expired: list[OptionLeg] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def realized(self) -> float:
        return sum(t.realized for t in self.tickers.values())

    @property
    def open_premium(self) -> float:
        return sum(t.open_premium for t in self.tickers.values())

    def total(self, attr: str) -> float:
        return sum(getattr(t, attr) for t in self.tickers.values())

    def short_legs(self, right: str | None = None) -> list[OptionLeg]:
        return [l for l in self.legs if l.direction == "short" and (right is None or l.right == right)]

    def win_rate(self) -> tuple[int, int]:
        short = self.short_legs()
        return sum(1 for l in short if l.pnl > 0), len(short)

    def put_return_annualized(self) -> float | None:
        """Put premium kept (net of buybacks) per dollar of cash secured per day, scaled to a year."""
        puts = self.short_legs("P")
        capital_days = sum(l.collateral * l.days for l in puts)
        if not capital_days:
            return None
        return sum(l.pnl for l in puts) / capital_days * 365

    def by_month(self) -> dict[str, float]:
        months: dict[str, float] = defaultdict(float)
        for leg in self.legs:
            months[leg.closed.strftime("%Y-%m")] += leg.pnl
        for sale in self.stock_sales:
            months[sale.date.strftime("%Y-%m")] += sale.pnl
        return dict(sorted(months.items()))


def _run_contract(trades: list[Trade]):
    """Walk one contract's trades in order, pairing buys with sells first-in-first-out."""
    legs: list[OptionLeg] = []
    lots: deque[list] = deque()  # [qty, price, date, direction]
    for t in trades:
        remaining = t.qty
        closing_direction = "long" if t.side == "sell" else "short"
        while remaining > 0 and lots and lots[0][3] == closing_direction:
            lot = lots[0]
            q = min(remaining, lot[0])
            if lot[3] == "short":
                pnl = (lot[1] - t.price) * CONTRACT_SIZE * q
                outcome = "bought back"
            else:
                pnl = (t.price - lot[1]) * CONTRACT_SIZE * q
                outcome = "sold"
            legs.append(OptionLeg(t.symbol, t.option.underlying, t.option.right, t.option.strike,
                                  t.option.expiry, lot[3], q, lot[2], t.when.date(), lot[1],
                                  t.price, outcome, pnl))
            lot[0] -= q
            remaining -= q
            if lot[0] == 0:
                lots.popleft()
        if remaining > 0:
            lots.append([remaining, t.price, t.when.date(), "short" if t.side == "sell" else "long"])
    return legs, lots


def _find_assignment_shares(pool: list[Trade], claimed: set, option: Option, shares: int):
    side = "buy" if option.right == "P" else "sell"
    for i, s in enumerate(pool):
        if (i not in claimed and s.side == side and abs(s.qty - shares) < 1e-6
                and abs(s.price - option.strike) < 0.011
                and 0 <= (s.when.date() - option.expiry).days <= ASSIGNMENT_WINDOW_DAYS):
            return i
    return None


def analyze(trades: list[Trade], today: date, assigned: frozenset[str] = frozenset(),
            opening_shares: list[tuple[str, float, float]] = (),
            prices: dict[str, float] | None = None) -> Analysis:
    result = Analysis(today=today)
    prices = prices or {}

    option_trades: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        if t.option:
            option_trades[t.symbol].append(t)
    wheel_tickers = {t.option.underlying for ts in option_trades.values() for t in ts[:1]}
    stock_trades = [t for t in trades if not t.option and t.underlying in wheel_tickers]
    stock_pool: dict[str, list[Trade]] = defaultdict(list)
    for t in stock_trades:
        stock_pool[t.underlying].append(t)
    claimed: dict[str, set] = defaultdict(set)
    synthetic: list[Trade] = []

    for contract, ts in option_trades.items():
        legs, lots = _run_contract(sorted(ts, key=lambda t: t.when))
        opt = ts[0].option
        for lot in lots:
            qty, price, opened, direction = lot
            if opt.expiry >= today:
                result.open_options.append(OpenOption(contract, opt.underlying, opt.right, opt.strike,
                                                      opt.expiry, direction, qty, opened, price))
                continue
            if direction == "long":
                legs.append(OptionLeg(contract, opt.underlying, opt.right, opt.strike, opt.expiry,
                                      "long", qty, opened, opt.expiry, price, 0.0, "expired",
                                      -price * CONTRACT_SIZE * qty))
                continue
            premium = price * CONTRACT_SIZE * qty
            shares = qty * CONTRACT_SIZE
            idx = _find_assignment_shares(stock_pool[opt.underlying], claimed[opt.underlying], opt, shares)
            if idx is not None:
                claimed[opt.underlying].add(idx)
                outcome = "assigned"
            elif contract in assigned:
                outcome = "assigned"
                synthetic.append(Trade(datetime.combine(opt.expiry, time(16, 0)), opt.underlying,
                                       opt.underlying, "buy" if opt.right == "P" else "sell", shares,
                                       opt.strike, source="assignment"))
            else:
                outcome = "expired"
            leg = OptionLeg(contract, opt.underlying, opt.right, opt.strike, opt.expiry, "short",
                            qty, opened, opt.expiry, price, 0.0, outcome, premium)
            legs.append(leg)
            if outcome == "expired":
                result.assumed_expired.append(leg)
        result.legs += legs

    def summary(name: str) -> TickerSummary:
        if name not in result.tickers:
            result.tickers[name] = TickerSummary(name, price=prices.get(name))
        return result.tickers[name]

    for leg in result.legs:
        s = summary(leg.underlying)
        if leg.direction == "long":
            s.long_pnl += leg.pnl
        elif leg.right == "P":
            s.put_pnl += leg.pnl
        else:
            s.call_pnl += leg.pnl
    for o in result.open_options:
        if o.direction == "short":
            summary(o.underlying).open_premium += o.premium

    # Shares: pair every sale with the oldest shares still held.
    lots_by_ticker: dict[str, deque] = defaultdict(deque)
    events = [(datetime.min, "buy", name, shares, cost) for name, shares, cost in opening_shares]
    events += [(t.when, t.side, t.underlying, t.qty, t.price) for t in stock_trades + synthetic]
    for when, side, name, qty, price in sorted(events, key=lambda e: e[0]):
        lots = lots_by_ticker[name]
        if side == "buy":
            lots.append([qty, price])
            continue
        remaining = qty
        while remaining > 1e-9 and lots:
            lot = lots[0]
            q = min(remaining, lot[0])
            result.stock_sales.append(StockSale(name, when.date(), q, price, lot[1]))
            lot[0] -= q
            remaining -= q
            if lot[0] <= 1e-9:
                lots.popleft()
        if remaining > 1e-9:
            result.warnings.append(
                f"{name}: sold {remaining:g} shares on {when.date()} that I have no purchase record for "
                "(bought before your export starts?). Their profit/loss is NOT counted. "
                "Add them to data/opening_shares.csv to fix this.")
    for sale in result.stock_sales:
        summary(sale.underlying).stock_pnl += sale.pnl
    for name, lots in lots_by_ticker.items():
        s = summary(name)
        s.open_shares = sum(l[0] for l in lots)
        s.open_cost = sum(l[0] * l[1] for l in lots)
    result.legs.sort(key=lambda l: (l.closed, l.contract))
    return result
