import argparse
import sys
from pathlib import Path

from . import calc, card, report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="frc_shop_card",
                                description="Wiring calculators and the checker for frc_shop_card.html.")
    p.add_argument("--html", default=str(card.HTML_PATH),
                   help="the card file to read tables from (default: the one next to this package)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="confirm every row has a source, every card a week, and the calculators agree")

    s = sub.add_parser("vdrop", help="voltage drop over a one-way run")
    s.add_argument("--awg", type=int, required=True, help="wire gauge, 6 to 24")
    s.add_argument("--amps", type=float, required=True)
    s.add_argument("--feet", type=float, required=True, help="one-way length; the tool doubles it")

    s = sub.add_parser("brownout", help="bus voltage under load, and the current that reaches a threshold")
    s.add_argument("--battery-mohm", type=float, required=True)
    s.add_argument("--path-mohm", type=float, required=True, help="SB50 + lugs + cable, milliohm")
    s.add_argument("--amps", type=float, help="load current; prints the bus voltage")
    s.add_argument("--threshold", type=float, help="volts; prints the current that pulls the bus down to it")
    s.add_argument("--open", type=float, default=calc.DEFAULT_OPEN_V, help="open-circuit volts (default 12.6)")

    s = sub.add_parser("battery-r", help="internal resistance from the sag under a known load")
    s.add_argument("--open", type=float, required=True, help="open-circuit volts")
    s.add_argument("--loaded", type=float, required=True, help="volts under the load")
    s.add_argument("--amps", type=float, required=True)

    s = sub.add_parser("short", help="bolted-fault current and the heat in the battery")
    s.add_argument("--battery-mohm", type=float, required=True)
    s.add_argument("--path-mohm", type=float, required=True)
    s.add_argument("--open", type=float, default=calc.DEFAULT_OPEN_V)

    s = sub.add_parser("ohm", help="Ohm's law: give two of --volts --amps --ohms")
    s.add_argument("--volts", type=float)
    s.add_argument("--amps", type=float)
    s.add_argument("--ohms", type=float)

    s = sub.add_parser("i2t", help="I^2 t for a current held for some seconds")
    s.add_argument("--amps", type=float, required=True)
    s.add_argument("--seconds", type=float, required=True)

    s = sub.add_parser("gauge", help="minimum wire gauge for a breaker or fuse, from the rule table")
    s.add_argument("--breaker", type=float, help="breaker rating in amps (120 reads the main-breaker row)")
    s.add_argument("--fuse", type=float, help="fuse rating in amps")

    sub.add_parser("awg-table", help="copper resistance per foot for AWG 6-24, from the formula")
    sub.add_parser("regen-awg", help="rewrite the awg_table rows inside the HTML from the formula")

    s = sub.add_parser("warmup", help="the same 5-question weekly warm-up the Print tab makes")
    s.add_argument("--week", type=int, required=True, help="0 to 10")
    s.add_argument("--seed", type=int, default=1, help="any whole number; same seed = same questions")

    args = p.parse_args(argv)
    try:
        return run(args)
    except (card.CardDataError, OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 1


def run(args) -> int:
    if args.cmd == "check":
        problems, counts = card.check_card(card.load_card_data(Path(args.html)))
        print(report.check_text(problems, counts))
        return 1 if problems else 0
    if args.cmd == "vdrop":
        print(report.vdrop_sentence(calc.vdrop(args.awg, args.amps, args.feet)))
    elif args.cmd == "brownout":
        r = calc.brownout(args.battery_mohm, args.path_mohm, args.amps, args.threshold, args.open)
        print("\n".join(report.brownout_sentences(r)))
    elif args.cmd == "battery-r":
        print(report.battery_r_sentence(calc.battery_r(args.open, args.loaded, args.amps)))
    elif args.cmd == "short":
        print(report.short_sentence(calc.short_circuit(args.battery_mohm, args.path_mohm, args.open)))
    elif args.cmd == "ohm":
        print(report.ohm_sentence(calc.ohms_law(args.volts, args.amps, args.ohms)))
    elif args.cmd == "i2t":
        print(report.i2t_sentence(calc.i2t(args.amps, args.seconds)))
    elif args.cmd == "gauge":
        if (args.breaker is None) == (args.fuse is None):
            raise ValueError("give --breaker AMPS or --fuse AMPS (one of them)")
        rule_table = card.load_card_data(Path(args.html))["rule_table"]
        kind = "breaker" if args.breaker is not None else "fuse"
        amps = args.breaker if kind == "breaker" else args.fuse
        print(report.gauge_sentence(amps, kind, calc.gauge_for(rule_table, amps, kind)))
    elif args.cmd == "awg-table":
        print(report.awg_table_text(calc.awg_rows()))
    elif args.cmd == "regen-awg":
        path = Path(args.html)
        html = path.read_text(encoding="utf-8")
        data = card.load_card_data(path)
        src = next((r.get("source") for r in data["awg_table"] if r.get("source")),
                   "computed from the AWG formula and copper resistivity")
        old = {r.get("awg"): r for r in data["awg_table"] if isinstance(r, dict)}
        # keep any extra columns he added (ampacity rules of thumb, notes); refresh the physics
        data["awg_table"] = [dict(old.get(r["awg"], {}), **r, source=src, tag="physics") for r in calc.awg_rows()]
        path.write_text(card.replace_block(html, data), encoding="utf-8", newline="\n")
        print(f"awg_table rewritten from the formula ({len(data['awg_table'])} rows) in {path}")
    elif args.cmd == "warmup":
        print(report.warmup_text(card.warmup(card.load_card_data(Path(args.html)), args.week, args.seed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
