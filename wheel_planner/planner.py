"""Pure math for the wheel planner. No file or screen I/O here, so every formula is easy to test.

Conventions (all pinned by tests/test_wheel_planner.py and explained in README.md):
  * Collateral for a cash-secured put = strike x 100 (Webull holds the full strike; the premium
    does not reduce the hold). For a covered call it is cost basis x 100 when a cost basis was
    typed, else price x 100 with a note.
  * Return on collateral = premium / collateral. Annualized = return x 365 / DTE.
  * DTE = calendar days from today to expiry, minimum 1.
  * Rough odds of finishing in the money = N(-d2) for a put, N(d2) for a call, Black-Scholes d2
    with the risk-free rate (default 4%) and no dividends. Labelled "rough" everywhere.
  * 1-sigma expected move = price x IV x sqrt(DTE / 365).
"""
import math
from dataclasses import dataclass, field
from datetime import date

CONTRACT_SIZE = 100
DEFAULT_RATE_PCT = 4.0        # 4-week T-bill coupon-equivalent yield, 2026-10-20 (Treasury daily bill rates)
DEFAULT_MAX_DTE = 45
DEFAULT_MAX_ODDS_PCT = 35.0
DEFAULT_MAX_PCT = 25.0


class PlannerError(ValueError):
    """Anything the user can fix by changing an input."""


def norm_cdf(x: float) -> float:
    """Standard normal CDF, the 'phi' example from the Python math docs."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def days_to_expiry(expiry: date, today: date) -> int:
    """Calendar days, never less than 1 (so nothing divides by zero on expiry day)."""
    return max(1, (expiry - today).days)


def d1_d2(price: float, strike: float, iv: float, dte: int, rate: float) -> tuple[float, float]:
    """Black-Scholes d1, d2 with no dividend yield. iv and rate as decimals (0.60, 0.04)."""
    if price <= 0 or strike <= 0 or iv <= 0 or dte <= 0:
        raise PlannerError("price, strike, IV and days to expiry must all be above zero")
    t = dte / 365
    sig_sqrt_t = iv * math.sqrt(t)
    d1 = (math.log(price / strike) + (rate + iv * iv / 2) * t) / sig_sqrt_t
    return d1, d1 - sig_sqrt_t


def prob_itm(price: float, strike: float, iv: float, dte: int, rate: float, right: str) -> float:
    """Rough chance the option finishes in the money: N(-d2) for a put, N(d2) for a call."""
    _, d2 = d1_d2(price, strike, iv, dte, rate)
    return norm_cdf(-d2) if right == "P" else norm_cdf(d2)


def delta(price: float, strike: float, iv: float, dte: int, rate: float, right: str) -> float:
    """Black-Scholes delta: N(d1) for a call, N(d1) - 1 for a put."""
    d1, _ = d1_d2(price, strike, iv, dte, rate)
    return norm_cdf(d1) if right == "C" else norm_cdf(d1) - 1


def expected_move(price: float, iv: float, dte: int) -> float:
    """1-sigma expected move in dollars: price x IV x sqrt(DTE / 365)."""
    return price * iv * math.sqrt(dte / 365)


@dataclass(frozen=True)
class Candidate:
    """One put or call exactly as typed. premium and price are per share; iv is a percent (60)."""
    ticker: str
    right: str              # "P" or "C"
    strike: float
    expiry: date
    premium: float
    price: float
    iv: float | None = None
    cost_basis: float | None = None
    note: str = ""
    earnings: date | None = None
    delta_typed: float | None = None   # optional: |delta| from the chain, used only when IV is blank

    @property
    def kind(self) -> str:
        return "put" if self.right == "P" else "call"


@dataclass
class Evaluation:
    """Everything the compare table prints for one candidate."""
    c: Candidate
    dte: int
    collateral: float
    collateral_note: str
    premium_dollars: float
    ret: float                 # return on collateral, decimal
    annualized: float          # decimal
    per_day: float
    cushion: float             # decimal; put: (price - strike) / price; call: (strike - price) / price
    break_even: float
    sigma_move: float | None
    odds: float | None         # decimal probability of finishing in the money
    odds_source: str           # "iv", "delta" or "none"
    flags: list[str] = field(default_factory=list)
    order: int = 0             # position in the typed input, so the echo keeps your order


def evaluate(c: Candidate, today: date, rate_pct: float = DEFAULT_RATE_PCT) -> Evaluation:
    if c.strike <= 0 or c.price <= 0:
        raise PlannerError(f"{c.ticker}: strike and price must be above zero")
    if c.premium < 0:
        raise PlannerError(f"{c.ticker}: premium cannot be negative")
    if c.iv is not None and c.iv < 0:
        raise PlannerError(f"{c.ticker}: IV cannot be negative")
    dte = days_to_expiry(c.expiry, today)
    if c.right == "P":
        collateral = c.strike * CONTRACT_SIZE
        note = ""
        cushion = (c.price - c.strike) / c.price
        break_even = c.strike - c.premium
    else:
        if c.cost_basis is not None and c.cost_basis > 0:
            basis = c.cost_basis
            note = ""
        else:
            basis = c.price
            note = ("no cost basis typed" if c.cost_basis is None else f"cost basis {c.cost_basis:g} typed") + \
                   ", so today's price stands in for it"
        collateral = basis * CONTRACT_SIZE
        cushion = (c.strike - c.price) / c.price
        break_even = basis - c.premium
    premium_dollars = c.premium * CONTRACT_SIZE
    ret = premium_dollars / collateral
    annualized = ret * 365 / dte
    sigma = odds = None
    source = "none"
    if c.iv is not None and c.iv > 0:
        iv = c.iv / 100
        sigma = expected_move(c.price, iv, dte)
        odds = prob_itm(c.price, c.strike, iv, dte, rate_pct / 100, c.right)
        source = "iv"
    elif c.delta_typed is not None:
        odds = min(1.0, abs(c.delta_typed))
        source = "delta"
    return Evaluation(c, dte, collateral, note, premium_dollars, ret, annualized,
                      premium_dollars / dte, cushion, break_even, sigma, odds, source)


@dataclass(frozen=True)
class Rules:
    """Your thresholds. Every flag sentence quotes the one that fired."""
    max_dte: int = DEFAULT_MAX_DTE
    max_odds_pct: float = DEFAULT_MAX_ODDS_PCT
    buying_power: float | None = None
    account: float | None = None
    max_pct: float = DEFAULT_MAX_PCT
    leveraged: frozenset[str] = frozenset()
    notes: dict[str, str] = field(default_factory=dict)


def _money(x: float) -> str:
    return f"${x:,.2f}"


def flags_for(e: Evaluation, rules: Rules) -> list[str]:
    """Plain sentences, each naming the rule and threshold that fired. No verdicts."""
    c = e.c
    out: list[str] = []
    if c.ticker in rules.leveraged:
        out.append(f"{c.ticker} is on your leveraged-ETF list (wheel_planner/leveraged_etfs.txt): daily-reset "
                   "funds can lose value while the index ends flat, so owning it after assignment is not the "
                   "plain wheel.")
    if e.dte > rules.max_dte:
        out.append(f"{c.ticker} expires in {e.dte} days, more than your {rules.max_dte}-day limit "
                   f"(--max-dte {rules.max_dte}).")
    if c.right == "C" and c.cost_basis is not None and c.strike < c.cost_basis:
        gap = (c.cost_basis - c.strike) * CONTRACT_SIZE
        locked = gap - e.premium_dollars
        head = f"{c.ticker} call strike {_money(c.strike)} is below your cost basis {_money(c.cost_basis)}: "
        if locked > 0:
            out.append(head + f"if called you lock in a loss of {_money(locked)} after keeping the "
                       f"{_money(e.premium_dollars)} premium.")
        else:
            out.append(head + f"the {_money(e.premium_dollars)} premium covers the {_money(gap)} gap, so being "
                       f"called away still nets +{_money(-locked)}, not a loss.")
    # buying power is checked on puts only: a covered call is written against shares you already own
    if c.right == "P" and rules.buying_power is not None and e.collateral > rules.buying_power:
        out.append(f"{c.ticker} needs {_money(e.collateral)} of collateral, more than your buying power of "
                   f"{_money(rules.buying_power)} (--buying-power {rules.buying_power:g}).")
    if rules.account is not None and rules.account > 0:
        pct = e.collateral / rules.account * 100
        if pct > rules.max_pct:
            out.append(f"{c.ticker} collateral {_money(e.collateral)} is {pct:.1f}% of your {_money(rules.account)} "
                       f"account, above your {rules.max_pct:g}% limit (--account {rules.account:g} "
                       f"--max-pct {rules.max_pct:g}).")
    if e.odds is not None and e.odds * 100 > rules.max_odds_pct:
        out.append(f"{c.ticker} rough odds of finishing in the money are {e.odds * 100:.1f}%, above your "
                   f"{rules.max_odds_pct:g}% limit (--max-odds {rules.max_odds_pct:g}).")
    if c.earnings is not None and c.earnings <= c.expiry:
        out.append(f"{c.ticker} expiry {c.expiry} crosses the earnings date you typed ({c.earnings}): "
                   "the IV-based odds and move do not include an earnings jump.")
    note = rules.notes.get(c.ticker)
    if note:
        out.append(f"{c.ticker}: your note says '{note}' (flags.txt).")
    return out


def sort_key(sort: str):
    if sort == "cushion":
        return lambda e: -e.cushion
    if sort == "odds":
        return lambda e: (e.odds is None, e.odds or 0.0)
    return lambda e: -e.annualized


def rank(evals: list[Evaluation], rules: Rules, sort: str = "annualized") -> list[Evaluation]:
    for i, e in enumerate(evals):
        e.order = i
        e.flags = flags_for(e, rules)
    return sorted(evals, key=sort_key(sort))


def income_goal_sentence(monthly_goal: float, evals: list[Evaluation]) -> str:
    best = max((e.annualized for e in evals), default=0.0)
    if best <= 0:
        return (f"To make {_money(monthly_goal)} a month you need a candidate with a positive annualized "
                "rate; none in this table has one.")
    needed = monthly_goal * 12 / best
    return (f"To make {_money(monthly_goal)} a month at the best annualized rate in this table ({best:.1%}) "
            f"you would need about ${needed:,.0f} of collateral working all month.")


# ---------------------------------------------------------------- roll math (short put)

@dataclass
class RollResult:
    net: float                  # per share: new credit - buyback
    net_contract: float
    days_added: int
    total_collected: float      # per share: old premium + new credit - buyback
    old_break_even: float
    new_break_even: float
    new_collateral: float
    annualized: float           # net / new strike x 365 / days added
    new_dte: int
    new_odds: float | None
    new_sigma: float | None
    verdict: str


VERDICT_CREDIT = "This roll pays you for the extra time (net credit > 0 and break-even not worse)."
VERDICT_DEBIT = "You are paying to delay, not to improve (net debit)."
VERDICT_WORSE = "Net credit but break-even got worse: only if you want to keep the shares."
VERDICT_EVEN = "This roll is even (no net credit and no debit): it only moves the date."


def roll(old_strike: float, old_expiry: date, old_premium: float, buyback: float,
         new_strike: float, new_expiry: date, new_credit: float,
         today: date, price: float | None = None, iv_pct: float | None = None,
         rate_pct: float = DEFAULT_RATE_PCT) -> RollResult:
    if min(old_strike, new_strike) <= 0:
        raise PlannerError("strikes must be above zero")
    if min(old_premium, buyback, new_credit) < 0:
        raise PlannerError("premium received, buyback and credit cannot be negative")
    net = new_credit - buyback
    total = old_premium + new_credit - buyback
    old_be = old_strike - old_premium
    new_be = new_strike - total
    days_added = (new_expiry - old_expiry).days
    if days_added <= 0:
        raise PlannerError(f"new expiry {new_expiry} must be after the old expiry {old_expiry} (no days added)")
    new_dte = days_to_expiry(new_expiry, today)
    annualized = net / new_strike * 365 / days_added
    odds = sigma = None
    if price and iv_pct:
        odds = prob_itm(price, new_strike, iv_pct / 100, new_dte, rate_pct / 100, "P")
        sigma = expected_move(price, iv_pct / 100, new_dte)
    if net > 0 and new_be <= old_be + 1e-9:
        verdict = VERDICT_CREDIT
    elif net > 0:
        verdict = VERDICT_WORSE
    elif net < 0:
        verdict = VERDICT_DEBIT
    else:
        verdict = VERDICT_EVEN
    return RollResult(net, net * CONTRACT_SIZE, days_added, total, old_be, new_be,
                      new_strike * CONTRACT_SIZE, annualized, new_dte, odds, sigma, verdict)


# ---------------------------------------------------------------- assignment what-if

@dataclass
class WhatIf:
    shares: int
    cost: float                 # strike x shares
    premium_kept: float
    basis_per_share: float      # strike - put credits per share
    call_premium: float | None
    call_return: float | None   # call premium / basis
    if_called: float | None     # (call strike - basis + call premium) x shares
    locked_loss: float | None   # set when the call strike is below the basis: gap to the basis minus the call
                                # premium; <= 0 means the premium covers the gap (called away is a net gain)


def assignment_whatif(strike: float, put_credits: float, contracts: int = 1,
                      call_strike: float | None = None, call_premium: float | None = None) -> WhatIf:
    if strike <= 0 or contracts <= 0:
        raise PlannerError("strike and contracts must be above zero")
    shares = contracts * CONTRACT_SIZE
    basis = strike - put_credits
    w = WhatIf(shares, strike * shares, put_credits * shares, basis, None, None, None, None)
    if call_strike and call_premium is not None:
        w.call_premium = call_premium * shares
        w.call_return = call_premium / basis if basis > 0 else None
        w.if_called = (call_strike - basis + call_premium) * shares
        if call_strike < basis:
            w.locked_loss = (basis - call_strike) * shares - w.call_premium
    return w
