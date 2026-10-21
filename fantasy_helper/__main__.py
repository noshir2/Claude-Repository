import argparse
import sys
from pathlib import Path

from .helper import (ExportFormatError, best_lineup, load_context, opponent_line, trade_report, waiver_report,
                     base_report)
from .parse import parse_name_list
from .report import html_report, text_report


def _common(sp):
    sp.add_argument("--league", required=True, help="folder with roster.csv and league.txt (e.g. data/league1)")
    sp.add_argument("--proj", required=True, help="folder with this week's six FantasyPros projection CSVs")
    sp.add_argument("--close", type=float, default=1.5, metavar="PTS",
                    help="two choices this close in projected points are a 'close call' (default 1.5)")
    sp.add_argument("--html", default="fantasy_report.html", help="where to write the HTML report ('' to skip)")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fantasy_helper",
                                description="Who do I start, is this trade good for my starters, which pickup helps most?")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("lineup", help="best lineup, floor lineup, bench and close calls")
    _common(s)
    s.add_argument("--opponent-total", type=float, metavar="PTS",
                   help="your opponent's projected total; prints whether to lean floor or ceiling")

    s = sub.add_parser("trade", help="best-lineup points before and after a trade")
    _common(s)
    s.add_argument("--give", action="append", required=True, metavar='"Player"', help="player you give (repeatable)")
    s.add_argument("--get", action="append", required=True, metavar='"Player"', help="player you get (repeatable)")
    s.add_argument("--ros", help="folder with rest-of-season projection CSVs (same six files)")

    s = sub.add_parser("waiver", help="lineup gain from a pickup, or rank several candidates")
    _common(s)
    s.add_argument("--add", metavar='"Player"', help="free agent to add")
    s.add_argument("--drop", metavar='"Player"', help="roster player to drop (default: weakest bench player)")
    s.add_argument("--candidates", help="text file with one free-agent name per line, ranked by lineup gain")
    args = p.parse_args(argv)

    try:
        ctx = load_context(Path(args.league), Path(args.proj))
        if args.command == "lineup":
            rep = base_report(ctx, "lineup", args.close)
            if args.opponent_total is not None:
                ceiling = best_lineup(ctx.players, ctx.league.slots, "ceil", "proj")
                rep.ceiling_lineup = ceiling
                rep.opponent_line = opponent_line(rep.lineup, ceiling, rep.floor_lineup, args.opponent_total)
        elif args.command == "trade":
            ros_ctx = load_context(Path(args.league), Path(args.ros), "rest of season") if args.ros else None
            rep = trade_report(ctx, args.give, args.get, args.close, ros_ctx)
        else:
            if not args.add and not args.candidates:
                raise ExportFormatError("waiver needs --add \"Player\" and/or --candidates file.txt")
            cands = parse_name_list(Path(args.candidates)) if args.candidates else []
            rep = waiver_report(ctx, args.add, args.drop, cands, args.close)
    except (ExportFormatError, OSError, ValueError, KeyError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 1
    print(text_report(rep))
    if args.html:
        try:
            Path(args.html).write_text(html_report(rep), encoding="utf-8")
        except OSError as e:
            print(f"Problem: could not write {args.html}: {e}", file=sys.stderr)
            return 1
        print(f"\nPicture-friendly version saved to {args.html} (open it in your browser).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
