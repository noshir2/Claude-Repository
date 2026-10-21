"""Checks for taal_trainer: the taal table embedded in taal_trainer.html and check.py.

Every expected value below was worked out by hand from the taal tables (see the
"Where the rules/figures come from" section of taal_trainer/README.md).
"""
import json
import re
from pathlib import Path

import pytest

from taal_trainer import check

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "taal_trainer" / "taal_trainer.html"
JSON_PATH = ROOT / "taal_trainer" / "taals.json"

# The seven required taals and their matra counts, plus the three extras.
KNOWN_MATRAS = {"Teentaal": 16, "Ektaal": 12, "Jhaptaal": 10, "Rupak": 7, "Dadra": 6, "Keherwa": 8,
                "Chautaal": 12, "Deepchandi": 14, "Tilwada": 16, "Jhoomra": 14}


@pytest.fixture(scope="module")
def html():
    return HTML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def data(html):
    return check.load_taals(html)


@pytest.fixture(scope="module")
def by_name(data):
    return {t["name"]: t for t in data["taals"]}


def test_block_is_found_with_a_regex_and_parses(html, data):
    m = re.search(r'<script id="taal-data" type="application/json">(.*?)</script>', html, re.S)
    assert m and json.loads(m.group(1)) == data
    assert len(data["taals"]) == 10
    names = [t["name"] for t in data["taals"]]
    assert len(names) == len(set(names)), "duplicate taal names"
    assert set(names) == set(KNOWN_MATRAS)


def test_every_taal_is_internally_consistent(data):
    for t in data["taals"]:
        assert check.check_taal(t) == [], t["name"]
        assert sum(t["vibhags"]) == t["matras"]
        assert len(t["bols"]) == t["matras"]
        assert t["sam"] == 1
        starts = check.vibhag_starts(t)
        for m in t["taali"] + t["khali"]:
            assert 1 <= m <= t["matras"]
            assert m in starts, f"{t['name']}: {m} is not the first matra of a vibhag"
        assert not set(t["taali"]) & set(t["khali"])
        assert t["status"] in ("standard", "standard-but-confirm")
    assert check.check_data(data) == []


def test_known_matra_counts(by_name):
    for name, n in KNOWN_MATRAS.items():
        assert by_name[name]["matras"] == n, name


def test_vibhag_starts():
    # Jhaptaal 2+3+2+3: vibhags begin at 1, 1+2=3, 3+3=6, 6+2=8
    assert check.vibhag_starts({"vibhags": [2, 3, 2, 3]}) == [1, 3, 6, 8]
    # Teentaal 4+4+4+4 -> 1, 5, 9, 13
    assert check.vibhag_starts({"vibhags": [4, 4, 4, 4]}) == [1, 5, 9, 13]


def test_structures_match_the_source_tables(by_name):
    # (vibhags, taali, khali) exactly as in the taal summary table
    expect = {
        "Teentaal": ([4, 4, 4, 4], [1, 5, 13], [9]),
        "Ektaal": ([2, 2, 2, 2, 2, 2], [1, 5, 9, 11], [3, 7]),
        "Jhaptaal": ([2, 3, 2, 3], [1, 3, 8], [6]),
        "Rupak": ([3, 2, 2], [4, 6], [1]),
        "Dadra": ([3, 3], [1], [4]),
        "Keherwa": ([4, 4], [1], [5]),
        "Chautaal": ([2, 2, 2, 2, 2, 2], [1, 5, 9, 11], [3, 7]),   # 2x6 school; 4+4+2+2 noted in its note
        "Deepchandi": ([3, 4, 3, 4], [1, 4, 11], [8]),
        "Tilwada": ([4, 4, 4, 4], [1, 5, 13], [9]),
        "Jhoomra": ([3, 4, 3, 4], [1, 4, 11], [8]),
    }
    for name, (vib, taali, khali) in expect.items():
        t = by_name[name]
        assert (t["vibhags"], sorted(t["taali"]), sorted(t["khali"])) == (vib, taali, khali), name


def test_marker_rows_hand_worked(by_name):
    def row(name):
        return " ".join(x or "." for x in check.marker_row(by_name[name]))
    # Teentaal: X at 1, taali 5 -> "2", khali 9 -> "0", taali 13 -> "3"
    assert row("Teentaal") == "X . . . 2 . . . 0 . . . 3 . . ."
    # Ektaal: X 0 2 0 3 4 on matras 1 3 5 7 9 11 (taali 5, 9, 11 numbered 2, 3, 4)
    assert row("Ektaal") == "X . 0 . 2 . 0 . 3 . 4 ."
    assert row("Jhaptaal") == "X . 2 . . 0 . 3 . ."
    # Rupak: matra 1 is sam AND khali, so it shows 0 (not X); taali at 4 and 6 are 2 and 3
    assert row("Rupak") == "0 . . 2 . 3 ."
    assert row("Dadra") == "X . . 0 . ."
    assert row("Keherwa") == "X . . . 0 . . ."
    assert row("Chautaal") == "X . 0 . 2 . 0 . 3 . 4 ."
    assert row("Deepchandi") == "X . . 2 . . . 0 . . 3 . . ."


def test_rupak_sam_is_khali(by_name):
    r = by_name["Rupak"]
    assert r["sam"] == 1 and 1 in r["khali"] and 1 not in r["taali"]
    assert check.marker_row(r)[0] == "0"
    assert r["bols"] == ["Tin", "Tin", "Na", "Dhin", "Na", "Dhin", "Na"]


def test_bols_of_the_core_taals(by_name):
    assert by_name["Teentaal"]["bols"] == ("Dha Dhin Dhin Dha Dha Dhin Dhin Dha Dha Tin Tin Ta Ta Dhin Dhin Dha").split()
    assert by_name["Jhaptaal"]["bols"] == "Dhin Na Dhin Dhin Na Tin Na Dhin Dhin Na".split()
    assert by_name["Dadra"]["bols"] == "Dha Dhin Na Dha Tin Na".split()
    assert by_name["Keherwa"]["bols"] == "Dha Ge Na Ti Na Ka Dhin Na".split()
    assert by_name["Ektaal"]["bols"] == "Dhin Dhin Dhage Tirakita Tu Na Kat Ta Dhage Tirakita Dhin Na".split()
    assert by_name["Chautaal"]["bols"] == "Dha Dha Din Ta Kita Dha Din Ta Tita Kata Gadi Gana".split()


def test_variable_thekas_are_labelled_confirm(by_name):
    for name in ("Ektaal", "Chautaal", "Deepchandi", "Tilwada", "Jhoomra"):
        assert by_name[name]["status"] == "standard-but-confirm", name
    assert "4+4+2+2" in by_name["Chautaal"]["note"]


def test_required_notes_and_no_network(html, data):
    assert "Thekas vary by teacher and gharana" in html
    assert "Thekas vary by teacher and gharana" in data["note"]
    assert "confirm with your teacher" in html
    assert not re.search(r"""(src|href)\s*=\s*["']\s*https?:""", html), "page must not load anything from the web"
    assert "fetch(" not in html and "XMLHttpRequest" not in html and "<link" not in html
    assert "silent switch" in html                      # iOS hint
    assert "AudioContext" in html and "currentTime" in html


def test_json_file_matches_embedded_block(data):
    assert json.loads(JSON_PATH.read_text(encoding="utf-8")) == data


def test_embed_round_trip(html, data):
    out = check.embed(html, data)
    assert check.load_taals(out) == data
    assert out.count('<script id="taal-data"') == 1
    with pytest.raises(ValueError):
        check.embed("<html>no block</html>", data)


def good():
    return {"name": "Demo", "status": "standard", "matras": 6, "vibhags": [3, 3], "sam": 1,
            "taali": [1], "khali": [4], "bols": ["a", "b", "c", "d", "e", "f"]}


def test_validator_catches_each_kind_of_mistake():
    assert check.check_taal(good()) == []
    t = good(); t["vibhags"] = [3, 4]                      # adds to 7, not 6
    assert any("add up to 7" in p for p in check.check_taal(t))
    t = good(); t["bols"] = t["bols"][:5]                  # 5 bols for 6 matras
    assert any("5 bols" in p for p in check.check_taal(t))
    t = good(); t["khali"] = [5]                           # 5 is not a vibhag start (1 or 4)
    assert any("not the first matra" in p for p in check.check_taal(t))
    t = good(); t["taali"] = [1, 7]                        # outside 1..6
    assert any("outside 1..6" in p for p in check.check_taal(t))
    t = good(); t["khali"] = [1]                           # 1 is both taali and khali
    assert any("both taali and khali" in p for p in check.check_taal(t))
    t = good(); t["sam"] = 2
    assert any("sam must be matra 1" in p for p in check.check_taal(t))
    t = good(); del t["bols"]
    assert any("missing field 'bols'" in p for p in check.check_taal(t))
    t = good(); t["status"] = "maybe"
    assert any("status" in p for p in check.check_taal(t))
    t = good(); t["vibhags"] = [3, 3, 0]                    # still adds to 6, but a 0-size vibhag
    assert any("vibhag size must be a whole number of 1 or more" in p for p in check.check_taal(t))
    t = good(); t["vibhags"] = [3, 4, -1]
    assert any("vibhag size" in p for p in check.check_taal(t))
    t = good(); t["name"] = " "
    assert any("empty name" in p for p in check.check_taal(t))
    t = good(); t["sam"] = True                            # True == 1 in Python, still not a matra number
    assert any("sam must be matra 1" in p for p in check.check_taal(t))
    # shape slips: a list typed as text or a number, a bool position; plain sentences, no traceback
    t = good(); t["vibhags"] = "3,3"
    assert any("vibhags must be a list" in p for p in check.check_taal(t))
    t = good(); t["taali"] = 1
    assert any("taali must be a list" in p for p in check.check_taal(t))
    t = good(); t["khali"] = [[4]]
    assert any("khali position [4] is outside 1..6" in p for p in check.check_taal(t))
    t = good(); t["matras"] = "6"
    assert any("matras must be a whole number" in p for p in check.check_taal(t))


def test_validator_catches_table_level_mistakes():
    note = check.REQUIRED_NOTE
    d = {"note": note, "taals": [good(), good()]}
    assert any("duplicate taal names: Demo" in p for p in check.check_data(d))
    d = {"note": "", "taals": [good()]}
    assert any("must contain" in p for p in check.check_data(d))
    rupak = good(); rupak.update(name="Rupak", matras=7, vibhags=[3, 2, 2], taali=[1, 4, 6], khali=[],
                                 bols=list("abcdefg"))                      # X on matra 1: wrong
    assert any("Rupak: matra 1 must be in khali" in p for p in check.check_data({"note": note, "taals": [rupak]}))
    with pytest.raises(ValueError, match="taal number 2 is not an object"):
        check.check_shape({"note": note, "taals": [good(), 5]})
    with pytest.raises(ValueError, match='"taals" list'):
        check.check_shape({"taals": {}})


def test_load_taals_gives_plain_errors():
    with pytest.raises(ValueError, match="no <script"):
        check.load_taals("<html></html>")
    bad = '<script id="taal-data" type="application/json">{"taals": [1,]}</script>'
    with pytest.raises(ValueError, match="missing comma or quote"):
        check.load_taals(bad)


def test_cli(capsys, tmp_path, html):
    assert check.main([]) == 0
    assert capsys.readouterr().out.strip() == "taal data OK: 10 taals"
    broken = tmp_path / "t.html"
    broken.write_text(html.replace('"matras": 16,', '"matras": 15,', 1), encoding="utf-8")
    assert check.main(["--html", str(broken)]) == 1
    err = capsys.readouterr().err
    assert "Problem: Teentaal" in err and "16 bols listed but the taal has 15 matras" in err
    assert check.main(["--html", str(tmp_path / "missing.html")]) == 1
    assert capsys.readouterr().err.startswith("Problem:")
    # --embed rewrites the block from a JSON file and the result validates
    j = tmp_path / "taals.json"
    j.write_text(json.dumps({"note": check.REQUIRED_NOTE, "taals": [good()]}), encoding="utf-8")
    assert check.main(["--html", str(broken), "--json", str(j), "--embed"]) == 0
    assert "taal data OK: 1 taals" in capsys.readouterr().out
    assert check.load_taals(broken.read_text(encoding="utf-8"))["taals"][0]["name"] == "Demo"


def test_cli_embed_refuses_bad_json_without_a_traceback(capsys, tmp_path, html):
    """Every shape slip a Notepad user can make ends in 'Problem: ...' and leaves the HTML as it was."""
    page = tmp_path / "t.html"
    page.write_text(html, encoding="utf-8")
    j = tmp_path / "taals.json"
    bad = [
        '{"taals": []}',                                                       # no top-level note
        '{"note": "%s", "taals": [5]}' % check.REQUIRED_NOTE,                  # entry is not an object
        '{"note": "%s", "taals": [%s]}' % (check.REQUIRED_NOTE,
                                           json.dumps(dict(good(), vibhags="3,3"))),   # list typed as text
        '{"note": "%s", "taals": [%s]}' % (check.REQUIRED_NOTE,
                                           json.dumps(dict(good(), taali=1))),
        '[1, 2]',                                                              # not even an object
        '{"note": "%s", "taals": [%s]}' % (check.REQUIRED_NOTE,
                                           json.dumps(dict(good(), vibhags=[3, 3, 0]))),
    ]
    for text in bad:
        j.write_text(text, encoding="utf-8")
        assert check.main(["--html", str(page), "--json", str(j), "--embed"]) == 1, text
        out = capsys.readouterr()
        assert out.err.startswith("Problem:") and "Traceback" not in out.err, text
        assert out.out == "", text
        assert page.read_text(encoding="utf-8") == html, "the HTML must be left alone: " + text
    # a good file saved as "UTF-8 with BOM" (a Windows Notepad option) is accepted
    j.write_text(json.dumps({"note": check.REQUIRED_NOTE, "taals": [good()]}), encoding="utf-8-sig")
    assert check.main(["--html", str(page), "--json", str(j), "--embed"]) == 0
    assert "taal data OK: 1 taals" in capsys.readouterr().out


# ---- the page itself, in a headless browser (skipped when Playwright/Chromium is not installed) ----

@pytest.fixture(scope="module")
def page_factory():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            try:
                browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
            except Exception as e:  # no browser on this machine
                pytest.skip(f"no headless Chromium: {e}")

        def make(width=375, block_audio=False, path=HTML_PATH):
            ctx = browser.new_context(viewport={"width": width, "height": 800})
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            if block_audio:
                page.add_init_script("window.AudioContext = undefined; window.webkitAudioContext = undefined;")
            page.goto(Path(path).as_uri())
            page.wait_for_timeout(200)
            return page, errors

        yield make
        browser.close()


def test_page_runs_muted_without_errors_at_phone_width(page_factory):
    page, errors = page_factory(width=375, block_audio=True)
    assert page.evaluate("document.documentElement.scrollWidth") <= 375, "horizontal overflow at 375px"
    tt = "window.TaalTrainer"
    rupak = page.evaluate(f"(() => {{ const t = {tt}.taals.find(t => t.name === 'Rupak');"
                          f" return [{tt}.markerFor(t, 1), {tt}.soundFor(t, 1), {tt}.markerFor(t, 4)]; }})()")
    assert rupak == ["0", "khali", "2"]        # the JS agrees with check.py: Rupak's sam is a wave
    ektaal = page.evaluate(f"(() => {{ const t = {tt}.taals.find(t => t.name === 'Ektaal');"
                           f" return Array.from({{length: 12}}, (_, i) => {tt}.markerFor(t, i + 1)); }})()")
    assert ektaal == ["X", "", "0", "", "2", "", "0", "", "3", "", "4", ""]
    assert page.evaluate(f"[59, 60, 119, 120].map({tt}.layaLabel)") == [
        "vilambit (slow)", "madhya (medium)", "madhya (medium)", "drut (fast)"]
    # 4 taps 500 ms apart = 120 per minute; a 5 s gap is ignored; 100 ms gaps clamp to 300
    assert page.evaluate(f"[{tt}.bpmFromTaps([0, 500, 1000, 1500]), {tt}.bpmFromTaps([0, 5000]), {tt}.bpmFromTaps([0, 100])]") == [120, None, 300]
    # Keherwa (8 matras) at 300/min, loop 2 cycles: 16 matras x 0.2 s = 3.2 s then it stops by itself
    page.select_option("#taal", label="Keherwa (8)")
    page.evaluate("document.getElementById('bpm').value = 300; document.getElementById('bpm').dispatchEvent(new Event('input'))")
    page.fill("#loop", "2")
    page.click("#startstop")
    page.wait_for_timeout(600)
    assert page.evaluate(f"{tt}.state.running") is True
    assert page.evaluate(f"{tt}.state.clock") == "perf"            # audio blocked -> visual beat still runs
    assert page.is_visible("#hint-blocked")
    assert page.evaluate("document.querySelectorAll('.cell.now').length") == 1
    assert page.text_content("#r-where").startswith("matra ")
    page.wait_for_timeout(3400)
    assert page.evaluate(f"{tt}.state.running") is False
    assert page.text_content("#startstop") == "Start"
    assert page.text_content("#startstop-top") == "Start"                 # the second copy of the button mirrors it
    assert page.text_content("#r-cycle").startswith("Stopped after 2 cycles, on the sam.")   # a loop that ran out says so
    key = page.evaluate(f"'taal_trainer.minutes.' + {tt}.dateKey()")
    assert page.evaluate(f"localStorage.getItem('{key}')") is not None
    assert all(k.startswith("taal_trainer.") for k in page.evaluate("Object.keys(localStorage)"))
    assert errors == []


def test_minutes_do_not_count_time_away(page_factory):
    """Locked phone / hidden tab: the beat is not running, so 'Today' must not grow."""
    page, errors = page_factory(block_audio=True)
    tt = "window.TaalTrainer"
    page.click("#startstop")
    page.wait_for_timeout(300)
    # iOS freezes all JS while locked and may not fire visibilitychange first: a stale lastTick of
    # 10 minutes ago must be ignored (it used to add 600 s in one frame -> 'Today: 10 min')
    page.evaluate(f"{tt}.state.lastTick = performance.now() - 600000; {tt}.state.lastSave = 0")
    page.wait_for_timeout(200)
    assert page.text_content("#today-min") == "0"
    assert page.evaluate(f"{tt}.state.secToday") < 2
    # a hidden page stops the count; coming back starts it again from that moment
    page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});"
                  " document.dispatchEvent(new Event('visibilitychange'))")
    assert page.evaluate(f"{tt}.state.lastTick") == 0
    before = page.evaluate(f"{tt}.state.secToday")
    page.wait_for_timeout(400)
    assert page.evaluate(f"{tt}.state.secToday") == before
    page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});"
                  " document.dispatchEvent(new Event('visibilitychange'))")
    assert page.evaluate(f"{tt}.state.lastTick") > 0
    page.wait_for_timeout(400)
    assert 0.2 < page.evaluate(f"{tt}.state.secToday") - before < 1.0
    page.click("#startstop")
    assert errors == []


def test_hide_after_n_wins_over_hide_bols(page_factory):
    """Both set: N cycles with the words first, then hidden (they used to be hidden from matra 1)."""
    page, errors = page_factory(block_audio=True)
    page.check("#hidebols")
    page.fill("#hideafter", "3")
    page.evaluate("TaalTrainer.state.running = true")   # applyHiding only looks at the cycle number
    for cycle, hidden in ((1, False), (3, False), (4, True)):
        page.evaluate(f"document.getElementById('hideafter').value = 3;"
                      f" TaalTrainer.applyHiding({cycle})")
        assert page.evaluate("document.body.classList.contains('hidden-bols')") is hidden, cycle
    page.fill("#hideafter", "0")
    page.evaluate("TaalTrainer.applyHiding(1)")
    assert page.evaluate("document.body.classList.contains('hidden-bols')") is True
    assert errors == []


def test_broken_taal_table_shows_a_message_not_a_blank_page(page_factory, tmp_path, html):
    broken = tmp_path / "broken.html"
    broken.write_text(html.replace('"matras": 16,', '"matras": 16', 1), encoding="utf-8")   # a lost comma
    page, errors = page_factory(block_audio=True, path=broken)
    note = page.text_content("#taalnote")
    assert note.startswith("The taal table at the top of this file has a mistake")
    assert "taal_trainer.check" in note
    assert page.is_disabled("#startstop") and page.is_disabled("#startstop-top")
    assert page.text_content("#r-where") == "Taal table has a mistake"
    assert errors == [], "the slip is reported on the page, not thrown"


# ---- first-time-user contract: no browser pop-ups, back link, privacy line, theme blocks ----
def test_page_meets_first_time_user_contract(html):
    assert not re.search(r"\b(alert|confirm|prompt)\(", html)           # confirmations live on the page
    assert 'href="../index.html"' in html and "Back to the toolbox" in html
    assert "Nothing you type or choose leaves your device." in html
    assert re.search(r":root\s*\{[^}]*--bg:", html)
    assert re.search(r'@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{[^}]*color-scheme:\s*dark', html)
    assert re.search(r':root\[data-theme="dark"\]\s*\{[^}]*color-scheme:\s*dark', html)
    assert re.search(r"html,\s*body\s*\{[^}]*background:\s*var\(--bg\)", html)
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", html)
    assert "env(safe-area-inset-left, 0px)" in html and "env(safe-area-inset-right, 0px)" in html
    assert 'id="start-hint"' in html and "Press Start" in html
    assert 'id="startstop-top"' in html                                 # a Start button under the steps, before the taal card
    assert "<summary>What the words mean</summary>" in html             # the gloss paragraph folds away on a phone
    for word in ("matra [", "vibhag [", "sam [", "taali [", "khali [", "laya [", "theka [", "padhant ["):
        assert word in html, word                                       # each term glossed in plain words


# ---- review fixes: plain-word labels, and count boxes that show what the page uses ----
def test_review_fixes_in_the_page_text(html):
    assert "Hide the words (bols)" in html                                   # the page's own word first, bol in brackets
    assert 'class="tempolabel"' in html and "<b>Tempo</b>" in html          # the tempo card is named
    assert "function clampCount" in html


def test_start_button_is_on_the_first_phone_screen_and_scrolls_to_the_beat(page_factory):
    """Round-3 review: the only green button used to be two screens down on a phone."""
    page, errors = page_factory(width=375, block_audio=True)
    top = page.evaluate("document.getElementById('startstop-top').getBoundingClientRect()")
    assert 0 <= top["top"] and top["bottom"] <= 800, top                 # visible without scrolling at 375x800
    assert page.evaluate("window.scrollY") == 0
    page.click("#startstop-top")
    page.wait_for_timeout(1200)                                          # smooth scroll settles
    assert page.evaluate("window.TaalTrainer.state.running") is True
    assert page.text_content("#startstop-top") == "Stop" and page.text_content("#startstop") == "Stop"
    assert page.evaluate("document.getElementById('startstop-top').classList.contains('on')")
    r = page.evaluate("document.getElementById('readout').getBoundingClientRect()")
    assert r["top"] >= -1 and r["bottom"] <= 800, r                      # the readout (and the grid under it) came on screen
    assert page.text_content("#r-where").startswith("matra ")
    page.click("#startstop")                                             # either button stops it
    assert page.text_content("#startstop-top") == "Start"
    assert page.evaluate("window.TaalTrainer.state.running") is False
    assert errors == []


def test_negative_loop_and_hide_after_are_written_back_as_zero(page_factory):
    page, errors = page_factory(width=375, block_audio=True)
    page.fill("#loop", "-4")
    page.dispatch_event("#loop", "change")
    assert page.input_value("#loop") == "0"
    page.fill("#hideafter", "-1")
    page.dispatch_event("#hideafter", "change")
    assert page.input_value("#hideafter") == "0"
    page.fill("#loop", "2")
    page.click("#startstop")
    assert page.evaluate("window.TaalTrainer.state.loopN") == 2
    page.click("#startstop")
    assert errors == []
