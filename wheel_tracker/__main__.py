import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from .analyze import analyze
from .parse import ExportFormatError, load_trades
from .report import html_report, text_report


def _read_assigned(path: Path) -> frozenset[str]:
    if not path.exists():
        return frozenset()
    lines = (l.split("#")[0].strip().upper() for l in path.read_text().splitlines())
    return frozenset(l for l in lines if l)


def _read_opening(path: Path):
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return [(r["ticker"].strip().upper(), float(r["shares"]), float(r["cost_per_share"]))
                for r in csv.DictReader(f)]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wheel_tracker",
                                description="Are your cash-secured puts and covered calls making money?")
    p.add_argument("files", nargs="+", help="Webull order-history CSV file(s)")
    p.add_argument("--assigned", default="data/assigned.txt", help="option symbols that were assigned")
    p.add_argument("--opening-shares", default="data/opening_shares.csv",
                   help="CSV (ticker,shares,cost_per_share) for shares bought before your export starts")
    p.add_argument("--price", action="append", default=[], metavar="TICKER=PRICE",
                   help="current share price, to value shares you still hold (repeatable)")
    p.add_argument("--html", default="wheel_report.html", help="where to write the HTML report ('' to skip)")
    p.add_argument("--today", help="treat this date (YYYY-MM-DD) as today; for testing")
    args = p.parse_args(argv)

    try:
        prices = {k.strip().upper(): float(v) for k, v in (x.split("=") for x in args.price)}
        trades, warnings = load_trades(args.files)
        today = date.fromisoformat(args.today) if args.today else date.today()
        result = analyze(trades, today, _read_assigned(Path(args.assigned)),
                         _read_opening(Path(args.opening_shares)), prices)
    except (ExportFormatError, OSError, ValueError, KeyError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 1
    result.warnings = warnings + result.warnings
    print(text_report(result))
    if args.html:
        Path(args.html).write_text(html_report(result), encoding="utf-8")
        print(f"\nPicture-friendly version saved to {args.html} (open it in your browser).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
