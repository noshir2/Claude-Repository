"""Pure wiring math. No I/O. Every function here has a twin in the JavaScript inside
frc_shop_card.html, and tests/test_frc_shop_card.py checks that the two agree."""
import math

# Annealed copper resistivity at 20 C, ohm-metre (Wikipedia 'American wire gauge'; PowerStream).
RHO_COPPER_OHM_M = 1.724e-8
M_PER_FT = 0.3048
NOMINAL_V = 12.0          # FRC battery nominal voltage (2026 Game Manual R601)
DEFAULT_OPEN_V = 12.6     # a rested, fully charged lead-acid battery reads about 12.6-12.65 V
AWG_MIN, AWG_MAX = 6, 24  # the range the card covers


def check_awg(awg) -> int:
    if isinstance(awg, bool) or not math.isfinite(awg) or awg != int(awg) or not AWG_MIN <= int(awg) <= AWG_MAX:
        raise ValueError(f"AWG must be a whole number from {AWG_MIN} to {AWG_MAX}, got {awg}")
    return int(awg)


def positive(name: str, x: float) -> float:
    if not math.isfinite(x):
        raise ValueError(f"{name} must be a finite number, got {x}")
    if not x > 0:
        raise ValueError(f"{name} must be greater than zero, got {x}")
    return float(x)


def not_negative(name: str, x: float) -> float:
    if not math.isfinite(x):
        raise ValueError(f"{name} must be a finite number, got {x}")
    if x < 0:
        raise ValueError(f"{name} cannot be negative, got {x}")
    return float(x)


# --- AWG (American Wire Gauge) from the defining formula ---------------------------------
def awg_diameter_mm(awg: int) -> float:
    """d(mm) = 0.127 x 92^((36 - n) / 39)."""
    return 0.127 * 92 ** ((36 - awg) / 39)


def awg_area_mm2(awg: int) -> float:
    d = awg_diameter_mm(awg)
    return math.pi * (d / 2) ** 2


def awg_ohm_per_m(awg: int) -> float:
    """Solid annealed copper at 20 C. Stranded wire reads a few percent higher."""
    return RHO_COPPER_OHM_M / (awg_area_mm2(awg) * 1e-6)


def awg_mohm_per_ft(awg: int) -> float:
    return awg_ohm_per_m(awg) * M_PER_FT * 1000


def awg_row(awg: int) -> dict:
    """One row of the reference table, rounded to 4 significant figures."""
    awg = check_awg(awg)
    return {
        "id": f"awg{awg}",
        "awg": awg,
        "diameter_mm": _sig(awg_diameter_mm(awg), 4),
        "area_mm2": _sig(awg_area_mm2(awg), 4),
        "mohm_per_ft": _sig(awg_mohm_per_ft(awg), 4),
        "ohm_per_1000ft": _sig(awg_mohm_per_ft(awg), 4),   # same digits: mohm/ft == ohm/1000 ft
        "ohm_per_km": _sig(awg_ohm_per_m(awg) * 1000, 4),
    }


def awg_rows(lo: int = AWG_MIN, hi: int = AWG_MAX) -> list[dict]:
    return [awg_row(n) for n in range(lo, hi + 1)]


def _sig(x: float, n: int) -> float:
    if x == 0:
        return 0.0
    return round(x, n - 1 - int(math.floor(math.log10(abs(x)))))


# --- the four calculators -------------------------------------------------------------------
def vdrop(awg: int, amps: float, feet: float) -> dict:
    """Voltage drop over a one-way run of `feet` (so 2 x feet of wire carries the current)."""
    awg = check_awg(awg)
    amps, feet = positive("amps", amps), positive("feet", feet)
    round_trip_ft = 2 * feet
    ohms = awg_ohm_per_m(awg) * M_PER_FT * round_trip_ft
    volts = amps * ohms
    return {"awg": awg, "amps": amps, "feet": feet, "round_trip_ft": round_trip_ft,
            "ohms": ohms, "mohm": ohms * 1000, "volts": volts,
            "pct": volts / NOMINAL_V * 100, "watts": amps * amps * ohms}


def brownout(battery_mohm: float, path_mohm: float, amps: float | None = None,
             threshold: float | None = None, open_v: float = DEFAULT_OPEN_V) -> dict:
    """Bus voltage under load (forward) and/or the current that reaches a threshold (inverse)."""
    battery_mohm, path_mohm = not_negative("battery mohm", battery_mohm), not_negative("path mohm", path_mohm)
    total_mohm = battery_mohm + path_mohm
    positive("total resistance", total_mohm)
    open_v = positive("open-circuit volts", open_v)
    out = {"battery_mohm": battery_mohm, "path_mohm": path_mohm, "total_mohm": total_mohm, "open_v": open_v}
    if amps is not None:
        amps = not_negative("amps", amps)
        out["amps"] = amps
        out["bus_v"] = open_v - amps * total_mohm / 1000
    if threshold is not None:
        threshold = positive("threshold volts", threshold)
        if threshold >= open_v:
            raise ValueError(f"threshold {threshold} V must be below the open-circuit {open_v} V")
        out["threshold"] = threshold
        out["amps_at_threshold"] = (open_v - threshold) / (total_mohm / 1000)
    if amps is None and threshold is None:
        raise ValueError("give amps (bus voltage) and/or a threshold (current that reaches it)")
    return out


def battery_r(open_v: float, loaded_v: float, amps: float) -> dict:
    """Internal resistance from the sag under a known load: R = (open - loaded) / amps."""
    open_v, amps = positive("open-circuit volts", open_v), positive("amps", amps)
    loaded_v = positive("loaded volts", loaded_v)
    if loaded_v > open_v:
        raise ValueError(f"loaded voltage {loaded_v} V is above open-circuit {open_v} V; swap them?")
    ohms = (open_v - loaded_v) / amps
    return {"open_v": open_v, "loaded_v": loaded_v, "amps": amps, "ohms": ohms, "mohm": ohms * 1000}


def short_circuit(battery_mohm: float, path_mohm: float, open_v: float = DEFAULT_OPEN_V) -> dict:
    """Bolted fault: I = V / (R_battery + R_path); the battery heats at I^2 x R_battery."""
    battery_mohm, path_mohm = positive("battery mohm", battery_mohm), not_negative("path mohm", path_mohm)
    open_v = positive("open-circuit volts", open_v)
    total_mohm = battery_mohm + path_mohm
    amps = open_v / (total_mohm / 1000)
    return {"battery_mohm": battery_mohm, "path_mohm": path_mohm, "total_mohm": total_mohm, "open_v": open_v,
            "amps": amps, "battery_w": amps * amps * battery_mohm / 1000, "total_w": open_v * amps}


def ohms_law(volts: float | None = None, amps: float | None = None, ohms: float | None = None) -> dict:
    """Give any two of V, I, R; get the third and the power."""
    given = [x is not None for x in (volts, amps, ohms)]
    if sum(given) != 2:
        raise ValueError("give exactly two of volts, amps, ohms")
    if volts is None:
        volts = not_negative("amps", amps) * not_negative("ohms", ohms)
    elif amps is None:
        amps = not_negative("volts", volts) / positive("ohms", ohms)
    else:
        ohms = not_negative("volts", volts) / positive("amps", amps)
    return {"volts": volts, "amps": amps, "ohms": ohms, "watts": volts * amps}


def i2t(amps: float, seconds: float) -> dict:
    """I^2 t, the number breaker let-through curves are drawn in. No trip curves here."""
    amps, seconds = not_negative("amps", amps), not_negative("seconds", seconds)
    return {"amps": amps, "seconds": seconds, "i2t": amps * amps * seconds}


# --- rule-table lookup ------------------------------------------------------------------------
def gauge_for(rule_table: list[dict], amps: float, protection: str = "breaker") -> dict | None:
    """Smallest '<= X A' bucket of the given protection type that contains `amps`.
    A 'breaker' question also reads the 'main' row (the 120 A main breaker is a breaker).
    Returns the row, or None when the rating is outside the table (see the manual).
    Limits typed as text ("31") are read as numbers, like the page does; rows whose limits
    are not numbers at all are skipped (the checker reports them)."""
    amps = positive("amps", amps)
    if amps < 0.01:
        raise ValueError(f"a rating of {amps} A is below 0.01 A, not a breaker or fuse rating; check the number")
    best, best_hi = None, None
    for row in rule_table:
        kinds = ("breaker", "main") if protection == "breaker" else (protection,)
        if not isinstance(row, dict) or row.get("protection") not in kinds:
            continue
        try:
            lo, hi = float(row.get("amps_min")), float(row.get("amps_max"))
        except (TypeError, ValueError):
            continue
        if not (lo <= amps <= hi):
            continue
        if best is None or hi < best_hi:
            best, best_hi = row, hi
    return best
