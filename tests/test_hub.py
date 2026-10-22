"""Checks for the hub page, index.html at the repo root.

index.html is the artifact main page: it starts with <title>, carries no
doctype/html/head/body tags, links only to files that exist in the repo, loads
nothing from the web, and holds the plain-English glossary and privacy sentence
the UX brief asks for.
"""
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "index.html"

# The hub shows no web address at all: the repo is public and the account name is on the
# private never-commit list, so the download steps point to "the GitHub link that came with
# this toolbox" instead of spelling the address out (or asking the user for a user name).
BRANCH = "claude/lucid-dijkstra-gic3gd"

# Pages the hub promises carry a "Try it with example data" button, and the button the
# photo page has instead.
EXAMPLE_BUTTON_PAGES = ("wheel_planner/wheel.html", "fantasy_helper/fantasy.html", "pdh_log/pdh.html")
PHOTO_BUTTONS = ("Try it with a drawn face", "Choose photo")
SECTION_IDS = ("what", "tools", "how", "copy", "words", "wrong")

TOOL_PAGES = (
    "wheel_planner/wheel.html",
    "fantasy_helper/fantasy.html",
    "frc_shop_card/frc_shop_card.html",
    "taal_trainer/taal_trainer.html",
    "pdh_log/pdh.html",
    "photo_sheet/photo_sheet.html",
)

# The private list of strings that must never appear in the public repo is never
# committed; the test reads it from this environment variable and skips when unset.
FORBIDDEN_ENV = "TOOLBOX_FORBIDDEN_STRINGS"


@pytest.fixture(scope="module")
def html():
    return HUB.read_text(encoding="utf-8")


def _text(html):
    """The page with tags removed and whitespace collapsed, for wording checks."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_file_exists():
    assert HUB.is_file(), "index.html must sit at the repo root"


def test_starts_with_title_then_viewport_meta(html):
    assert html.startswith("<title>Toolbox</title>"), "the file must begin with <title>Toolbox</title>"
    lines = html.splitlines()
    assert lines[1] == '<meta name="claude:viewport-fit-sides" content="cover">'
    # The ordinary viewport meta follows, so the page lays out at phone width when opened as
    # a local file too (the hosted viewer adds one of its own).
    assert lines[2] == '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    assert lines[3].startswith("<style>")


def test_no_document_skeleton_tags(html):
    low = html.lower()
    assert "<!doctype" not in low, "artifact main page must not contain <!doctype"
    for tag in ("html", "head", "body"):
        # <head> and <head ...> are skeleton tags; <header> is an ordinary element.
        assert not re.search(rf"<{tag}[\s>]", low), f"artifact main page must not contain <{tag}>"


def _hrefs(html):
    return re.findall(r'href="([^"]+)"', html)


def test_every_relative_link_points_to_an_existing_file(html):
    missing = []
    for href in _hrefs(html):
        if href.startswith(("http://", "https://", "#", "mailto:", "tel:", "data:")):
            continue
        target = (ROOT / href.split("#")[0]).resolve()
        if not target.is_file():
            missing.append(href)
    assert not missing, f"links to files that do not exist in the repo: {missing}"


def test_links_cover_every_tool_page(html):
    hrefs = set(_hrefs(html))
    for page in TOOL_PAGES:
        assert page in hrefs, f"hub does not link to {page}"


def test_links_open_in_the_same_tab(html):
    # The glossary tells the user the tools open in the same tab, so no link may open a new one.
    assert "target=" not in html.lower()


def test_no_web_resources_or_addresses(html):
    import re as _re
    urls = set(_re.findall(r"https?://[^\s\"'<>]+", html))
    assert urls <= {"https://github.com/noshir2/Claude-Repository"}, f"the hub shows no web address except the public project page: {urls}"
    low = html.lower()
    for tag in ("<script", "<link ", "@import", "url(", "<img", "<iframe"):
        assert tag not in low, f"the hub must not load external resources or run code ({tag})"


def test_step_one_can_be_followed_without_a_github_user_name(html):
    """The high finding from the novice review: step 1 used to show a placeholder address
    and ask for a GitHub user name right after promising no sign-in was needed."""
    text = _text(html)
    assert "YOUR-USER-NAME" not in text, "no placeholder the user has to fill in"
    paths = re.findall(r"github\.com/[\w.-]+/[\w.-]+", text)
    assert paths and set(paths) == {"github.com/noshir2/Claude-Repository"}, "only the public project address may appear"
    m = re.search(r'<h3 id="copy">.*?</ol>', html, re.S)
    steps = [_text(li) for li in re.findall(r"<li>(.*?)</li>", m.group(0), re.S)]
    step1 = steps[0]
    assert "github.com/noshir2/Claude-Repository" in step1, "step 1 shows the public project address"
    assert "no account" in step1, "step 1 says no account is needed"
    intro = _text(html[html.find('<h3 id="copy">'):html.find("<ol>", html.find('<h3 id="copy">'))])
    assert "You do not need to sign in" not in intro, "do not promise no sign-in, then ask for one"
    assert "needs no sign-in" in intro, "say that downloading needs no sign-in"


def test_hub_agrees_with_the_root_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert BRANCH in readme, "README.md must name the same branch as the hub"
    assert "may say main" not in readme.lower(), "the branch button never reads main for this repo"
    assert "may open in a new tab" not in readme.lower(), "tools open in the same tab, as the hub says"


def test_jump_links_reach_every_section(html):
    m = re.search(r'<ul class="jump".*?</ul>', html, re.S)
    assert m, "the row of in-page links under the welcome is missing"
    assert m.start() < html.find('<h2 id="what">'), "the jump links sit above the first section"
    for sid in SECTION_IDS:
        assert f'href="#{sid}"' in m.group(0), f"no jump link to #{sid}"
        assert f'id="{sid}"' in html, f"section #{sid} is missing"
    # every in-page link on the page points at an id that exists
    for frag in set(re.findall(r'href="#([^"]+)"', html)):
        assert f'id="{frag}"' in html, f"in-page link to #{frag} has no target"


def test_csv_mentions_in_cards_link_to_the_glossary(html):
    cards = re.search(r'<div class="cards">.*?</div>\s*<h2', html, re.S).group(0)
    assert cards.count('<a href="#words">.csv</a>') >= 3, "each card that needs a .csv links the word to the glossary"
    assert "(.csv)" not in cards, "a bare (.csv) in a card is not linked"


def test_fantasy_card_says_how_many_files(html):
    card = re.search(r"<h3>Fantasy football</h3>.*?</div>", html, re.S).group(0)
    text = _text(card)
    assert "six weekly projection files" in text and "one per position" in text


def test_flashcards_row_opens_the_flashcards_tab(html):
    rows = re.search(r'<ul class="situations">.*?</ul>', html, re.S).group(0)
    assert 'href="frc_shop_card/frc_shop_card.html#cards">Quiz students' in rows
    assert 'href="frc_shop_card/frc_shop_card.html#rules">Look up a robot wiring rule' in rows
    frc = (ROOT / "frc_shop_card/frc_shop_card.html").read_text(encoding="utf-8")
    for tab in ("cards", "rules"):
        assert f'data-tab="{tab}"' in frc, f"the robotics page has no {tab} tab to land on"
    assert "location.hash" in frc, "the robotics page must pick its tab from the link"


def test_names_match_the_pages_they_open(html):
    text = _text(html)
    wheel_title = re.search(r"<title>(.*?)</title>", (ROOT / "wheel_planner/wheel.html").read_text(encoding="utf-8")).group(1)
    assert f"Opens the {wheel_title} page" in text, "the row says the same name as the page title"
    assert f"<h3>{wheel_title}</h3>" in html
    assert "The wheel is the routine of" in text, "explain the word wheel where it first appears"
    assert "FIRST Robotics Competition (FRC)" in text, "expand FRC once"
    assert "bols (the spoken syllables" in text, "gloss bols once"


def test_own_copy_steps_describe_the_real_github_page(html):
    """The branch button on GitHub is always present and does not read 'main' for this repo,
    and Extract All makes a folder with one more folder inside it."""
    text = _text(html)
    m = re.search(r'<h3 id="copy">.*?</ol>', html, re.S)
    assert m, "the Getting your own copy section with its numbered steps is missing"
    steps = [_text(li) for li in re.findall(r"<li>(.*?)</li>", m.group(0), re.S)]
    assert len(steps) >= 6, f"expected at least six steps, found {len(steps)}"
    joined = " ".join(steps)
    assert BRANCH in joined
    assert "type lucid" in joined.lower() or "type <strong>lucid" in m.group(0).lower()
    assert "may say main" not in joined.lower(), "do not tell the user the button may say main"
    assert "do not see such a menu" not in joined.lower(), "the branch button is always there"
    assert "Download ZIP" in joined and "Extract All" in joined
    assert "one more folder" in joined.lower(), "the ZIP holds a folder inside a folder; say so"
    assert "which program to use" in joined.lower() and "web browser" in joined.lower()
    assert "index.html" in joined
    assert "README" not in text or "README.md" in text, "name the README file if it is mentioned"
    assert "Notepad" in text, "say how to open a README.md (Notepad) if the hub points to one"


def test_card_wording_avoids_undefined_jargon(html):
    text = _text(html).lower()
    assert "option chain" not in text, "say 'the numbers Webull shows on its screen', not 'option chain'"
    assert "fantasypros website" in text, "say FantasyPros is a website"
    assert '<a href="#words">.csv</a>' in html, "tie the projection files to the .csv glossary entry"
    assert "practise" not in text, "US spelling: practice"


def test_back_link_promise_matches_the_tool_pages(html):
    assert "Back to the toolbox" in html, "the hub must say how to get back"
    for page in TOOL_PAGES:
        path = ROOT / page
        if path.is_file():
            assert "Back to the toolbox" in path.read_text(encoding="utf-8"), f"{page} has no back link"


def test_example_button_promise_is_qualified(html):
    text = _text(html)
    assert "Try it with example data" in text
    assert "Each tool has a button" not in text, "not every tool has the example button; qualify it"
    assert "Every tool that works from" not in text, "the photo page has no such button; name the pages"
    assert "If the page has a button called" in text


def test_example_button_promise_matches_the_pages(html):
    """Every page the hub says has the example button really has it, and the photo page has
    the buttons the hub names instead."""
    text = _text(html)
    for name in ("Options wheel", "Fantasy football", "PE continuing education"):
        assert name in text[:text.find("Try it with example data")] or name in text
    for page in EXAMPLE_BUTTON_PAGES:
        assert "Try it with example data" in (ROOT / page).read_text(encoding="utf-8"), f"{page} lacks the button the hub promises"
    photo = (ROOT / "photo_sheet/photo_sheet.html").read_text(encoding="utf-8")
    for label in PHOTO_BUTTONS:
        assert label in text, f"the hub should name the photo page's {label} button"
        assert label in photo, f"photo page lacks the {label} button the hub names"
    assert "Try it with example data" not in photo, "if the photo page gains the button, update the hub wording"


def test_glossary_has_at_least_ten_terms(html):
    m = re.search(r'<h2 id="words">.*?</dl>', html, re.S)
    assert m, "glossary section (h2 id=words followed by a <dl>) is missing"
    terms = re.findall(r"<dt>(.*?)</dt>", m.group(0))
    assert 10 <= len(terms) <= 14, f"glossary has {len(terms)} terms; the spec asks for 10 to 14"
    for word in ("csv", "option", "put", "covered call", "premium", "strike", "expiry",
                 "assigned", "roll", "projection", "roster", "pdh", "browser tab", "pop-up"):
        assert any(word in t.lower() for t in terms), f"glossary is missing '{word}'"
    for dd in re.findall(r"<dd>(.*?)</dd>", m.group(0), re.S):
        assert dd.strip(), "every glossary term needs a one-sentence meaning"


def test_privacy_sentence_present(html):
    assert "nothing you type or choose is uploaded anywhere" in html.lower()
    assert "runs on the page in your browser" in html.lower()


def test_required_sections_in_order(html):
    headings = ("What do you want to do?", "The tools", "How to use these", "Getting your own copy",
                "Words you will see", "If something looks wrong")
    positions = [html.find(h) for h in headings]
    assert all(p >= 0 for p in positions), f"missing section: {dict(zip(headings, positions))}"
    assert positions == sorted(positions), "sections are out of the order the brief asks for"
    assert BRANCH in html


def test_no_dialogs_or_emoji_or_shouting_headings(html):
    for call in ("alert(", "confirm(", "prompt("):
        assert call not in html
    # no characters outside the Basic Multilingual Plane (where emoji live)
    assert all(ord(ch) <= 0xFFFF for ch in html), "no emoji in the hub"
    headings = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html)
    for h in headings:
        text = re.sub(r"<[^>]+>", "", h)
        letters = [c for c in text if c.isalpha()]
        assert not (len(letters) > 3 and all(c.isupper() for c in letters)), f"all-caps heading: {text}"


def test_tool_cards(html):
    assert html.count("Works on a phone: yes") >= 6
    assert html.count("You need:") >= 6
    assert html.count('class="btn"') >= 6


def test_situations_list_has_nine_entries(html):
    m = re.search(r'<ul class="situations">.*?</ul>', html, re.S)
    assert m
    assert len(re.findall(r'class="situation"', m.group(0))) == 9


def test_no_email_addresses(html):
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", html), "no email addresses in the public hub"


def test_no_generic_private_patterns():
    """Always runs, even without the private list: the kinds of strings that would be
    private if they ever crept into the public hub."""
    for name in ("index.html", "tests/test_hub.py"):
        content = (ROOT / name).read_text(encoding="utf-8")
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", content), f"email address in {name}"
        others = set(re.findall(r"github\.com/[\w.-]+/[\w.-]+", content)) - {"github.com/noshir2/Claude-Repository"}
        assert not others, f"a GitHub path other than the public project address in {name}: {others}"
        if name == "index.html":
            assert "YOUR-USER-NAME" not in content, "placeholder address in the hub"
        assert not re.search(r"\d{7,}", content), f"a long run of digits (phone or account number) in {name}"
        secret_words = "pass" + "word|pass" + "code"  # split so this file does not match itself
        assert not re.search(secret_words, content, re.I), f"credential wording in {name}"


def test_no_forbidden_strings(html):
    path = os.environ.get(FORBIDDEN_ENV)
    if not path or not Path(path).is_file():
        pytest.skip(f"set {FORBIDDEN_ENV} to the path of the private never-commit list to run this")
    words = [w.strip() for w in Path(path).read_text(encoding="utf-8").splitlines() if w.strip()]
    for name in ("index.html", "tests/test_hub.py"):
        content = (ROOT / name).read_text(encoding="utf-8").lower()
        hits = [w for w in words if w.lower() in content]
        assert not hits, f"forbidden strings in {name}: {hits}"
