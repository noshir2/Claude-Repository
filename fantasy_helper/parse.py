"""Read FantasyPros projection CSV exports, league.txt and roster.csv.

Column layouts come from facts_fantasy.md Table A (verified against the FantasyPros
projection pages and 20+ public exports, 2019-2026). The first real file may still
need a one-line fix here; when a file does not match, the error shows both headers.
"""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DST")

# Header rows exactly as FantasyPros exports them (season and weekly exports are identical).
EXPECTED_HEADERS = {
    "QB": ["Player", "Team", "ATT", "CMP", "YDS", "TDS", "INTS", "ATT", "YDS", "TDS", "FL", "FPTS"],
    "RB": ["Player", "Team", "ATT", "YDS", "TDS", "REC", "YDS", "TDS", "FL", "FPTS"],
    "WR": ["Player", "Team", "REC", "YDS", "TDS", "ATT", "YDS", "TDS", "FL", "FPTS"],
    "TE": ["Player", "Team", "REC", "YDS", "TDS", "FL", "FPTS"],
    "K": ["Player", "Team", "FG", "FGA", "XPT", "FPTS"],
    "DST": ["Player", "Team", "SACK", "INT", "FR", "FF", "TD", "SAFETY", "PA", "YDS_AGN", "FPTS"],
}
# What each stat column means, in file order. The repeated ATT/YDS/TDS names are told
# apart by position: QB = passing then rushing; RB = rushing then receiving;
# WR = receiving then rushing; TE = receiving only.
STAT_KEYS = {
    "QB": ["pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int",
           "rush_att", "rush_yds", "rush_td", "fumble_lost"],
    "RB": ["rush_att", "rush_yds", "rush_td", "rec", "rec_yds", "rec_td", "fumble_lost"],
    "WR": ["rec", "rec_yds", "rec_td", "rush_att", "rush_yds", "rush_td", "fumble_lost"],
    "TE": ["rec", "rec_yds", "rec_td", "fumble_lost"],
    "K": ["fg", "fga", "xpt"],
    "DST": ["dst_sack", "dst_int", "dst_fr", "dst_ff", "dst_td", "dst_safety", "dst_pa", "dst_yds_agn"],
}
# The website shows 'YDS AGN' and 'DEF TD'; the CSV uses 'YDS_AGN' and 'TD'. Accept both.
HEADER_SYNONYMS = {"YDS AGN": "YDS_AGN", "DEF TD": "TD", "DEF_TD": "TD"}

# Which word in a file name picks the position (FantasyPros_Fantasy_Football_Projections_QB.csv).
FILE_WORDS = {"QB": ("qb",), "RB": ("rb",), "WR": ("wr",), "TE": ("te",), "K": ("k",), "DST": ("dst", "def")}

# Weekly and season exports have identical headers, so we judge by size: no single game
# reaches these numbers, season totals always do.
SEASON_SIGNALS = {
    "QB": ("pass_att", "pass attempts", 100),
    "RB": ("rush_att", "rush attempts", 60),
    "WR": ("rec", "receptions", 30),
    "TE": ("rec", "receptions", 30),
    "K": ("fga", "field-goal attempts", 10),
    "DST": ("dst_sack", "sacks", 12),
}

POSITION_ALIASES = {"DEF": "DST", "D/ST": "DST", "DST": "DST", "D": "DST", "DEFENSE": "DST",
                    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "PK": "K"}


class ExportFormatError(ValueError):
    """A projection, roster or league file does not look the way we expect."""


@dataclass
class Projection:
    name: str
    team: str
    pos: str
    stats: dict
    fpts: float | None
    high: dict | None = None
    low: dict | None = None
    high_fpts: float | None = None
    low_fpts: float | None = None


@dataclass
class ProjectionSet:
    folder: Path
    by_pos: dict
    season: bool
    kind_note: str

    def all(self) -> list:
        return [p for rows in self.by_pos.values() for p in rows]


def _number(text: str) -> float:
    cleaned = text.strip().replace(",", "").replace("$", "")
    if cleaned in ("", "-", "--"):
        return 0.0
    return float(cleaned)


def _clean_header(cells) -> list:
    out = []
    for c in cells:
        c = c.strip().lstrip("﻿").strip().upper()
        out.append(HEADER_SYNONYMS.get(c, c))
    while out and out[-1] == "":
        out.pop()
    return out


def parse_projection_file(path: Path, pos: str) -> list:
    """One FantasyPros position file -> list of Projection (with high/low rows attached)."""
    expected = EXPECTED_HEADERS[pos]
    keys = STAT_KEYS[pos]
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ExportFormatError(f"{path.name} is empty.")
    if _clean_header(rows[0]) != [h.upper() for h in expected]:
        raise ExportFormatError(
            f"{path.name} does not look like a FantasyPros {pos} projection export.\n"
            f"  Header found:    {','.join(c.strip() for c in rows[0])}\n"
            f"  Header expected: {','.join(expected)}\n"
            "  Check that the file is the Projections export for that position (not Rankings). "
            "If FantasyPros changed its columns, EXPECTED_HEADERS in fantasy_helper/parse.py needs a one-line fix.")
    width = len(expected)
    players: list[Projection] = []
    for lineno, raw in enumerate(rows[1:], start=2):
        row = [c.strip() for c in raw] + [""] * max(0, width - len(raw))
        name, team = row[0], row[1]
        try:
            if name == "":
                tag = team.lower()
                if tag in ("high", "low") and players:
                    stats = {k: _number(v) for k, v in zip(keys, row[2:2 + len(keys)])}
                    fpts = _number(row[2 + len(keys)]) if row[2 + len(keys)] else None
                    if tag == "high":
                        players[-1].high, players[-1].high_fpts = stats, fpts
                    else:
                        players[-1].low, players[-1].low_fpts = stats, fpts
                continue  # junk row (' ,,,') or a stray blank line
            stats = {k: _number(v) for k, v in zip(keys, row[2:2 + len(keys)])}
            fpts = _number(row[2 + len(keys)]) if row[2 + len(keys)] else None
        except ValueError as e:
            raise ExportFormatError(f"{path.name} line {lineno}: could not read a number ({e}).") from None
        players.append(Projection(name, team, pos, stats, fpts))
    return players


def find_projection_files(folder: Path) -> dict:
    """Pick each position's CSV by the position word in its file name."""
    if not folder.is_dir():
        raise ExportFormatError(f"projection folder {folder} does not exist.")
    found: dict[str, Path] = {}
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() != ".csv":
            continue
        tokens = set(re.split(r"[^a-z0-9]+", path.stem.lower())) - {""}
        for pos, words in FILE_WORDS.items():
            if tokens & set(words):
                if pos in found:
                    raise ExportFormatError(
                        f"two {pos} files in {folder}: {found[pos].name} and {path.name}. Keep one.")
                found[pos] = path
    return found


def looks_like_season(by_pos: dict) -> tuple:
    for pos, (stat, label, limit) in SEASON_SIGNALS.items():
        rows = by_pos.get(pos)
        if rows:
            biggest = max(p.stats.get(stat, 0.0) for p in rows)
            if biggest > limit:
                return True, (f"look like SEASON TOTALS (largest {pos} {label} is {biggest:g}; "
                              f"one game never reaches {limit})")
            return False, (f"look like WEEKLY numbers (largest {pos} {label} is {biggest:g}; "
                           f"a season file would be above {limit})")
    return False, "could not tell weekly from season (no files)"


def load_projections(folder: Path, needed=POSITIONS) -> ProjectionSet:
    files = find_projection_files(folder)
    missing = [p for p in needed if p not in files]
    if missing:
        names = ", ".join(p.name for p in sorted(folder.iterdir())) or "(folder is empty)"
        raise ExportFormatError(
            f"no projection file for {', '.join(missing)} in {folder}. I look for a CSV whose name contains "
            f"qb, rb, wr, te, k, or dst/def. Files there: {names}")
    by_pos = {pos: parse_projection_file(path, pos) for pos, path in files.items()}
    season, note = looks_like_season(by_pos)
    return ProjectionSet(folder, by_pos, season, note)


# ---------------------------------------------------------------- league.txt and roster.csv

@dataclass
class Slot:
    label: str
    allowed: tuple
    count: int


@dataclass
class League:
    slots: list
    scoring: dict
    folder: Path = field(default_factory=Path)

    def positions_needed(self) -> tuple:
        return tuple(p for p in POSITIONS if any(p in s.allowed for s in self.slots))


# Yahoo default starters (help.yahoo.com/kb/SLN6489.html, facts Table C): verify on your league's settings page.
DEFAULT_SLOTS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1}
DEFAULT_FLEX_FROM = ("WR", "RB", "TE")  # Yahoo's W/R/T flex (help.yahoo.com/kb/SLN6500.html)
SLOT_ORDER = ("QB", "RB", "WR", "TE", "FLEX", "K", "DEF")


def _position(text: str) -> str:
    p = text.strip().upper()
    if p == "":
        return ""
    if p not in POSITION_ALIASES:
        raise ExportFormatError(f"unknown position {text!r}; use QB, RB, WR, TE, K or DEF.")
    return POSITION_ALIASES[p]


def parse_league_text(text: str, scoring_defaults: dict, source: str = "league.txt") -> League:
    """key = value lines, # comments. Unknown keys are an error so a typo cannot silently do nothing."""
    counts: dict[str, int] = {}
    flex_from: dict[str, tuple] = {}
    scoring = dict(scoring_defaults)
    order: list[str] = []
    seen: dict[str, int] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" not in line:
            raise ExportFormatError(f"{source} line {lineno}: expected 'name = value', got {raw.strip()!r}.")
        key, value = (s.strip() for s in line.split("=", 1))
        k = key.lstrip("\ufeff").upper().replace("-", "_")
        try:
            if k == "DST":
                k = "DEF"
            if k in seen:
                raise ExportFormatError(f"{source} line {lineno}: {key!r} was already set on line {seen[k]}; keep one.")
            seen[k] = lineno
            if k.endswith("_FROM"):
                base = k[:-5]
                flex_from[base] = tuple(_position(v) for v in value.replace("/", ",").split(",") if v.strip())
                if base not in order:
                    order.append(base)
            elif k in DEFAULT_SLOTS or k.startswith("FLEX") or k.endswith("FLEX"):
                counts[k] = int(value)
                if counts[k] < 0:
                    raise ExportFormatError(f"{source} line {lineno}: {key} = {value} is below 0; use 0 for no such slot.")
                if k not in order:
                    order.append(k)
            elif key.lower() in scoring:
                scoring[key.lower()] = float(value)
            else:
                known = ", ".join(list(DEFAULT_SLOTS) + ["FLEX_FROM", "<NAME>FLEX / <NAME>FLEX_FROM"] + list(scoring))
                raise ExportFormatError(f"{source} line {lineno}: unknown setting {key!r}. Known settings: {known}")
        except ExportFormatError:
            raise
        except ValueError:
            raise ExportFormatError(f"{source} line {lineno}: {value!r} is not a number.") from None
    for k, v in DEFAULT_SLOTS.items():
        counts.setdefault(k, v)
    flex_from.setdefault("FLEX", DEFAULT_FLEX_FROM)
    for k, v in counts.items():
        if v > 0 and k not in DEFAULT_SLOTS and k not in flex_from:
            raise ExportFormatError(f"{source}: '{k} = {v}' needs a '{k}_FROM = WR,RB,TE' line saying which "
                                    "positions may fill it.")
    for base in flex_from:
        counts.setdefault(base, 0)
    slots = []
    for label in SLOT_ORDER[:4]:
        if counts[label] > 0:
            slots.append(Slot(label, (label,), counts[label]))
    for label in order + ["FLEX"]:
        if label in flex_from and counts.get(label, 0) > 0 and not any(s.label == label for s in slots):
            slots.append(Slot(label, flex_from[label], counts[label]))
    for label, pos in (("K", "K"), ("DEF", "DST")):
        if counts[label] > 0:
            slots.append(Slot(label, (pos,), counts[label]))
    if not slots:
        raise ExportFormatError(f"{source}: every starting slot is 0, so there is no lineup to fill.")
    return League(slots, scoring)


def parse_league(path: Path, scoring_defaults: dict) -> League:
    if not path.exists():
        raise ExportFormatError(f"{path} not found. Copy fantasy_helper/samples/league1/league.txt there and edit it.")
    league = parse_league_text(path.read_text(encoding="utf-8-sig"), scoring_defaults, path.name)
    league.folder = path.parent
    return league


def parse_roster(path: Path) -> list:
    """roster.csv (player,position) -> [(name, position-or-'')]. Position blank is allowed."""
    if not path.exists():
        raise ExportFormatError(f"{path} not found. It needs a header 'player,position' and one player per line.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [[c.strip() for c in r] for r in reader]
    if not rows:
        raise ExportFormatError(f"{path} is empty.")
    header = [c.lower() for c in rows[0]]
    if "player" not in header:
        raise ExportFormatError(f"{path.name}: expected a header with 'player' (and optionally 'position'); "
                                f"found: {','.join(rows[0])}")
    pi = header.index("player")
    qi = header.index("position") if "position" in header else None
    out = []
    for r in rows[1:]:
        if not r or pi >= len(r) or not r[pi] or r[pi].startswith("#"):
            continue
        pos = _position(r[qi]) if qi is not None and qi < len(r) else ""
        out.append((r[pi], pos))
    return out


def parse_name_list(path: Path) -> list:
    """One player name per line; # comments allowed."""
    if not path.exists():
        raise ExportFormatError(f"{path} not found.")
    names = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            names.append(line)
    return names
