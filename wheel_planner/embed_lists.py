"""Rewrite the leveraged-ETF JSON block inside wheel_calculator.html from leveraged_etfs.txt.

Run after editing leveraged_etfs.txt:  python -m wheel_planner.embed_lists
"""
import json
import re
import sys
from pathlib import Path

from .candidates import LEVERAGED_FILE, load_leveraged

HTML = Path(__file__).resolve().parent / "wheel_calculator.html"
BLOCK = re.compile(r'(<script id="leveraged-etfs" type="application/json">)(.*?)(</script>)', re.S)


def embed(html_path: Path = HTML, list_path: Path = LEVERAGED_FILE) -> int:
    tickers = sorted(load_leveraged(list_path))
    text = html_path.read_text(encoding="utf-8")
    new, n = BLOCK.subn(lambda m: m.group(1) + json.dumps(tickers) + m.group(3), text)
    if n != 1:
        raise SystemExit(f"Problem: expected one leveraged-etfs block in {html_path.name}, found {n}")
    html_path.write_text(new, encoding="utf-8")
    print(f"Embedded {len(tickers)} tickers from {list_path.name} into {html_path.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(embed())
