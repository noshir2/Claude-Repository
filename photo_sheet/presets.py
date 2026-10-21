"""Pure helpers behind the photo page: mm/px maths, the embedded preset block, the print-sheet grid,
and a synthetic test-face PNG (no real photos). No browser code here; the page does the cropping."""
import json
import re
import struct
import zlib
from pathlib import Path

MM_PER_INCH = 25.4
SHEET_W, SHEET_H = 1200, 1800        # 4 x 6 in at 300 dpi
BLOCK_RE = re.compile(r'(<script id="presets" type="application/json">)(.*?)(</script>)', re.S)


def mm_to_px(mm: float, dpi: float) -> int:
    """Pixels for a physical length at a print resolution, rounded to the nearest whole pixel."""
    return round(mm * dpi / MM_PER_INCH)


def px_to_mm(px: float, dpi: float) -> float:
    return px * MM_PER_INCH / dpi


def validate_presets(presets: list[dict]) -> list[dict]:
    """Refuse a preset the page could not draw or the README could not vouch for: at least one preset,
    unique names, a source line, positive sizes, and the head (and eye) figures both set or both null.
    Raises ValueError naming the preset and the field."""
    if not isinstance(presets, list):
        raise ValueError("presets.json must hold a list of presets")
    if not presets:
        raise ValueError("presets.json must hold at least one preset")
    seen = set()
    for p in presets:
        name = p.get("name") if isinstance(p, dict) else None
        if not name:
            raise ValueError("every preset needs a name")
        if name in seen:
            raise ValueError(f"preset {name!r}: the name is used twice")
        seen.add(name)
        if not isinstance(p.get("source"), str) or not p["source"].strip():
            raise ValueError(f"preset {name!r}: source must say where the figures come from")
        for field in ("width_mm", "height_mm", "dpi"):
            v = p.get(field)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
                raise ValueError(f"preset {name!r}: {field} must be a positive number")
        for lo, hi in (("head_min_mm", "head_max_mm"), ("eye_min_mm_from_bottom", "eye_max_mm_from_bottom")):
            a, b = p.get(lo), p.get(hi)
            if (a is None) != (b is None):
                raise ValueError(f"preset {name!r}: set both {lo} and {hi}, or leave both null")
            if a is not None and not (0 < a <= b):
                raise ValueError(f"preset {name!r}: {lo} must be positive and not above {hi}")
    return presets


def load_presets(path: Path) -> list[dict]:
    # utf-8-sig also accepts a file saved with a BOM (older Windows Notepad default)
    return validate_presets(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def with_pixels(preset: dict) -> dict:
    """Return a copy with width_px/height_px recomputed from mm and dpi."""
    p = dict(preset)
    p["width_px"] = mm_to_px(p["width_mm"], p["dpi"])
    p["height_px"] = mm_to_px(p["height_mm"], p["dpi"])
    return p


def head_percent(preset: dict) -> tuple[float, float] | None:
    """Head height as a percentage of the photo height (min, max), or None when the preset has no rule."""
    lo, hi = preset.get("head_min_mm"), preset.get("head_max_mm")
    if lo is None or hi is None:
        return None
    return (100 * lo / preset["height_mm"], 100 * hi / preset["height_mm"])


def sheet_layout(cell_w: int, cell_h: int, copies: int = 6) -> dict:
    """Where each copy goes on a 1200 x 1800 sheet: columns, rows, margins and cell origins.
    Copies are capped at what fits; zero means the cell is bigger than the sheet."""
    cols = min(2, SHEET_W // cell_w) if cell_w > 0 else 0
    rows = SHEET_H // cell_h if cell_h > 0 else 0
    n = min(copies, cols * rows)
    if n == 0:
        return {"cols": 0, "rows": 0, "copies": 0, "cells": []}
    cols = min(cols, n)
    rows = -(-n // cols)                       # ceiling division
    mx = (SHEET_W - cols * cell_w) // 2
    my = (SHEET_H - rows * cell_h) // 2
    cells = [(mx + (i % cols) * cell_w, my + (i // cols) * cell_h) for i in range(n)]
    return {"cols": cols, "rows": rows, "copies": n, "margin_x": mx, "margin_y": my, "cells": cells}


def embedded_block(html: str) -> str:
    """The JSON text inside <script id="presets" type="application/json">."""
    m = BLOCK_RE.search(html)
    if not m:
        raise ValueError("no presets block found in the HTML")
    return m.group(2)


def embed(html: str, presets: list[dict]) -> str:
    """Replace the preset block in the page with freshly computed presets."""
    text = "\n" + json.dumps([with_pixels(p) for p in presets], indent=2) + "\n"
    if not BLOCK_RE.search(html):
        raise ValueError("no presets block found in the HTML")
    return BLOCK_RE.sub(lambda m: m.group(1) + text + m.group(3), html, count=1)


def test_face_png(width: int = 480, height: int = 640) -> bytes:
    """A plain synthetic picture: a skin-toned oval with two dark eye dots on a light grey
    background. Drawn pixel by pixel and written as an uncompressed-filter PNG (zlib + struct)."""
    cx, cy = width / 2, height * 0.45
    rx, ry = width * 0.22, height * 0.22
    rows = bytearray()
    for y in range(height):
        rows.append(0)                                      # filter type 0 for this row
        for x in range(width):
            dx, dy = (x - cx) / rx, (y - cy) / ry
            inside = dx * dx + dy * dy <= 1
            eye = inside and abs(dy + 0.15) < 0.08 and abs(abs(dx) - 0.4) < 0.1
            if eye:
                rows += b"\x30\x28\x20"
            elif inside:
                rows += b"\xd9\xa6\x82"
            else:
                rows += b"\xe4\xe4\xe4"

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)   # 8-bit RGB
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))
