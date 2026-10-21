"""Read candidates from a CSV, from --candidate one-liners, plus flags.txt and leveraged_etfs.txt."""
import csv
from datetime import date, datetime
from pathlib import Path

from .planner import Candidate, PlannerError

REQUIRED = ["ticker", "type", "strike", "expiry", "premium", "price", "iv", "cost_basis", "note"]
OPTIONAL = ["earnings", "delta"]
HERE = Path(__file__).resolve().parent
LEVERAGED_FILE = HERE / "leveraged_etfs.txt"


def _right(text: str, where: str) -> str:
    t = text.strip().lower()
    if t in ("p", "put"):
        return "P"
    if t in ("c", "call"):
        return "C"
    raise PlannerError(f"{where}: type must be P, C, put or call, not {text!r}")


def _num(text: str | None, name: str, where: str, optional: bool = False) -> float | None:
    t = (text or "").strip().replace("$", "").replace(",", "").rstrip("%")
    if not t:
        if optional:
            return None
        raise PlannerError(f"{where}: {name} is empty")
    try:
        return float(t)
    except ValueError:
        raise PlannerError(f"{where}: {name} should be a number, not {text!r}") from None


DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y")   # what Excel on a US Windows machine writes back into a date cell


def _date(text: str | None, name: str, where: str, optional: bool = False) -> date | None:
    t = (text or "").strip()
    if not t:
        if optional:
            return None
        raise PlannerError(f"{where}: {name} is empty")
    try:
        return date.fromisoformat(t)
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    raise PlannerError(f"{where}: {name} must be YYYY-MM-DD (or MM/DD/YYYY as Excel saves it), not {text!r}")


def _build(fields: dict[str, str | None], where: str) -> Candidate:
    ticker = (fields.get("ticker") or "").strip().upper()
    if not ticker:
        raise PlannerError(f"{where}: ticker is empty")
    return Candidate(
        ticker=ticker,
        right=_right(fields.get("type") or "", where),
        strike=_num(fields.get("strike"), "strike", where),
        expiry=_date(fields.get("expiry"), "expiry", where),
        premium=_num(fields.get("premium"), "premium", where),
        price=_num(fields.get("price"), "price", where),
        iv=_num(fields.get("iv"), "iv", where, optional=True),
        cost_basis=_num(fields.get("cost_basis"), "cost_basis", where, optional=True),
        note=(fields.get("note") or "").strip(),
        earnings=_date(fields.get("earnings"), "earnings", where, optional=True),
        delta_typed=_num(fields.get("delta"), "delta", where, optional=True),
    )


def parse_one_liner(text: str) -> Candidate:
    """ticker,type,strike,expiry,premium,price[,iv[,cost_basis]]"""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 6 or len(parts) > 8:
        raise PlannerError(f"--candidate needs ticker,type,strike,expiry,premium,price[,iv[,cost_basis]] "
                           f"(6 to 8 values); got {len(parts)} in {text!r}")
    names = ["ticker", "type", "strike", "expiry", "premium", "price", "iv", "cost_basis"]
    return _build(dict(zip(names, parts)), f"--candidate {text!r}")


def load_candidates(path: str | Path) -> tuple[list[Candidate], bool]:
    """Return (candidates, has_earnings_column). Lines starting with # are ignored."""
    path = Path(path)
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [l for l in f if l.strip() and not l.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    found = [h.strip() for h in (reader.fieldnames or [])]
    lower = {h.lower(): h for h in found}
    missing = [n for n in REQUIRED if n not in lower]
    if missing:
        raise PlannerError(f"{path.name}: missing column(s) {', '.join(missing)}. "
                           f"Columns found: {', '.join(found) or '(none)'}. "
                           f"The header must be: {','.join(REQUIRED)}")
    out = []
    for line_no, row in enumerate(reader, start=2):
        fields = {n: row.get(lower[n]) for n in REQUIRED + OPTIONAL if n in lower}
        if not any((v or "").strip() for v in fields.values()):
            continue
        out.append(_build(fields, f"{path.name} line {line_no}"))
    return out, "earnings" in lower


def load_notes(path: str | Path) -> dict[str, str]:
    """flags.txt: one line per ticker, `TICKER: note`; lines starting with # are comments (a # inside a
    note is kept). Missing file -> no notes."""
    path = Path(path)
    if not path.exists():
        return {}
    notes = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        ticker, note = line.split(":", 1)
        if ticker.strip() and note.strip():
            notes[ticker.strip().upper()] = note.strip()
    return notes


def load_leveraged(path: str | Path = LEVERAGED_FILE) -> frozenset[str]:
    """leveraged_etfs.txt: one ticker per line, # comments."""
    path = Path(path)
    if not path.exists():
        return frozenset()
    tickers = (l.split("#")[0].strip().upper() for l in path.read_text(encoding="utf-8").splitlines())
    return frozenset(t for t in tickers if t)
