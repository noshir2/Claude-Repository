import argparse
import sys
from datetime import date
from pathlib import Path

from .log import Entry, LogFormatError, append_entry, load_log, normalize_category, parse_date, parse_hours
from .report import html_report, rules_text, text_report
from .rules import UnknownStateError, get_rules
from .status import compute_status


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pdh_log",
                                description="Do I have the continuing-education hours my PE renewal needs?")
    p.add_argument("--state", default="IL", help="which state's rules to use (only IL is shipped)")
    sub = p.add_subparsers(dest="command", required=True)

    st = sub.add_parser("status", help="hours this period, what is missing, days left, record check")
    st.add_argument("--log", default="data/pdh_log.csv", help="the log CSV (default data/pdh_log.csv)")
    st.add_argument("--today", help="treat this date (YYYY-MM-DD) as today; for testing")
    st.add_argument("--html", default="pdh_report.html", help="where to write the HTML report ('' to skip)")
    st.add_argument("--period", type=int, metavar="YEAR",
                    help="report the period ending Nov 30 of this (odd) year instead of the current one")

    ad = sub.add_parser("add", help="append one row to the log (creates the file if needed)")
    ad.add_argument("--log", default="data/pdh_log.csv")
    ad.add_argument("--date", required=True, help="YYYY-MM-DD")
    ad.add_argument("--hours", required=True, help="PDH earned, e.g. 1 or 1.5")
    ad.add_argument("--title", required=True)
    ad.add_argument("--provider", required=True, help="sponsor name (put its address in --notes)")
    ad.add_argument("--category", required=True, help="elective, statutes_rules, ethics or harassment")
    ad.add_argument("--format", default="", help="webinar, in-person, college course, ...")
    ad.add_argument("--location", default="", help="online, or the city")
    ad.add_argument("--certificate", default="", help="certificate file, relative to the log's folder")
    ad.add_argument("--notes", default="")

    sub.add_parser("rules", help="print the rule table the tool uses, with citations")

    args = p.parse_args(argv)
    try:
        rules = get_rules(args.state)
        if args.command == "rules":
            print(rules_text(args.state, rules))
            return 0
        if args.command == "add":
            entry = Entry(parse_date(args.date), parse_hours(args.hours), args.title, args.provider,
                          normalize_category(args.category), args.format, args.location,
                          args.certificate, args.notes)
            append_entry(Path(args.log), entry)
            print(f"Saved to {args.log}:")
            print("  " + ",".join(entry.as_row()))
            if not entry.certificate_file:
                print("  (no certificate file given; add one later so the row passes the record check)")
            return 0
        today = date.fromisoformat(args.today) if args.today else date.today()
        entries = load_log(Path(args.log))
        status = compute_status(entries, today, Path(args.log), args.state, args.period)
    except (LogFormatError, UnknownStateError, OSError, ValueError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 1
    print(text_report(status))
    if args.html:
        Path(args.html).write_text(html_report(status), encoding="utf-8")
        print(f"\nPicture-friendly version saved to {args.html} (open it in your browser).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
