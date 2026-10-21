"""Turn FantasyPros stat columns into points under YOUR league's scoring.

Defaults are Yahoo's default scoring (help.yahoo.com/kb/SLN6489.html, facts_fantasy.md Table D).
Yahoo's help page is undated and a commissioner can change anything, so every value here can be
overridden in league.txt: verify against your league's settings page for the current season.
"""
import math

DEFAULT_SCORING = {
    # offense (Table D)
    "pass_yds": 0.04,      # 1 point per 25 passing yards
    "pass_td": 4,
    "pass_int": -1,
    "rush_yds": 0.1,       # 1 per 10
    "rush_td": 6,
    "rec": 0.5,            # half-PPR, the modern Yahoo default
    "rec_yds": 0.1,
    "rec_td": 6,
    "fumble_lost": -2,
    # kickers. Yahoo pays 3 (0-39 yds), 4 (40-49), 5 (50+), but the FantasyPros file has no distance
    # split, so one average per field goal is used. 3.3 is an estimate for Yahoo's tiers; FantasyPros'
    # own FPTS column uses a flat 3 (facts Table E). Change 'fg' in league.txt if you prefer.
    "fg": 3.3,
    "fg_missed": 0,        # Yahoo default: no penalty (Table D); applied to FGA - FG
    "xpt": 1,
    # defense / special teams (Table D). Blocked kicks and return TDs are not in the CSV, so not scored.
    "dst_sack": 1,
    "dst_int": 2,
    "dst_fr": 2,
    "dst_td": 6,
    "dst_safety": 2,
    "dst_pa_0": 10,
    "dst_pa_1_6": 7,
    "dst_pa_7_13": 4,
    "dst_pa_14_20": 1,
    "dst_pa_21_27": 0,
    "dst_pa_28_34": -1,
    "dst_pa_35": -4,
}

# What FantasyPros' own FPTS column is built from on the Half PPR tab (facts Table F and the
# FPTS note): same as above except a flat 3 per field goal. Used only to explain mismatches.
FANTASYPROS_HALF_PPR = {**DEFAULT_SCORING, "fg": 3}


def points_allowed_tier(pa: float, rules: dict) -> float:
    """Points-allowed tier. A projected 17.2 counts as 17 (the 14-20 tier), i.e. whole-number part."""
    n = math.floor(pa + 1e-9)
    if n <= 0:
        return rules["dst_pa_0"]
    if n <= 6:
        return rules["dst_pa_1_6"]
    if n <= 13:
        return rules["dst_pa_7_13"]
    if n <= 20:
        return rules["dst_pa_14_20"]
    if n <= 27:
        return rules["dst_pa_21_27"]
    if n <= 34:
        return rules["dst_pa_28_34"]
    return rules["dst_pa_35"]


def score(pos: str, stats: dict, rules: dict, pa_tier: bool = True) -> float:
    """Points for one stat line. pa_tier=False skips the DST points-allowed tier (season totals)."""
    g = stats.get
    if pos == "K":
        misses = max(g("fga", 0.0) - g("fg", 0.0), 0.0)
        return g("fg", 0.0) * rules["fg"] + g("xpt", 0.0) * rules["xpt"] + misses * rules["fg_missed"]
    if pos == "DST":
        total = (g("dst_sack", 0.0) * rules["dst_sack"] + g("dst_int", 0.0) * rules["dst_int"]
                 + g("dst_fr", 0.0) * rules["dst_fr"] + g("dst_td", 0.0) * rules["dst_td"]
                 + g("dst_safety", 0.0) * rules["dst_safety"])
        if pa_tier:
            total += points_allowed_tier(g("dst_pa", 0.0), rules)
        return total
    return (g("pass_yds", 0.0) * rules["pass_yds"] + g("pass_td", 0.0) * rules["pass_td"]
            + g("pass_int", 0.0) * rules["pass_int"]
            + g("rush_yds", 0.0) * rules["rush_yds"] + g("rush_td", 0.0) * rules["rush_td"]
            + g("rec", 0.0) * rules["rec"] + g("rec_yds", 0.0) * rules["rec_yds"]
            + g("rec_td", 0.0) * rules["rec_td"]
            + g("fumble_lost", 0.0) * rules["fumble_lost"])
