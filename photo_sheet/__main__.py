import argparse
import sys
from pathlib import Path

from .presets import embed, head_percent, load_presets, sheet_layout, test_face_png, with_pixels

HERE = Path(__file__).resolve().parent


def show_presets(presets: list[dict]) -> str:
    out = ["PHOTO PRESETS (verify every figure with the body that will receive the photo)", "=" * 78,
           f"{'Preset':<34}{'mm':>14}{'px @ dpi':>16}{'head %':>12}"]
    for p in presets:
        p = with_pixels(p)
        hp = head_percent(p)
        head = f"{hp[0]:.0f}-{hp[1]:.0f}%" if hp else "none"
        out.append(f"{p['name']:<34}{p['width_mm']:g} x {p['height_mm']:g}".ljust(48)
                   + f"{p['width_px']} x {p['height_px']} @ {p['dpi']}".rjust(16) + f"{head:>12}")
    out += ["", "4 x 6 in print sheet at 300 dpi (1200 x 1800 px), copies that fit:"]
    for p in presets:
        p = with_pixels(p)
        lay = sheet_layout(p["width_px"], p["height_px"])
        out.append(f"   {p['name']:<34}{lay['copies']} copies ({lay['cols']} across x {lay['rows']} down)")
    out += ["", "Sources:"] + [f"   {p['name']}: {p['source']}" for p in presets]
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="photo_sheet",
                                description="Helpers for photo_sheet.html (the page itself needs no Python).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("presets", help="print the preset table and print-sheet layout")
    e = sub.add_parser("embed", help="copy presets.json into the page's <script id=presets> block")
    e.add_argument("--html", default=str(HERE / "photo_sheet.html"))
    e.add_argument("--presets", default=str(HERE / "presets.json"))
    t = sub.add_parser("testface", help="write a synthetic test picture (an oval, not a person)")
    t.add_argument("out", help="PNG file to write")
    t.add_argument("--size", default="480x640", help="WIDTHxHEIGHT in pixels, both at least 1")
    args = p.parse_args(argv)

    try:
        if args.cmd == "presets":
            print(show_presets(load_presets(HERE / "presets.json")))
        elif args.cmd == "embed":
            html_path = Path(args.html)
            html = html_path.read_text(encoding="utf-8")
            new = embed(html, load_presets(Path(args.presets)))
            html_path.write_text(new, encoding="utf-8", newline="\n")
            print(f"Preset block {'updated' if new != html else 'already current'} in {html_path}")
        elif args.cmd == "testface":
            w, h = (int(x) for x in args.size.lower().split("x"))
            if w < 1 or h < 1:
                raise ValueError("size must be WIDTHxHEIGHT with both at least 1")
            data = test_face_png(w, h)
            Path(args.out).write_bytes(data)
            print(f"Wrote {args.out} ({w} x {h} px, {len(data):,} bytes). It is a drawn oval, not a photo.")
    except (OSError, ValueError, KeyError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
