"""Match the names in roster.csv to the names in the projection files, loudly."""
import difflib
import re
from dataclasses import dataclass

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
DST_WORDS = {"dst", "d", "st", "def", "defense", "defence", "dt"}
CLOSE_CUTOFF = 0.85

# NFL team abbreviations as used in the FantasyPros Team column, mapped to the full team name
# used in the DST file. General knowledge, NOT from the verified facts file: verify. If one is
# wrong for your file, write the city or nickname in roster.csv instead (e.g. 'Chicago D/ST').
NFL_TEAMS = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAC": "Jacksonville Jaguars",
    "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams", "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants", "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}


def normalise(name: str) -> str:
    """'A.J. Sample Jr.' -> 'aj sample'; 'Sample City D/ST' -> 'sample city d st'."""
    s = name.lower().replace(".", "").replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    tokens = s.split()
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def dst_tokens(name: str) -> frozenset:
    """Words that identify a defense: drop 'D/ST', 'DEF' and friends, expand a team abbreviation."""
    tokens = [t for t in normalise(name).split() if t not in DST_WORDS]
    if len(tokens) == 1 and tokens[0].upper() in NFL_TEAMS:
        tokens = normalise(NFL_TEAMS[tokens[0].upper()]).split()
    return frozenset(tokens)


def looks_like_dst(name: str) -> bool:
    return bool(set(normalise(name).split()) & DST_WORDS)


@dataclass
class Match:
    query: str
    projection: object       # Projection or None
    how: str                 # exact | spelling | team | close | none
    detail: str = ""

    @property
    def line(self) -> str:
        """The 'I matched X to Y' sentence; '' for an exact match."""
        if self.how in ("exact", "none"):
            return ""
        return f"I matched '{self.query}' to '{self.projection.name}' ({self.detail})"


def match_name(query: str, pos: str, projections: list) -> Match:
    """Exact (after normalising) first, then D/ST aliases, then a close spelling above 0.85."""
    pool = [p for p in projections if not pos or p.pos == pos]
    q = normalise(query)
    for p in pool:
        if normalise(p.name) == q:
            if p.name == query:
                return Match(query, p, "exact")
            return Match(query, p, "spelling", "same name, different punctuation or suffix")
    def by_team():
        want = dst_tokens(query)
        hits = [p for p in pool if p.pos == "DST" and want and want <= dst_tokens(p.name)]
        if len(hits) == 1:
            return Match(query, hits[0], "team", "team name")
        if len(hits) > 1:
            return Match(query, None, "none",
                         f"'{query}' fits more than one defense: {', '.join(p.name for p in hits)}")
        return None

    if pos == "DST" or (not pos and looks_like_dst(query)):
        m = by_team()
        if m is not None:
            return m
    names = {normalise(p.name): p for p in pool}
    close = difflib.get_close_matches(q, list(names), n=1, cutoff=CLOSE_CUTOFF)
    if close:
        p = names[close[0]]
        ratio = difflib.SequenceMatcher(None, q, close[0]).ratio()
        return Match(query, p, "close", f"closest spelling, {ratio:.0%} similar; fix roster.csv if that is wrong")
    if not pos:  # a bare city or nickname with no position given, e.g. 'Sample City'
        m = by_team()
        if m is not None:
            return m
    return Match(query, None, "none")
