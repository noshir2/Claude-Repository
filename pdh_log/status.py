"""The rule math: renewal period, daily cap, totals, core hours, carry-over, record check."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .log import Entry
from .rules import get_rules


@dataclass
class Counted:
    """One log row plus the hours that actually count after the daily cap."""
    entry: Entry
    counted: float


@dataclass
class Carryover:
    hours: float
    prev_start: date
    prev_end: date
    window_start: date
    window_end: date
    prev_total: float        # hours counted in the previous period (after the daily cap)
    carried_in: float        # hours that period itself received from the one before it
    surplus: float           # hours beyond that period's own requirement (counted + carried in - total)
    window_elective: float   # elective hours earned inside the window
    cap: int
    form: str

    def sentence(self) -> str:
        return (f"Carry-over from the previous period ({self.prev_start} to {self.prev_end}): {self.hours:g} PDH. "
                f"Only hours earned {self.window_start} to {self.window_end} count, only elective hours "
                f"(statutes/rules, ethics and harassment hours never carry), only hours beyond that period's own "
                f"total requirement, and at most {self.cap}. "
                f"(That period had {self.prev_total:g} counted hours"
                + (f" plus {self.carried_in:g} carried into it" if self.carried_in else "")
                + f", so {self.surplus:g} were spare; {self.window_elective:g} elective hours fell in the window.) "
                f"Document carried hours on {self.form} and keep it with your records.")


@dataclass
class Status:
    today: date
    state: str
    rules: dict
    start: date
    end: date
    rows: list[Counted]                        # rows in the period, in file order
    by_category: dict[str, float]              # counted hours per category in the period
    core: dict[str, tuple[float, float, bool]]  # key -> (have, need, met)
    elective: float
    earned: float                              # counted hours in the period (after the daily cap)
    carryover: Carryover
    total: float                               # earned + carry-over
    flagged_days: list[tuple[date, float, float]]  # (day, raw hours, counted hours)
    missing_certificate: list[Entry]
    certificate_not_found: list[tuple[Entry, Path]]
    warnings: list[str] = field(default_factory=list)
    all_entries: list[Entry] = field(default_factory=list)

    @property
    def days_left(self) -> int:
        return (self.end - self.today).days

    @property
    def short_by(self) -> float:
        return max(0.0, self.rules["total_hours"] - self.total)

    @property
    def missing(self) -> list[str]:
        """Plain-English list of what is still missing, in the order the verdict prints it."""
        out = []
        if self.short_by > 0:
            out.append(f"{self.short_by:g} more hour{'s' if self.short_by != 1 else ''}")
        labels = {"statutes_rules": "the Illinois statutes/rules hour", "ethics": "the ethics hour",
                  "harassment": "the harassment hour"}
        for key, (have, need, met) in self.core.items():
            if not met:
                out.append(labels.get(key, f"the {key} hour"))
        return out

    def next_period_carryover(self) -> Carryover:
        """What this period could pass on to the next one, if nothing else changes."""
        return carryover_for(self.all_entries, self.start, self.end, self.rules)


def renewal_period(today: date, rules: dict) -> tuple[date, date]:
    """The period that contains `today`: 24 months ending on the next expiration date on or after today."""
    m, d = rules["period_end_month"], rules["period_end_day"]
    year = today.year
    if date(year, m, d) < today:
        year += 1
    want_odd = rules["period_end_year_parity"] == "odd"
    while (year % 2 == 1) != want_odd:
        year += 1
    return period_ending(year, rules)


def period_ending(year: int, rules: dict) -> tuple[date, date]:
    m, d = rules["period_end_month"], rules["period_end_day"]
    want_odd = rules["period_end_year_parity"] == "odd"
    if (year % 2 == 1) != want_odd:
        raise ValueError(f"no renewal period ends in {year}: licenses expire in "
                         f"{rules['period_end_year_parity']}-numbered years")
    end = date(year, m, d)
    start = date(year - rules["period_months"] // 12, m, d) + timedelta(days=1)
    return start, end


def apply_daily_cap(entries: list[Entry], cap: float) -> tuple[list[Counted], list[tuple[date, float, float]]]:
    """Trim any calendar day above the cap. Excess comes off elective rows first, last row in the file first."""
    by_day: dict[date, list[Entry]] = {}
    for e in entries:
        by_day.setdefault(e.date, []).append(e)
    counted = {id(e): e.hours for e in entries}
    flagged = []
    for day, rows in sorted(by_day.items()):
        raw = sum(e.hours for e in rows)
        if raw <= cap:
            continue
        excess = raw - cap
        # trim order: elective rows (latest in file first), then core rows (latest first)
        for e in sorted(rows, key=lambda e: (e.category != "elective", -e.line)):
            if excess <= 0:
                break
            cut = min(excess, counted[id(e)])
            counted[id(e)] -= cut
            excess -= cut
        flagged.append((day, raw, cap))
    return [Counted(e, counted[id(e)]) for e in entries], flagged


def previous_period(start: date, rules: dict) -> tuple[date, date]:
    """The period just before the one that starts on `start`."""
    prev_end = start - timedelta(days=1)
    prev_start = date(prev_end.year - rules["period_months"] // 12, prev_end.month, prev_end.day) + timedelta(days=1)
    return prev_start, prev_end


def carryover_for(entries: list[Entry], prev_start: date, prev_end: date, rules: dict) -> Carryover:
    """Hours a period ending on prev_end can pass to the next period.

    Hours carried INTO that period are treated as used first, so they chain: a period that received 10
    and then earned exactly 30 of its own has 10 spare (1380.325(a)(8) 'not used for the current period';
    IDFPR decides what it accepts). The chain walks back one period at a time until the log has no
    rows before the period in question."""
    prev = [e for e in entries if prev_start <= e.date <= prev_end]
    carried_in = 0.0
    if any(e.date < prev_start for e in entries):
        carried_in = carryover_for(entries, *previous_period(prev_start, rules), rules).hours
    counted, _ = apply_daily_cap(prev, rules["daily_cap"])
    window_start = date(prev_end.year, rules["carryover_window_start_month"], rules["carryover_window_start_day"])
    prev_total = sum(c.counted for c in counted)
    surplus = max(0.0, prev_total + carried_in - rules["total_hours"])
    window_elective = sum(c.counted for c in counted
                          if c.entry.category == "elective" and window_start <= c.entry.date <= prev_end)
    hours = min(float(rules["carryover_max"]), surplus, window_elective)
    return Carryover(hours, prev_start, prev_end, window_start, prev_end, prev_total, carried_in, surplus,
                     window_elective, rules["carryover_max"], rules["carryover_form"])


def compute_status(entries: list[Entry], today: date, log_path: Path | None = None, state: str = "IL",
                   period_year: int | None = None) -> Status:
    rules = get_rules(state)
    start, end = period_ending(period_year, rules) if period_year else renewal_period(today, rules)
    in_period = [e for e in entries if start <= e.date <= end]
    rows, flagged = apply_daily_cap(in_period, rules["daily_cap"])

    by_category = {k: 0.0 for k in ("elective", *rules["core"])}
    for c in rows:
        by_category[c.entry.category] = by_category.get(c.entry.category, 0.0) + c.counted
    core = {key: (by_category.get(key, 0.0), float(need), by_category.get(key, 0.0) >= need)
            for key, (need, _label, _cite) in rules["core"].items()}
    earned = sum(c.counted for c in rows)

    carry = carryover_for(entries, *previous_period(start, rules), rules)

    base = Path(log_path).parent if log_path else Path(".")
    missing = [c.entry for c in rows if not c.entry.certificate_file]
    not_found = []
    for c in rows:
        if c.entry.certificate_file:
            p = base / c.entry.certificate_file
            if not p.exists():
                not_found.append((c.entry, p))

    warnings = []
    for e in entries:
        if e.date > today:
            warnings.append(f"line {e.line}: date {e.date} is after today ({today}); typo?")
        # 0.25 is a real credit (the IDFPR newsletter quiz, see rules.py activity_credits), so only
        # finer fractions look like typos.
        if (e.hours * 4) != int(e.hours * 4):
            warnings.append(f"line {e.line}: {e.hours:g} hours is not a multiple of 0.25; "
                            "one PDH is at least 50 minutes (the IDFPR newsletter quiz is 0.25), "
                            "so check the certificate")

    return Status(today, state.upper(), rules, start, end, rows, by_category, core, by_category["elective"],
                  earned, carry, earned + carry.hours, flagged, missing, not_found, warnings, list(entries))
