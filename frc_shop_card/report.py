"""Plain-English sentences for every calculator, plus the text tables the CLI prints.
The JavaScript in frc_shop_card.html builds the same sentences character for character, so a
number typed on the page and the same number typed at the command line read the same."""
import math


def num(x: float, d: int = 0) -> str:
    """Fixed decimals, half rounds up, thousands commas: num(1234.5, 1) -> '1,234.5'.
    Rounds via floor(x * 10^d + 0.5) so Python and JavaScript land on identical digits."""
    if not math.isfinite(x):
        raise ValueError("the result is too large to print; check the inputs")
    p = 10 ** d
    v = math.floor(abs(x) * p + 0.5) / p
    s = f"{v:.{d}f}"
    whole, _, frac = s.partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    out = ",".join(groups) + ("." + frac if frac else "")
    return ("-" if x < 0 and v != 0 else "") + out


def g(x: float) -> str:
    """Up to 2 decimals, trailing zeros dropped: g(120.0) -> '120', g(7.5) -> '7.5'."""
    s = num(x, 2)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def vdrop_sentence(r: dict) -> str:
    return (f"At {g(r['amps'])} A through {g(r['feet'])} ft of {r['awg']} AWG "
            f"({g(r['round_trip_ft'])} ft round trip, {num(r['mohm'], 1)} mohm) you lose "
            f"{num(r['volts'], 2)} V, about {num(r['pct'], 1)}% of 12 V; the wire dissipates "
            f"{num(r['watts'])} W.")


def brownout_sentences(r: dict) -> list[str]:
    out = []
    if "bus_v" in r:
        out.append(f"A {g(r['battery_mohm'])} mohm battery plus {g(r['path_mohm'])} mohm of connectors "
                   f"and cable ({g(r['total_mohm'])} mohm total) at {g(r['amps'])} A: the "
                   f"{g(r['open_v'])} V battery sags to {num(r['bus_v'], 2)} V on the bus.")
    if "amps_at_threshold" in r:
        out.append(f"To pull that {g(r['open_v'])} V battery down to {g(r['threshold'])} V through "
                   f"{g(r['total_mohm'])} mohm takes about {num(r['amps_at_threshold'])} A.")
    return out


def battery_r_sentence(r: dict) -> str:
    return (f"Open-circuit {g(r['open_v'])} V, {g(r['loaded_v'])} V under {g(r['amps'])} A: internal "
            f"resistance about {num(r['mohm'], 1)} mohm (this includes whatever leads and connectors "
            f"sit between the meter and the battery plates).")


def short_sentence(r: dict) -> str:
    return (f"A bolted short across a {g(r['open_v'])} V battery with {g(r['battery_mohm'])} mohm inside "
            f"and {g(r['path_mohm'])} mohm of path ({g(r['total_mohm'])} mohm) drives about "
            f"{num(r['amps'])} A; the battery itself heats at about {num(r['battery_w'] / 1000, 1)} kW "
            f"and the whole loop at {num(r['total_w'] / 1000, 1)} kW.")


def ohm_sentence(r: dict) -> str:
    return (f"V = {g(r['volts'])} V, I = {g(r['amps'])} A, R = {g(r['ohms'])} ohm, "
            f"P = {g(r['watts'])} W.")


def i2t_sentence(r: dict) -> str:
    return (f"{g(r['amps'])} A for {g(r['seconds'])} s: I^2t = {num(r['i2t'])} A^2-s. Compare it with "
            f"your breaker's published curve; this card prints no trip curves.")


def gauge_sentence(amps: float, protection: str, row: dict | None) -> str:
    if row is None:
        return f"{g(amps)} A {protection}: not in the table, see the manual."
    tail = f"{row['source']}" + (f", season {row['season']}" if row.get("season") else "")
    what = "is the main breaker: battery to main breaker to PD input needs" if row.get("protection") == "main" else "needs"
    return (f"A {g(amps)} A {protection} {what} at least {row['min_awg']} AWG "
            f"({tail}; verify against the current season's manual).")


def awg_table_text(rows: list[dict]) -> str:
    out = ["Solid annealed copper at 20 C, from d(mm) = 0.127 x 92^((36-n)/39) and rho = 1.724e-8 ohm-m",
           "Stranded wire reads 2-5% higher; at 75 C copper reads about 22% higher.",
           f"{'AWG':>4} {'dia mm':>8} {'mm2':>7} {'mohm/ft':>9} {'ohm/1000ft':>11} {'ohm/km':>8}"]
    for r in rows:
        out.append(f"{r['awg']:>4} {r['diameter_mm']:>8.3f} {r['area_mm2']:>7.3f} {r['mohm_per_ft']:>9.4g} "
                   f"{r['ohm_per_1000ft']:>11.4g} {r['ohm_per_km']:>8.4g}")
    return "\n".join(out)


def check_text(problems: list[str], counts: dict) -> str:
    if not problems:
        return (f"card data OK: {counts['rows']} rows, {counts['cards']} cards "
                f"({counts['written']} written + {counts['generated']} generated from tables), all sourced")
    return "card data has problems:\n" + "\n".join(f"  - {p}" for p in problems)


def warmup_text(w: dict) -> str:
    out = [f"WEEKLY WARM-UP  week {w['week']}  seed {w['seed']}", "=" * 60]
    for i, c in enumerate(w["questions"], 1):
        out.append(f"{i}. (week {c['week']}) {c['front']}")
        out.append("")
    out += ["ANSWER KEY", "-" * 60]
    for i, c in enumerate(w["questions"], 1):
        out.append(f"{i}. {c['back']}")
        out.append(f"   source: {c['source']}")
    out += ["", "EXIT TICKET (each student, before leaving)", "-" * 60,
            "1. One safety rule from today:",
            "2. The SL connector current limit, and the wire gauge it takes:",
            "3. One thing that is still fuzzy:"]
    return "\n".join(out)
