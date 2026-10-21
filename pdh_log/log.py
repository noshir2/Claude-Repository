"""Read and append the PDH log CSV. No rule logic here."""
import csv
import io
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HEADER = ["date", "hours", "title", "provider", "category", "format", "location", "certificate_file", "notes"]

CATEGORIES = ("elective", "statutes_rules", "ethics", "harassment")

# Plain words people type, mapped to the four category keys (matched after lower-casing and turning
# spaces, slashes, hyphens and '&' into underscores).
_ALIASES = {
    "elective": "elective", "general": "elective", "technical": "elective", "": "elective",
    "statutes_rules": "statutes_rules", "statutes": "statutes_rules", "rules": "statutes_rules",
    "statutes_and_rules": "statutes_rules", "statutes_rules_": "statutes_rules", "laws": "statutes_rules",
    "laws_rules": "statutes_rules", "laws_and_rules": "statutes_rules", "illinois_statutes_rules": "statutes_rules",
    "illinois_statutes_and_rules": "statutes_rules", "il_statutes_rules": "statutes_rules",
    "ethics": "ethics", "ethic": "ethics", "professional_conduct": "ethics", "conduct": "ethics",
    "professional_conduct_ethics": "ethics", "conduct_ethics": "ethics",
    "harassment": "harassment", "sexual_harassment": "harassment", "sexual_harassment_prevention": "harassment",
    "harassment_prevention": "harassment", "sh": "harassment", "shp": "harassment",
}


class LogFormatError(ValueError):
    pass


@dataclass
class Entry:
    date: date
    hours: float
    title: str
    provider: str
    category: str
    format: str = ""
    location: str = ""
    certificate_file: str = ""
    notes: str = ""
    line: int = 0  # line number in the CSV, for messages

    def as_row(self) -> list[str]:
        return [self.date.isoformat(), f"{self.hours:g}", self.title, self.provider, self.category,
                self.format, self.location, self.certificate_file, self.notes]


def normalize_category(text: str) -> str:
    key = text.strip().lower().replace("&", "and")
    for ch in " /-,.":
        key = key.replace(ch, "_")
    while "__" in key:
        key = key.replace("__", "_")
    key = key.strip("_")
    if key in _ALIASES:
        return _ALIASES[key]
    # Keyword fallback, so the full labels the tool prints ("Sexual harassment prevention training",
    # "Professional conduct / ethics", "Illinois statutes and rules (Part 1380)") work when copied.
    # Anything that says "elective" is elective, whatever else it says ("elective - NEC rules"), so an
    # elective course can never be mistaken for a core hour.
    if any(word in key for word in ("elective", "general", "technical")):
        return "elective"
    found = {cat for word, cat in (("harass", "harassment"), ("ethic", "ethics"), ("conduct", "ethics"),
                                   ("statut", "statutes_rules"), ("rules", "statutes_rules"), ("laws", "statutes_rules"))
             if word in key}
    if len(found) == 1:
        return found.pop()
    if found:
        raise LogFormatError(f"category '{text}' could be {' or '.join(sorted(found))}; use one of: "
                             f"{', '.join(CATEGORIES)}")
    raise LogFormatError(f"category '{text}' is not one of: {', '.join(CATEGORIES)} "
                         "(plain words like 'Ethics' or 'sexual harassment' are fine)")


def parse_hours(text: str) -> float:
    try:
        hours = float(text.strip())
    except ValueError:
        raise LogFormatError(f"hours '{text}' is not a number") from None
    if not math.isfinite(hours):   # 'inf' and 'nan' parse as floats but are not hours
        raise LogFormatError(f"hours '{text}' is not a number")
    if hours <= 0:
        raise LogFormatError(f"hours must be more than 0, got {text.strip()}")
    return hours


def parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise LogFormatError(f"date '{text}' is not YYYY-MM-DD") from None


def _row_to_entry(row: list[str], line: int) -> Entry:
    if len(row) != len(HEADER):
        raise LogFormatError(f"line {line}: expected {len(HEADER)} columns, found {len(row)}")
    r = dict(zip(HEADER, (c.strip() for c in row)))
    try:
        return Entry(parse_date(r["date"]), parse_hours(r["hours"]), r["title"], r["provider"],
                     normalize_category(r["category"]), r["format"], r["location"],
                     r["certificate_file"], r["notes"], line)
    except LogFormatError as e:
        raise LogFormatError(f"line {line}: {e}") from None


def _read_text(path: Path) -> str:
    """UTF-8 (with or without Excel's BOM) is expected. Excel's plain 'CSV (Comma delimited)' save on
    Windows is cp1252, so an en dash or curly quote pasted from a certificate would otherwise crash."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def load_log(path: Path) -> list[Entry]:
    """Read the CSV. '#' comment lines and blank lines are skipped. Problems name the line number."""
    path = Path(path)
    if not path.exists():
        raise LogFormatError(f"log file not found: {path}. Add a row with 'python3 -m pdh_log add ...' "
                             "or copy samples/pdh_log_sample.csv to data/pdh_log.csv.")
    # The csv module sees the whole file, so a quoted cell with a line break (Excel Alt+Enter) stays one
    # row and the line numbers in messages stay right; reader.line_num counts physical lines.
    reader = csv.reader(io.StringIO(_read_text(path), newline=""))
    header_seen = False
    entries = []
    while True:
        line = reader.line_num + 1  # the physical line this row starts on
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as e:
            raise LogFormatError(f"line {line}: {e}") from None
        if not row or not "".join(row).strip() or row[0].lstrip().startswith("#"):
            continue
        if not header_seen:
            if [c.strip().lower() for c in row] != HEADER:
                raise LogFormatError(f"line {line}: header must be exactly '{','.join(HEADER)}', "
                                     f"found '{','.join(row)}'")
            header_seen = True
            continue
        entries.append(_row_to_entry(row, line))
    if not header_seen:
        raise LogFormatError(f"{path} has no header line. Expected: {','.join(HEADER)}")
    return entries


def append_entry(path: Path, entry: Entry) -> None:
    """Append one row; create the file (and its folder) with the header if it does not exist.
    An existing file must start with the expected header, so a row is never added to some other CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    if not new:
        first = _read_text(path).splitlines()[0]
        if [c.strip().lower() for c in first.split(",")] != HEADER:
            raise LogFormatError(f"{path} does not start with the header '{','.join(HEADER)}' "
                                 f"(found '{first.strip()}'), so nothing was added")
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HEADER)
        w.writerow(entry.as_row())
