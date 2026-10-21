"""Checks for photo_sheet. The browser side (EXIF rotation, canvas.toBlob) cannot run under pytest;
these tests cover the preset maths, the embedded JSON block, the print-sheet grid, the synthetic
test image, and the promises the page makes in its text."""
import json
import re
import struct
import zlib
from pathlib import Path

import pytest

from photo_sheet.__main__ import main
from photo_sheet.presets import (embed, embedded_block, head_percent, load_presets, mm_to_px,
                                 px_to_mm, sheet_layout, with_pixels)
from photo_sheet.presets import test_face_png as face_png

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "photo_sheet" / "photo_sheet.html").read_text(encoding="utf-8")
README = (ROOT / "photo_sheet" / "README.md").read_text(encoding="utf-8")
PRESETS = load_presets(ROOT / "photo_sheet" / "presets.json")


def test_mm_to_px_hand_worked():
    # 50.8 mm * 300 / 25.4 = 600 exactly (2 inches at 300 dpi)
    assert mm_to_px(50.8, 300) == 600
    # 35 * 300 / 25.4 = 413.39 -> 413 ; 45 * 300 / 25.4 = 531.50 -> 531 (round half to even on .496 is moot: 531.496)
    assert mm_to_px(35, 300) == 413
    assert mm_to_px(45, 300) == 531
    # 35 mm at 600 dpi = 826.77 -> 827
    assert mm_to_px(35, 600) == 827
    # back the other way: 600 px at 300 dpi = 50.8 mm
    assert px_to_mm(600, 300) == pytest.approx(50.8)


def test_presets_block_parses_with_expected_sizes():
    block = json.loads(embedded_block(HTML))
    names = {p["name"]: p for p in block}
    assert names["US 2x2 in"]["width_px"] == 600 and names["US 2x2 in"]["height_px"] == 600
    intl = names["35x45 mm (common international)"]
    assert (intl["width_px"], intl["height_px"]) == (413, 531)
    assert len(block) >= 3
    for p in block:
        # the pixel figures in the block must match mm x dpi / 25.4 within 1 px
        assert abs(p["width_px"] - p["width_mm"] * p["dpi"] / 25.4) <= 1
        assert abs(p["height_px"] - p["height_mm"] * p["dpi"] / 25.4) <= 1
        assert "verify with the issuing body" in p["source"]
    # the block is exactly what presets.json gives (so editing the JSON and running `embed` is enough)
    assert block == [with_pixels(p) for p in PRESETS]


def test_head_percent():
    # US: 25 / 50.8 = 49.2 %, 35 / 50.8 = 68.9 %
    lo, hi = head_percent(with_pixels(PRESETS[0]))
    assert lo == pytest.approx(49.21, abs=0.01)
    assert hi == pytest.approx(68.90, abs=0.01)
    assert head_percent(PRESETS[1]) is None            # 35x45 carries no head rule on purpose


def test_us_preset_guides_match_the_published_inch_figures():
    us = PRESETS[0]
    # 1 in = 25.4 mm, 1 3/8 in = 34.925 mm; eyes 1 1/8 in = 28.575 mm to 1 3/8 in = 34.925 mm from the bottom
    assert us["head_min_mm"] == 25 and us["head_max_mm"] == 35
    assert us["eye_min_mm_from_bottom"] == pytest.approx(28.575, abs=0.05)
    assert us["eye_max_mm_from_bottom"] == pytest.approx(34.925, abs=0.05)


def test_sheet_layout_six_two_by_two():
    # 600 x 600 cells on 1200 x 1800: 2 across, 3 down, no margin -> origins at 0/600 x 0/600/1200
    lay = sheet_layout(600, 600)
    assert (lay["cols"], lay["rows"], lay["copies"]) == (2, 3, 6)
    assert (lay["margin_x"], lay["margin_y"]) == (0, 0)
    assert lay["cells"] == [(0, 0), (600, 0), (0, 600), (600, 600), (0, 1200), (600, 1200)]


def test_sheet_layout_35x45_and_edge_cases():
    # 413 x 531: grid 826 x 1593; margins (1200-826)/2 = 187, (1800-1593)/2 = 103.5 -> 103
    lay = sheet_layout(413, 531)
    assert (lay["cols"], lay["rows"], lay["copies"], lay["margin_x"], lay["margin_y"]) == (2, 3, 6, 187, 103)
    assert lay["cells"][0] == (187, 103) and lay["cells"][5] == (187 + 413, 103 + 2 * 531)
    # 2-per-sheet layout: 2 across, 1 down, margin_y = (1800-531)/2 = 634
    two = sheet_layout(413, 531, copies=2)
    assert (two["cols"], two["rows"], two["copies"], two["margin_y"]) == (2, 1, 2, 634)
    # a 5 x 7 in print (1500 x 2100 px) cannot fit at all
    assert sheet_layout(1500, 2100)["copies"] == 0
    # a 4 x 6 in cell fits exactly once
    assert sheet_layout(1200, 1800)["copies"] == 1


def test_html_is_self_contained():
    # no http(s) or protocol-relative URLs in src/href, no @import, no fetch(), no <link>
    assert not re.search(r'(src|href)\s*=\s*["\']\s*(https?:)?//', HTML, re.I)
    assert "@import" not in HTML
    assert "fetch(" not in HTML
    assert "<link" not in HTML.lower()
    assert "XMLHttpRequest" not in HTML


def test_required_sentences_present():
    assert "Your photo never leaves this browser" in HTML
    assert "The guides help; the issuing body decides." in HTML
    assert "the issuing body decides; check its own rules" in HTML.lower()
    assert "Share, then Save Image" in HTML
    assert "async function fitUnderCap" in HTML             # the quality loop lives here
    assert "being enlarged" in HTML and "enlarged" in README   # a small original gets a soft-picture warning
    assert 'createImageBitmap(file, { imageOrientation: "from-image" })' in HTML
    assert 'accept="image/*"' in HTML
    assert "prefers-color-scheme" in HTML
    assert "browser-dependent" in README.lower() or "depends on the browser" in README.lower()


def test_embed_round_trip():
    html = '<p>x</p><script id="presets" type="application/json">\n[]\n</script><p>y</p>'
    out = embed(html, [{"name": "T", "width_mm": 25.4, "height_mm": 50.8, "dpi": 100}])
    block = json.loads(embedded_block(out))
    assert block == [{"name": "T", "width_mm": 25.4, "height_mm": 50.8, "dpi": 100, "width_px": 100, "height_px": 200}]
    with pytest.raises(ValueError):
        embedded_block("<html></html>")


def test_test_face_png_is_valid_and_synthetic():
    data = face_png(48, 64)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    w, h, depth, ctype = struct.unpack(">IIBB", data[16:26])
    assert (w, h, depth, ctype) == (48, 64, 8, 2)
    # IDAT starts after signature(8) + IHDR chunk(4+4+13+4 = 25) -> at byte 33; length is the first 4 bytes
    n = struct.unpack(">I", data[33:37])[0]
    raw = zlib.decompress(data[41:41 + n])
    assert len(raw) == 64 * (1 + 48 * 3)                   # one filter byte plus RGB per row
    # corner pixel is the grey background, centre pixel is the oval
    assert raw[1:4] == b"\xe4\xe4\xe4"
    mid = 28 * (1 + 48 * 3) + 1 + 24 * 3                   # row 28 (0.45 * 64), column 24
    assert raw[mid:mid + 3] == b"\xd9\xa6\x82"
    sample = ROOT / "samples" / "photo_sheet_test_face.png"
    assert sample.read_bytes() == face_png(480, 640)  # the shipped sample is regenerable


def test_load_presets_accepts_bom_and_refuses_half_set_figures(tmp_path):
    # a BOM (older Windows Notepad default) must not break `embed`
    bom = tmp_path / "bom.json"
    bom.write_bytes(b"\xef\xbb\xbf" + json.dumps(PRESETS).encode("utf-8"))
    assert load_presets(bom) == PRESETS
    # head_min_mm set but head_max_mm null would draw a zero-size oval: refused with the preset and field named
    half = [dict(PRESETS[1], head_min_mm=30)]
    bad = tmp_path / "half.json"
    bad.write_text(json.dumps(half), encoding="utf-8")
    with pytest.raises(ValueError, match="35x45.*head_min_mm"):
        load_presets(bad)
    # a non-positive size is refused too
    bad.write_text(json.dumps([dict(PRESETS[0], width_mm=-5)]), encoding="utf-8")
    with pytest.raises(ValueError, match="width_mm"):
        load_presets(bad)
    # no source line, a repeated name, or an empty list would break the page or the presets command
    nosrc = {k: v for k, v in PRESETS[0].items() if k != "source"}
    for bad_list, why in (([nosrc], "source"), ([PRESETS[0], PRESETS[0]], "twice"), ([], "at least one")):
        bad.write_text(json.dumps(bad_list), encoding="utf-8")
        with pytest.raises(ValueError, match=why):
            load_presets(bad)
    copy = tmp_path / "page.html"
    copy.write_text(HTML, encoding="utf-8", newline="\n")
    assert main(["embed", "--html", str(copy), "--presets", str(bad)]) == 1
    assert copy.read_text(encoding="utf-8") == HTML                # nothing written on refusal


def test_cli(tmp_path, capsys):
    assert main(["presets"]) == 0
    out = capsys.readouterr().out
    assert "600 x 600 @ 300" in out and "413 x 531 @ 300" in out and "49-69%" in out
    assert main(["testface", str(tmp_path / "f.png"), "--size", "32x40"]) == 0
    assert (tmp_path / "f.png").read_bytes() == face_png(32, 40)
    assert main(["testface", str(tmp_path / "g.png"), "--size", "wide"]) == 1
    assert "Problem:" in capsys.readouterr().err
    # 0x0 would be an invalid PNG and a negative size is meaningless: both refused, nothing written
    assert main(["testface", str(tmp_path / "g.png"), "--size", "0x0"]) == 1
    assert main(["testface", str(tmp_path / "g.png"), "--size=-5x10"]) == 1
    assert "at least 1" in capsys.readouterr().err and not (tmp_path / "g.png").exists()
    # embed into a copy of the page leaves it byte-identical (block already current)
    copy = tmp_path / "page.html"
    copy.write_text(HTML, encoding="utf-8", newline="\n")
    assert main(["embed", "--html", str(copy)]) == 0
    assert copy.read_text(encoding="utf-8") == HTML


# --- first-time-user contract: no browser pop-ups, back link, privacy line, theme blocks --------
def test_page_meets_first_time_user_contract():
    assert not re.search(r"\b(alert|confirm|prompt)\(", HTML)           # messages live on the page
    assert 'href="../index.html"' in HTML and "Back to the toolbox" in HTML
    assert "Nothing you type or choose leaves your device." in HTML
    assert re.search(r":root\s*\{[^}]*--bg:", HTML)
    assert re.search(r'@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{[^}]*color-scheme:\s*dark', HTML)
    assert re.search(r':root\[data-theme="dark"\]\s*\{[^}]*color-scheme:\s*dark', HTML)
    assert re.search(r"body\s*\{[^}]*background:\s*var\(--bg\)", HTML)
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", HTML)
    assert "env(safe-area-inset-left, 0px)" in HTML and "env(safe-area-inset-right, 0px)" in HTML
    assert "Try it with a drawn face" in HTML and 'id="testface" class="primary"' in HTML
    assert 'id="jpegimg"' in HTML and 'id="sheetimg"' in HTML           # results shown on the page, not only downloaded
    assert "Press and hold (phone) or right-click (PC) the picture and choose Save" in HTML
    assert "if nothing happens, you are using the online copy" in HTML.lower()
    assert "dpi [" in HTML and "EXIF tag [" in HTML
    # round-3 review: every control has an id, the load error says what to do about phone photo formats,
    # and the file-size error uses the label's own words
    for cid in ("chk-background", "chk-expression", "chk-head", "chk-glasses", "chk-recent", "chk-edits"):
        assert f'id="{cid}"' in HTML, cid
    assert "HEIC" in HTML and "The picture already in the crop box is unchanged." in HTML
    assert "Largest file size must be at least 5 KB." in HTML and "Max KB must be" not in HTML
    assert 'id="sec-crop"' in HTML and "function showCropBox" in HTML


# --- review fixes: the example ends in a green result, the quality number has a meaning, the drawn face is the sample ---
def test_review_fixes_in_the_page_text():
    assert "1.00 is best; the page lowers it only until the file fits under your KB limit" in HTML
    assert "small on purpose" in HTML and "state.drawn" in HTML
    assert "function drawTestFacePixels" in HTML and "window.drawTestFacePixels" in HTML


@pytest.fixture(scope="module")
def photo_page():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            try:
                browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            except Exception as e:
                pytest.skip(f"no headless Chromium: {e}")

        def make(width=375):
            ctx = browser.new_context(viewport={"width": width, "height": 800})
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto((ROOT / "photo_sheet" / "photo_sheet.html").as_uri())
            page.wait_for_timeout(200)
            return page, errors

        yield make
        browser.close()


def test_drawn_face_is_the_sample_png_pixel_for_pixel(photo_page):
    import base64
    page, errors = photo_page(375)
    b64 = base64.b64encode((ROOT / "samples" / "photo_sheet_test_face.png").read_bytes()).decode()
    same = page.evaluate("""async (b64) => {
      const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
      const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
      c.getContext('2d').drawImage(img, 0, 0);
      const a = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      const d = window.drawTestFacePixels(img.width, img.height);
      const b = d.getContext('2d').getImageData(0, 0, d.width, d.height).data;
      if (a.length !== b.length) return 'size differs';
      let diff = 0; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) diff++;
      return diff === 0 ? 'same' : diff + ' bytes differ';
    }""", b64)
    assert same == "same"
    assert errors == []


def test_first_click_brings_the_crop_box_on_screen_and_a_bad_file_is_explained(photo_page, tmp_path):
    """Round-3 review: on a phone the drawn face used to load two screens below the button."""
    page, errors = photo_page(375)
    assert page.evaluate("document.getElementById('view').getBoundingClientRect().top") > 800   # starts below the fold
    page.click("#testface")
    page.wait_for_timeout(1200)                                          # smooth scroll settles
    r = page.evaluate("document.getElementById('view').getBoundingClientRect()")
    assert r["top"] >= 0 and r["bottom"] <= 800, r                       # the face is on screen after the first click
    assert page.evaluate("[...document.querySelectorAll('input,select,textarea,button')].filter(e => !e.id).length") == 0
    empty = tmp_path / "empty.jpg"
    empty.write_bytes(b"")
    page.set_input_files("#file", str(empty))
    page.wait_for_function("document.getElementById('loadinfo').textContent.startsWith('Could not read')")
    msg = page.text_content("#loadinfo")
    assert "HEIC" in msg and msg.endswith("The picture already in the crop box is unchanged.")
    assert page.is_enabled("#savejpeg")                                  # the drawn face is still there to save
    page.fill("#maxkb", "-1")
    page.click("#savejpeg")
    assert page.text_content("#jpegstatus") == "Largest file size must be at least 5 KB."
    # PC width: the crop box sits beside the controls in the top row, and is wholly on screen after the click
    page, errors2 = photo_page(1100)
    page.click("#testface")
    page.wait_for_timeout(1200)
    r = page.evaluate("document.getElementById('view').getBoundingClientRect()")
    assert r["top"] >= 0 and r["bottom"] <= 800 and r["left"] > 500, r
    assert errors == [] and errors2 == []


def test_example_click_ends_in_a_green_result_and_a_real_small_file_still_warns(photo_page):
    page, errors = photo_page(375)
    page.click("#testface")
    assert "480 x 640" in page.text_content("#loadinfo")
    page.click("#savejpeg")
    page.wait_for_function("document.getElementById('jpegstatus').textContent.startsWith('Made')")
    status = page.text_content("#jpegstatus")
    assert page.get_attribute("#jpegstatus", "class") == "status ok"
    assert "small on purpose" in status and "being enlarged" not in status
    assert page.evaluate("document.getElementById('jpegimg').src.startsWith('data:image/jpeg')")
    # the same picture chosen as a file is a real photo as far as the page knows: the enlarging note comes back
    page.set_input_files("#file", str(ROOT / "samples" / "photo_sheet_test_face.png"))
    page.wait_for_function("document.getElementById('loadinfo').textContent.includes('480 x 640')")
    page.click("#savejpeg")
    page.wait_for_function("document.getElementById('jpegstatus').textContent.startsWith('Made 600')")
    assert "being enlarged" in page.text_content("#jpegstatus")
    assert page.get_attribute("#jpegstatus", "class") == "status warn"
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    assert errors == []
