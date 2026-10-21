"""Read the JSON block out of frc_shop_card.html, check it, expand the flashcards, pick warm-ups.
No HTML rendering here: the page renders itself in the browser from the same block."""
import json
import re
from pathlib import Path

from . import calc

HTML_PATH = Path(__file__).with_name("frc_shop_card.html")
BLOCK_RE = re.compile(r'<script id="card-data" type="application/json">\s*(.*?)\s*</script>', re.S)
SECTIONS = ("safety", "rule_table", "reference_tables", "team_standards_example", "motors", "battery",
            "awg_table", "cards", "golden")
TAGS = ("physics", "rule", "vendor", "example-team-standard")
KINDS = ("number", "concept", "safety")
WEEKS = range(0, 11)
MIN_CARDS, MAX_CARDS, MIN_PER_WEEK = 50, 70, 3
AWG_TOLERANCE = 0.02      # the embedded AWG table may differ from the formula by at most 2%
GOLDEN_TOLERANCE = 0.02   # golden examples are stored rounded; Python must land within 2%
FIELD_RE = re.compile(r"\{(\w+)\}")


class CardDataError(ValueError):
    pass


def extract_block(html: str) -> str:
    m = BLOCK_RE.search(html)
    if not m:
        raise CardDataError('no <script id="card-data" type="application/json"> block found')
    return m.group(1)


def load_card_data(path: Path = HTML_PATH) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(extract_block(text))
    except json.JSONDecodeError as e:
        raise CardDataError(f"the card-data block is not valid JSON: {e}. "
                            "Common causes: a missing comma, a trailing comma, or a quote mark.") from e


def replace_block(html: str, data: dict) -> str:
    return BLOCK_RE.sub(lambda m: '<script id="card-data" type="application/json">\n'
                        + dump_block(data) + "\n</script>", html, count=1)


def dump_block(data: dict) -> str:
    """JSON with one table row per line, so a number is easy to find and edit in Notepad."""
    def row(x):
        return json.dumps(x, ensure_ascii=False)

    lines = ["{"]
    keys = list(data)
    for ki, key in enumerate(keys):
        val = data[key]
        comma = "," if ki < len(keys) - 1 else ""
        if key == "reference_tables":
            lines.append(f'  "{key}": [')
            for ti, table in enumerate(val):
                lines.append("    {")
                tkeys = [k for k in table if k != "rows"]
                for k in tkeys:
                    lines.append(f'      "{k}": {row(table[k])},')
                lines.append('      "rows": [')
                for ri, r in enumerate(table.get("rows", [])):
                    lines.append("        " + row(r) + ("," if ri < len(table["rows"]) - 1 else ""))
                lines.append("      ]")
                lines.append("    }" + ("," if ti < len(val) - 1 else ""))
            lines.append("  ]" + comma)
        elif isinstance(val, list):
            lines.append(f'  "{key}": [')
            for ri, r in enumerate(val):
                lines.append("    " + row(r) + ("," if ri < len(val) - 1 else ""))
            lines.append("  ]" + comma)
        else:
            lines.append(f'  "{key}": {row(val)}{comma}')
    lines.append("}")
    return "\n".join(lines)


# --- tables and cards -------------------------------------------------------------------------
def tables(data: dict) -> dict[str, list[dict]]:
    """Every row list that a number card may read, by table name."""
    out = {"rule_table": data.get("rule_table", []), "team_standards_example": data.get("team_standards_example", []),
           "motors": data.get("motors", []), "battery": data.get("battery", []),
           "awg_table": data.get("awg_table", []), "safety": data.get("safety", [])}
    for t in data.get("reference_tables", []):
        if isinstance(t, dict) and t.get("id"):
            out[t["id"]] = t.get("rows", [])
    return out


def find_row(rows: list[dict], ref):
    """A card points at a row by its "id" (preferred) or its position."""
    if isinstance(ref, bool) or not isinstance(rows, list):
        return None
    if isinstance(ref, int):
        return rows[ref] if 0 <= ref < len(rows) and isinstance(rows[ref], dict) else None
    for r in rows:
        if isinstance(r, dict) and r.get("id") == ref:
            return r
    return None


def _js_str(v) -> str:
    """Render a value the way JavaScript's String() does, so both sides print '3 A', not '3.0 A'."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def fill(template: str, row: dict) -> str:
    return FIELD_RE.sub(lambda m: _js_str(row[m.group(1)]) if m.group(1) in row else m.group(0), str(template))


def card_id(card: dict) -> str:
    if card.get("kind") == "number" and "from_table" in card:
        return f"n:{card['from_table']}:{card['row']}"
    h = 0
    for ch in f"{card.get('week')}|{card.get('front', '')}":
        h = (h * 31 + ord(ch)) % 4294967296
    return f"w:{card.get('week')}:{h}"


def expand_cards(data: dict) -> list[dict]:
    """Written cards as they are; number cards filled in from their table row, in data order.
    A number card whose row has no source is dropped, like the row itself on the page."""
    tbl = tables(data)
    out = []
    for c in data.get("cards", []):
        if c.get("kind") == "number" and "from_table" in c:
            row = find_row(tbl.get(c["from_table"], []), c.get("row"))
            if row is None or not row.get("source"):
                continue
            src = str(row.get("source", ""))
            if row.get("season"):
                src += f" (season {row['season']}; verify against the current manual)"
            answer = "{value}" if c.get("answer") is None else c["answer"]
            out.append({"id": card_id(c), "week": c.get("week"), "kind": "number",
                        "front": fill(c.get("template", ""), row), "back": fill(answer, row),
                        "source": src, "tag": row.get("tag", "")})
        else:
            out.append({"id": card_id(c), "week": c.get("week"), "kind": c.get("kind", "concept"),
                        "front": c.get("front", ""), "back": c.get("back", ""),
                        "source": c.get("source", ""), "tag": c.get("tag", "")})
    return out


# --- deterministic warm-up ------------------------------------------------------------------
def lcg(seed: int):
    """32-bit linear congruential generator; the page uses the same one, so a week + seed
    prints the same five questions on paper and on the screen."""
    s = int(seed) % 4294967296

    def rand():
        nonlocal s
        s = (s * 1664525 + 1013904223) % 4294967296
        return s / 4294967296
    return rand


def shuffle(items: list, rand) -> list:
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = int(rand() * (i + 1))
        out[i], out[j] = out[j], out[i]
    return out


def warmup(data: dict, week: int, seed: int, n_week: int = 3, n_earlier: int = 2) -> dict:
    """3 questions from the chosen week + 2 from earlier weeks, fixed by the seed."""
    if week not in WEEKS:
        raise ValueError(f"week must be 0-10, got {week}")
    cards = [c for c in expand_cards(data) if _is_num(c.get("week"))]   # a card with a text week is skipped; check names it
    rand = lcg(seed * 1000 + week)
    this_week = shuffle([c for c in cards if c["week"] == week], rand)
    earlier = shuffle([c for c in cards if c["week"] < week], rand)
    picks = this_week[:n_week] + earlier[:n_earlier]
    if len(picks) < n_week + n_earlier:          # a short week borrows from the other pool
        extra = this_week[n_week:] + earlier[n_earlier:]
        picks += extra[:n_week + n_earlier - len(picks)]
    return {"week": week, "seed": seed, "questions": picks}


# --- the checker ------------------------------------------------------------------------------
def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def check_card(data: dict) -> tuple[list[str], dict]:
    problems: list[str] = []
    counts = {"rows": 0, "cards": 0, "written": 0, "generated": 0}

    for s in SECTIONS:
        if s not in data:
            problems.append(f"section '{s}' is missing from the block")
        elif not isinstance(data[s], list):
            problems.append(f"section '{s}' must be a list [ ... ] of rows")
    if problems:
        return problems, counts

    def check_rows(name: str, rows, need_season: bool = False):
        if not isinstance(rows, list):
            problems.append(f"{name}: must be a list of rows")
            return
        ids = set()
        for i, r in enumerate(rows):
            counts["rows"] += 1
            if not isinstance(r, dict):
                problems.append(f"{name} row {i}: not an object")
                continue
            where = f"{name} row {i} ({r.get('id') or r.get('item') or r.get('label') or '?'})"
            if r.get("id") is not None:
                if r["id"] in ids:
                    problems.append(f"{where}: duplicate id {r['id']!r} (a card or lookup would read the first copy)")
                ids.add(r["id"])
            if not str(r.get("source", "")).strip():
                problems.append(f"{where}: no source")
            if r.get("tag") not in TAGS:
                problems.append(f"{where}: tag must be one of {', '.join(TAGS)}")
            if (need_season or r.get("tag") == "rule") and not str(r.get("season", "")).strip():
                problems.append(f"{where}: rule row without a season")

    check_rows("safety", data["safety"])
    check_rows("rule_table", data["rule_table"], need_season=True)
    for r in data["rule_table"]:
        if isinstance(r, dict):
            if r.get("protection") in ("breaker", "fuse") and not (_is_num(r.get("amps_min")) and _is_num(r.get("amps_max"))):
                problems.append(f"rule_table row {r.get('id')}: breaker/fuse rows need numeric amps_min and amps_max")
            if not (_is_num(r.get("min_awg")) or r.get("min_awg") == "n/a"):
                problems.append(f"rule_table row {r.get('id')}: min_awg must be a number (the gauge) or \"n/a\"")
    if not isinstance(data["reference_tables"], list):
        problems.append("reference_tables must be a list of tables")
    else:
        for t in data["reference_tables"]:
            if not isinstance(t, dict) or not t.get("id") or not t.get("title"):
                problems.append("a reference table lacks an id or title")
                continue
            check_rows(f"reference table '{t['id']}'", t.get("rows", []))
    check_rows("team_standards_example", data["team_standards_example"])
    check_rows("motors", data["motors"])
    check_rows("battery", data["battery"])
    check_rows("awg_table", data["awg_table"])

    # AWG table versus the formula
    seen = set()
    for r in data["awg_table"]:
        if not isinstance(r, dict) or not _is_num(r.get("awg")):
            problems.append("awg_table row without a numeric awg")
            continue
        try:
            n = calc.check_awg(r["awg"])
        except ValueError as e:
            problems.append(f"awg_table: {e}")
            continue
        seen.add(n)
        want = calc.awg_mohm_per_ft(n)
        have = r.get("mohm_per_ft")
        if not _is_num(have):
            problems.append(f"awg_table {n} AWG: mohm_per_ft {have!r} is text in quotes or missing, not a number")
        elif abs(have - want) / want > AWG_TOLERANCE:
            problems.append(f"awg_table {n} AWG: mohm_per_ft {have} differs from the formula ({want:.4g}) by more than 2%")
    missing = [n for n in range(calc.AWG_MIN, calc.AWG_MAX + 1) if n not in seen]
    if missing:
        problems.append(f"awg_table is missing AWG {missing}")

    # cards
    tbl = tables(data)
    per_week = {w: 0 for w in WEEKS}
    seen_cards = set()
    for i, c in enumerate(data["cards"]):
        where = f"card {i}"
        if not isinstance(c, dict):
            problems.append(f"{where}: not an object")
            continue
        counts["cards"] += 1
        cid = card_id(c)
        if cid in seen_cards:
            problems.append(f"{where}: duplicate card (week {c.get('week')}, "
                            f"{str(c.get('front') or c.get('template', ''))[:40]!r}); progress would be shared")
        seen_cards.add(cid)
        if not (_is_num(c.get("week")) and c["week"] in WEEKS):
            problems.append(f"{where}: week must be 0-10")
        else:
            per_week[c["week"]] += 1
        if c.get("kind") not in KINDS:
            problems.append(f"{where}: kind must be one of {', '.join(KINDS)}")
        if c.get("kind") == "number" and "from_table" in c:
            counts["generated"] += 1
            rows = tbl.get(c["from_table"])
            if rows is None:
                problems.append(f"{where}: from_table '{c['from_table']}' is not a table in the block")
                continue
            row = find_row(rows, c.get("row"))
            if row is None:
                problems.append(f"{where}: row {c.get('row')!r} not found in {c['from_table']}")
                continue
            if not str(c.get("template", "")).strip():
                problems.append(f"{where}: number card without a template")
            if "answer" in c and not isinstance(c["answer"], str):
                problems.append(f"{where}: answer must be text in quotes, e.g. \"{{value}}\"")
            for fld in FIELD_RE.findall(str(c.get("template", "")) + str(c.get("answer", "{value}"))):
                if fld not in row:
                    problems.append(f"{where}: template field {{{fld}}} is not in {c['from_table']} row {c.get('row')}")
        else:
            counts["written"] += 1
            for fld in ("front", "back", "source"):
                if not str(c.get(fld, "")).strip():
                    problems.append(f"{where} ({str(c.get('front', ''))[:40]}): no {fld}")
    if counts["cards"] < MIN_CARDS:
        problems.append(f"only {counts['cards']} cards; the deck needs at least {MIN_CARDS}")
    if counts["cards"] > MAX_CARDS:
        problems.append(f"{counts['cards']} cards; the deck is meant to stay at or under {MAX_CARDS}")
    short = [w for w, n in per_week.items() if n < MIN_PER_WEEK]
    if short:
        problems.append(f"weeks with fewer than {MIN_PER_WEEK} cards: {short}")

    problems += check_golden(data["golden"])
    return problems, counts


def run_golden(ex: dict) -> dict:
    """Run one golden example through the Python calculators."""
    kind, inp = ex.get("calc"), dict(ex.get("in", {}))
    if kind == "vdrop":
        return calc.vdrop(inp["awg"], inp["amps"], inp["feet"])
    if kind == "brownout":
        return calc.brownout(inp["battery_mohm"], inp["path_mohm"], inp.get("amps"), inp.get("threshold"),
                             inp.get("open_v", calc.DEFAULT_OPEN_V))
    if kind == "battery_r":
        return calc.battery_r(inp["open_v"], inp["loaded_v"], inp["amps"])
    if kind == "short":
        return calc.short_circuit(inp["battery_mohm"], inp["path_mohm"], inp.get("open_v", calc.DEFAULT_OPEN_V))
    if kind == "ohm":
        return calc.ohms_law(inp.get("volts"), inp.get("amps"), inp.get("ohms"))
    if kind == "i2t":
        return calc.i2t(inp["amps"], inp["seconds"])
    raise ValueError(f"unknown calc '{kind}'")


def check_golden(golden) -> list[str]:
    problems = []
    if not isinstance(golden, list) or not golden:
        return ["golden: needs at least one example"]
    for i, ex in enumerate(golden):
        try:
            got = run_golden(ex)
        except (KeyError, ValueError, TypeError) as e:
            problems.append(f"golden example {i}: cannot run ({e})")
            continue
        for key, want in ex.get("out", {}).items():
            have = got.get(key)
            if not _is_num(have):
                problems.append(f"golden example {i} ({ex.get('calc')}): calculator has no '{key}'")
            elif abs(have - want) > max(GOLDEN_TOLERANCE * abs(want), 0.005):
                problems.append(f"golden example {i} ({ex.get('calc')}): {key} expected {want}, Python gives {have:.4g}")
    return problems
