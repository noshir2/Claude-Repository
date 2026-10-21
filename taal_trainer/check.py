"""Check the taal table embedded in taal_trainer.html, or rebuild it from taals.json.

    python3 -m taal_trainer.check            validate the block in the HTML
    python3 -m taal_trainer.check --embed    copy taals.json into the HTML block, then validate

Prints 'taal data OK: N taals' or 'Problem: ...' (exit code 1).
Standard library only. No I/O in the pure functions so the tests can call them directly.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML_PATH = HERE / "taal_trainer.html"
JSON_PATH = HERE / "taals.json"

BLOCK_RE = re.compile(
    r'(<script id="taal-data" type="application/json">)(.*?)(</script>)', re.S)
REQUIRED_NOTE = "Thekas vary by teacher and gharana"
STATUSES = ("standard", "standard-but-confirm")
FIELDS = ("name", "status", "matras", "vibhags", "sam", "taali", "khali", "bols")


def extract_block(html: str) -> str:
    """Return the raw JSON text inside <script id="taal-data">."""
    m = BLOCK_RE.search(html)
    if not m:
        raise ValueError('no <script id="taal-data" type="application/json"> block found')
    return m.group(2)


def load_taals(html: str) -> dict:
    """Parse the embedded block. Raises ValueError with a plain message on bad JSON."""
    text = extract_block(html)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"the taal block is not valid JSON (line {e.lineno}, column {e.colno}): "
                         f"{e.msg}. Check for a missing comma or quote.") from None
    return check_shape(data)


def check_shape(data) -> dict:
    """Raise ValueError unless data is {"note": str, "taals": [ {...}, ... ]}."""
    if not isinstance(data, dict) or not isinstance(data.get("taals"), list):
        raise ValueError('the taal table must be an object with a "taals" list')
    if not isinstance(data.get("note", ""), str):
        raise ValueError("the top-level 'note' must be a piece of text in quotes")
    for i, t in enumerate(data["taals"], 1):
        if not isinstance(t, dict):
            raise ValueError(f"taal number {i} is not an object in curly braces")
    return data


def whole(x) -> bool:
    """True for a plain whole number (not True/False, which Python also counts as ints)."""
    return isinstance(x, int) and not isinstance(x, bool)


def vibhag_starts(taal: dict) -> list[int]:
    """First matra of each vibhag. Teentaal [4,4,4,4] -> [1, 5, 9, 13]."""
    starts, pos = [], 1
    for size in taal["vibhags"]:
        starts.append(pos)
        pos += size
    return starts


def marker_row(taal: dict) -> list[str]:
    """Bhatkhande signs per matra: 'X' sam, '0' khali, '2','3',... taali in order, '' elsewhere.

    A sam that is also khali (Rupak) shows '0'. Taali numbering starts at 2 and skips the sam.
    """
    row = [""] * taal["matras"]
    n = 2
    for m in sorted(taal["taali"]):
        if m == taal["sam"]:
            continue
        row[m - 1] = str(n)
        n += 1
    for m in taal["khali"]:
        row[m - 1] = "0"
    if taal["sam"] not in taal["khali"]:
        row[taal["sam"] - 1] = "X"
    return row


def check_taal(taal: dict) -> list[str]:
    """Every problem with one taal, as plain sentences. Empty list = fine."""
    name = taal.get("name", "<unnamed>")
    out = []
    for f in FIELDS:
        if f not in taal:
            out.append(f"{name}: missing field '{f}'")
    if out:
        return out
    if not isinstance(taal["name"], str) or not taal["name"].strip():
        out.append("a taal has an empty name")
    n = taal["matras"]
    if not whole(n) or n < 1:
        out.append(f"{name}: matras must be a whole number of 1 or more")
    for f in ("vibhags", "taali", "khali", "bols"):
        if not isinstance(taal[f], list):
            out.append(f"{name}: {f} must be a list in square brackets, like [4, 4, 4, 4]")
    if out:
        return out
    if any(not whole(v) or v < 1 for v in taal["vibhags"]):
        return [f"{name}: every vibhag size must be a whole number of 1 or more (got {taal['vibhags']})"]
    if taal["status"] not in STATUSES:
        out.append(f"{name}: status must be one of {', '.join(STATUSES)}")
    if sum(taal["vibhags"]) != n:
        out.append(f"{name}: vibhags {taal['vibhags']} add up to {sum(taal['vibhags'])}, not {n} matras")
    if len(taal["bols"]) != n:
        out.append(f"{name}: {len(taal['bols'])} bols listed but the taal has {n} matras")
    if any(not isinstance(b, str) or not b for b in taal["bols"]):
        out.append(f"{name}: every bol must be a non-empty word (use '-' for a rest)")
    if not whole(taal["sam"]) or taal["sam"] != 1:
        out.append(f"{name}: sam must be matra 1 (it is {taal['sam']!r})")
    starts = vibhag_starts(taal)
    for kind in ("taali", "khali"):
        for m in taal[kind]:
            if not whole(m) or m < 1 or m > n:
                out.append(f"{name}: {kind} position {m!r} is outside 1..{n}")
            elif m not in starts:
                out.append(f"{name}: {kind} position {m} is not the first matra of a vibhag {starts}")
        if any(not whole(m) for m in taal[kind]):
            return out
        if len(set(taal[kind])) != len(taal[kind]):
            out.append(f"{name}: duplicate {kind} positions {taal[kind]}")
    both = sorted(set(taal["taali"]) & set(taal["khali"]))
    if both:
        out.append(f"{name}: matras {both} are listed as both taali and khali")
    return out


def check_data(data: dict) -> list[str]:
    """All problems across the table. Empty list = fine."""
    out = []
    if REQUIRED_NOTE not in data.get("note", ""):
        out.append(f"the block's top-level 'note' must contain: {REQUIRED_NOTE}")
    names = [t.get("name") for t in data["taals"]]
    dupes = sorted({x for x in names if names.count(x) > 1})
    if dupes:
        out.append(f"duplicate taal names: {', '.join(map(str, dupes))}")
    for t in data["taals"]:
        out += check_taal(t)
    rupak = next((t for t in data["taals"] if t.get("name") == "Rupak"), None)
    if rupak is not None and not check_taal(rupak):
        if rupak["sam"] not in rupak["khali"] or rupak["sam"] in rupak["taali"]:
            out.append("Rupak: matra 1 must be in khali and not in taali (its sam is a wave)")
    return out


def format_block(data: dict) -> str:
    """Pretty JSON with one taal per block and every list on one line (easy to edit by hand)."""
    def one_line(v):
        return json.dumps(v, ensure_ascii=False)
    lines = ["{", f'  "note": {one_line(data["note"])},', '  "taals": [']
    for i, t in enumerate(data["taals"]):
        body = ",\n".join(f'      "{k}": {one_line(v)}' for k, v in t.items())
        lines.append("    {\n" + body + "\n    }" + ("," if i < len(data["taals"]) - 1 else ""))
    lines += ["  ]", "}"]
    return "\n".join(lines)


def embed(html: str, data: dict) -> str:
    """Return the HTML with the taal block replaced by data."""
    if not BLOCK_RE.search(html):
        raise ValueError('no <script id="taal-data" type="application/json"> block to replace')
    return BLOCK_RE.sub(lambda m: m.group(1) + "\n" + format_block(data) + "\n" + m.group(3), html, count=1)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="taal_trainer.check",
                                description="Validate the taal table inside taal_trainer.html")
    p.add_argument("--html", default=str(HTML_PATH), help="the HTML file to check")
    p.add_argument("--embed", action="store_true",
                   help="first copy taals.json into the HTML block (use after editing taals.json)")
    p.add_argument("--json", default=str(JSON_PATH), help="taals.json used by --embed")
    args = p.parse_args(argv)
    problems = []
    try:
        html = Path(args.html).read_text(encoding="utf-8")
        if args.embed:
            # utf-8-sig also accepts a file saved as "UTF-8 with BOM" (a Notepad option)
            try:
                data = check_shape(json.loads(Path(args.json).read_text(encoding="utf-8-sig")))
            except json.JSONDecodeError as e:
                raise ValueError(f"{Path(args.json).name} is not valid JSON (line {e.lineno}, column "
                                 f"{e.colno}): {e.msg}. Check for a missing comma or quote.") from None
            problems = check_data(data)
            if problems:          # never write a broken table into the HTML
                problems.append(f"{Path(args.html).name} was left unchanged")
            else:
                html = embed(html, data)
                Path(args.html).write_text(html, encoding="utf-8")
                print(f"Copied {Path(args.json).name} into {Path(args.html).name}.")
        if not problems:
            data = load_taals(html)
            problems = check_data(data)
            if REQUIRED_NOTE not in html:
                problems.append(f"the HTML must contain the note: {REQUIRED_NOTE}")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 1
    if problems:
        for pr in problems:
            print(f"Problem: {pr}", file=sys.stderr)
        return 1
    print(f"taal data OK: {len(data['taals'])} taals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
