import argparse
import sys
from datetime import date
from pathlib import Path

from .candidates import LEVERAGED_FILE, _date, _num, load_candidates, load_leveraged, load_notes, parse_one_liner
from .expiry import check_expiry
from .planner import (DEFAULT_MAX_DTE, DEFAULT_MAX_ODDS_PCT, DEFAULT_MAX_PCT, DEFAULT_RATE_PCT, PlannerError,
                      Rules, evaluate, rank, roll)
from .report import html_compare, html_expiry, text_compare, text_expiry, text_roll


def _today(text: str | None) -> date:
    return _date(text, "date", "--today") if text else date.today()


def _parse_roll_leg(text: str, n: int, what: str) -> list:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != n:
        raise PlannerError(f"--{what} needs {n} values separated by commas, got {len(parts)}: {text!r}")
    return parts


def cmd_compare(args) -> int:
    cands, has_earnings = [], False
    if args.file:
        cands, has_earnings = load_candidates(args.file)
    cands += [parse_one_liner(t) for t in args.candidate]
    if not cands:
        raise PlannerError("nothing to compare: give a candidates CSV file and/or --candidate TICKER,P,strike,...")
    if args.monthly_goal is not None and args.monthly_goal <= 0:
        raise PlannerError(f"--monthly-goal must be above zero, not {args.monthly_goal:g}")
    today = _today(args.today)
    rules = Rules(max_dte=args.max_dte, max_odds_pct=args.max_odds, buying_power=args.buying_power,
                  account=args.account, max_pct=args.max_pct, leveraged=load_leveraged(args.leveraged),
                  notes=load_notes(args.flags))
    warnings = []
    for c in cands:
        if c.expiry <= today:
            warnings.append(f"{c.ticker}: expiry {c.expiry} is on or before today ({today}); treated as 1 day left.")
    evals = rank([evaluate(c, today, args.rate) for c in cands], rules, args.sort)
    print(text_compare(evals, rules, today, args.rate, args.monthly_goal, has_earnings, warnings))
    if args.html:
        Path(args.html).write_text(html_compare(evals, rules, today, args.rate, args.monthly_goal, has_earnings,
                                                warnings), encoding="utf-8")
        print(f"\nPicture-friendly version saved to {args.html} (open it in your browser).")
    return 0


def cmd_roll(args) -> int:
    os_, oe, op, bb = _parse_roll_leg(args.old, 4, "old")
    ns, ne, nc = _parse_roll_leg(args.new, 3, "new")
    today = _today(args.today)
    old = (_num(os_, "strike", "--old"), _date(oe, "expiry", "--old"), _num(op, "premium received", "--old"),
           _num(bb, "buyback", "--old"))
    new = (_num(ns, "strike", "--new"), _date(ne, "expiry", "--new"), _num(nc, "credit", "--new"))
    r = roll(*old, *new, today=today, price=args.price, iv_pct=args.iv, rate_pct=args.rate)
    warnings = []
    if new[1] <= today:
        warnings.append(f"new expiry {new[1]} is on or before today ({today}); treated as 1 day left for the odds "
                        "and the 1-sigma move.")
    print(text_roll(r, old, new, args.price, args.iv, today, args.rate, warnings))
    return 0


def cmd_expiry(args) -> int:
    prices = {}
    for item in args.price:
        if "=" not in item:
            raise PlannerError(f"--price needs TICKER=PRICE, got {item!r}")
        k, v = item.split("=", 1)
        ticker = k.strip().upper()
        prices[ticker] = _num(v, f"price for {ticker}", "--price")
    if args.cash is not None and args.cash < 0:
        raise PlannerError(f"--cash cannot be negative, not {args.cash:g}")
    x = check_expiry(args.files, _today(args.today), prices, args.cash)
    print(text_expiry(x))
    if args.html:
        Path(args.html).write_text(html_expiry(x), encoding="utf-8")
        print(f"\nPicture-friendly version saved to {args.html} (open it in your browser).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wheel_planner",
                                description="Before you sell or roll: is this put or call worth the cash it ties up, "
                                            "and what do your own rules say?")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--today", help="treat this date (YYYY-MM-DD) as today; for testing and reproducible samples")
        sp.add_argument("--rate", type=float, default=DEFAULT_RATE_PCT,
                        help=f"risk-free rate in percent for the rough odds (default {DEFAULT_RATE_PCT:g}, "
                             "about the 4-week T-bill)")

    c = sub.add_parser("compare", help="rank candidate puts and calls and run your rules over them")
    c.add_argument("file", nargs="?", help="candidates CSV (header: ticker,type,strike,expiry,premium,price,iv,cost_basis,note)")
    c.add_argument("--candidate", action="append", default=[], metavar="TICKER,P,strike,expiry,premium,price[,iv[,cost_basis]]",
                   help="one candidate typed inline (repeatable)")
    c.add_argument("--buying-power", type=float, help="flag any collateral above this many dollars")
    c.add_argument("--account", type=float, help="account value in dollars, used with --max-pct")
    c.add_argument("--max-pct", type=float, default=DEFAULT_MAX_PCT,
                   help=f"flag collateral above this percent of --account (default {DEFAULT_MAX_PCT:g})")
    c.add_argument("--max-odds", type=float, default=DEFAULT_MAX_ODDS_PCT,
                   help=f"flag rough odds of finishing in the money above this percent (default {DEFAULT_MAX_ODDS_PCT:g})")
    c.add_argument("--max-dte", type=int, default=DEFAULT_MAX_DTE,
                   help=f"flag expiries more than this many days out (default {DEFAULT_MAX_DTE})")
    c.add_argument("--monthly-goal", type=float, help="dollars per month; adds one sentence on collateral needed")
    c.add_argument("--sort", choices=["annualized", "cushion", "odds"], default="annualized")
    c.add_argument("--flags", default="data/flags.txt", help="your per-ticker notes file (TICKER: note)")
    c.add_argument("--leveraged", default=str(LEVERAGED_FILE), help="leveraged-ETF list, one ticker per line")
    c.add_argument("--html", default="wheel_planner_report.html", help="where to write the HTML report ('' to skip)")
    common(c)
    c.set_defaults(func=cmd_compare)

    r = sub.add_parser("roll", help="net credit, break-even and a stated-rule sentence for rolling a short put")
    r.add_argument("--old", required=True, metavar="strike,expiry,premium_received,buyback")
    r.add_argument("--new", required=True, metavar="strike,expiry,credit")
    r.add_argument("--price", type=float, help="current share price (needed for the rough odds)")
    r.add_argument("--iv", type=float, help="implied volatility of the new contract in percent")
    common(r)
    r.set_defaults(func=cmd_roll)

    e = sub.add_parser("expiry", help="open short puts/calls from a Webull export and the cash needed if all puts are assigned")
    e.add_argument("files", nargs="+", help="Webull order-history CSV file(s), the same ones wheel_tracker reads")
    e.add_argument("--price", action="append", default=[], metavar="TICKER=PRICE", help="current share price (repeatable)")
    e.add_argument("--cash", type=float, help="cash on hand in dollars")
    e.add_argument("--html", default="", help="optional HTML report path ('' = none)")
    e.add_argument("--today", help="treat this date (YYYY-MM-DD) as today")
    e.set_defaults(func=cmd_expiry)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (PlannerError, OSError, ValueError, KeyError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
