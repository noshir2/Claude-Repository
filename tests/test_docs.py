"""Checks on the written guides: the root README ("Start here"), OPEN-ME-FIRST.txt and the
first-time-user sections of every tool README.

- every relative path written in backticks or as a Markdown link in the root README and
  OPEN-ME-FIRST.txt exists (the four browser pages built alongside the guides may be missing:
  then the check is skipped, not failed); in the seven tool READMEs every path with a slash in
  it exists too, resolved from the project root or from the tool's own folder, except the
  reader's own files under data/ and the report files the commands write;
- every `python -m <package>` command in an "Advanced: the command-line version" section names a
  package folder that exists, and the package answers `--help` with exit code 0;
- no guide (root README, OPEN-ME-FIRST.txt, the seven tool READMEs) holds a forbidden (personal)
  string or an e-mail address, and no README holds the stale file name wheel_calculator.html;
- the glossary ("Words you will see") has at least 10 terms;
- the word "repo" appears in the root README only next to "folder" or "project", or in the
  Advanced section;
- every tool README has "The easy way" (naming its browser page and the example button that page
  really has), "Limits" and the Advanced section, and no undefined coding jargon;
- every **bold** control name in the numbered steps of "The easy way" is text that exists in the
  tool's page, so the guide never tells the reader to press a button that is not there;
- the root README's "Getting your own copy" is followable without a GitHub account and includes
  the nested-folder step after Extract All.

The forbidden-strings list is private and never committed. The test reads it from the environment
variable FORBIDDEN_STRINGS_FILE (a path) or TOOLBOX_FORBIDDEN_STRINGS (the same name test_hub.py
uses); CI should set one of them. Without either it falls back to the build scratchpad and
otherwise skips with a message.
"""
import html as html_mod
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ROOT_README = ROOT / "README.md"
OPEN_ME_FIRST = ROOT / "OPEN-ME-FIRST.txt"

TOOLS = ["wheel_tracker", "wheel_planner", "frc_shop_card", "fantasy_helper", "taal_trainer",
         "pdh_log", "photo_sheet"]

# The page each tool's "The easy way" section must point at (the UX brief's file map).
PAGE_FOR_TOOL = {
    "wheel_tracker": "wheel_planner/wheel.html",
    "wheel_planner": "wheel_planner/wheel.html",
    "frc_shop_card": "frc_shop_card/frc_shop_card.html",
    "fantasy_helper": "fantasy_helper/fantasy.html",
    "taal_trainer": "taal_trainer/taal_trainer.html",
    "pdh_log": "pdh_log/pdh.html",
    "photo_sheet": "photo_sheet/photo_sheet.html",
}

# The big first button each page really has (the Taal trainer needs nothing, so its first press
# is Start). "The easy way" must name this one, and the page must contain it.
EXAMPLE_BUTTON = {
    "wheel_tracker": "Try it with example data",
    "wheel_planner": "Try it with example data",
    "frc_shop_card": "Show me an example",
    "fantasy_helper": "Try it with example data",
    "taal_trainer": "Start",
    "pdh_log": "Try it with example data",
    "photo_sheet": "Try it with a drawn face",
}

GUIDES = [ROOT_README, OPEN_ME_FIRST] + [ROOT / t / "README.md" for t in TOOLS]

# Pages other builders produce; allowed to be missing while the guides are tested on their own.
PENDING_PAGES = {"index.html", "wheel_planner/wheel.html", "fantasy_helper/fantasy.html",
                 "pdh_log/pdh.html"}

ADVANCED_HEADING = "## Advanced: the command-line version"
JARGON = re.compile(r"\b(CLI|argparse|stdlib)\b")
BACKTICK = re.compile(r"`([^`\n]+)`")
MD_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
PATH_LIKE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*")
PATH_SUFFIXES = (".html", ".txt", ".md", ".csv", ".py", ".json", ".zip", ".png")
MODULE_CMD = re.compile(r"\b(?:python3|python|py) -m ([A-Za-z0-9_.]+)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BOLD = re.compile(r"\*\*([^*\n]+?)\*\*")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    """The body of a '## heading' section up to the next '## ' heading (or the end)."""
    m = re.search(r"^" + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def numbered_steps(body: str) -> str:
    """The numbered-step lines of a section (``1. ...`` and their indented continuation lines),
    stopping at the first ``###`` sub-heading, with wrapped lines joined back into one."""
    out, keep = [], False
    for line in body.split("\n### ", 1)[0].splitlines():
        if re.match(r"^\d+\. ", line):
            keep = True
            out.append(line)
        elif keep and line.startswith("   "):
            out[-1] += " " + line.strip()
        else:
            keep = False
    return "\n".join(out)


def backtick_paths(text: str):
    """Relative paths named in backticks or as Markdown link targets."""
    out = []
    for tok in BACKTICK.findall(text) + MD_LINK.findall(text):
        if tok.startswith(("http://", "https://")) or not PATH_LIKE.fullmatch(tok):
            continue
        if "/" in tok or tok.endswith(PATH_SUFFIXES):
            if tok not in out:
                out.append(tok)
    return out


def guide_paths():
    paths = []
    for f in (ROOT_README, OPEN_ME_FIRST):
        if f.exists():
            paths.extend(p for p in backtick_paths(read(f)) if p not in paths)
    # OPEN-ME-FIRST.txt has no backticks, but names index.html and README.md in plain words.
    for name in ("index.html", "README.md"):
        if name not in paths:
            paths.append(name)
    return paths


def tool_readme_paths():
    """(tool, path) for every slash path a tool README names, except the reader's own files
    (data/..., which never exist in the project) and the report files the commands write."""
    out = []
    for tool in TOOLS:
        readme = ROOT / tool / "README.md"
        if not readme.exists():
            continue
        for rel in backtick_paths(read(readme)):
            if "/" not in rel or rel.startswith("data/") or rel.endswith("_report.html"):
                continue
            if re.fullmatch(r"[\d/]+", rel):  # a date such as 11/20/2026, not a path
                continue
            if (tool, rel) not in out:
                out.append((tool, rel))
    return out


def test_guides_exist():
    assert ROOT_README.exists(), "README.md (Start here) is missing"
    assert OPEN_ME_FIRST.exists(), "OPEN-ME-FIRST.txt is missing"
    lines = [l for l in read(OPEN_ME_FIRST).splitlines() if l.strip()]
    assert len(lines) == 10, f"OPEN-ME-FIRST.txt should be ten plain lines, has {len(lines)}"
    # Classic Windows Notepad does not wrap by default, so every line must fit on screen.
    long = [l for l in lines if len(l) > 110]
    assert not long, f"OPEN-ME-FIRST.txt lines over 110 characters run off a Notepad window: {long}"
    text = read(OPEN_ME_FIRST)
    assert "index.html" in text and "browser" in text.lower()
    assert "upload" in text.lower()


def test_open_me_first_does_not_tell_the_reader_to_bin_the_tool_folders():
    # The pages live inside the tool folders, so the note must not call them ignorable.
    text = read(OPEN_ME_FIRST)
    assert "work without them" not in text and "can be ignored" not in text
    assert "Leave the folders" in text
    # Every button name it quotes exists on some page.
    for label in re.findall(r'"([^"]+)"', text):
        if label in ("Start here",):
            continue
        hits = [p for p in PAGE_FOR_TOOL.values()
                if (ROOT / p).exists() and label in html_mod.unescape(read(ROOT / p))]
        assert hits, f"OPEN-ME-FIRST.txt quotes the button {label!r} but no page has it"


@pytest.mark.parametrize("rel", guide_paths())
def test_backtick_paths_exist(rel):
    target = ROOT / rel
    if not target.exists() and rel in PENDING_PAGES:
        pytest.skip(f"{rel} is being built alongside the guides and is not in the folder yet")
    assert target.exists(), f"root guide mentions `{rel}` but it does not exist"


@pytest.mark.parametrize("tool,rel", tool_readme_paths(), ids=[f"{t}:{r}" for t, r in tool_readme_paths()])
def test_tool_readme_paths_exist(tool, rel):
    """A path a tool README names exists, read from the project root (where the commands run) or
    from the tool's own folder (where GitHub resolves the README's links)."""
    if not (ROOT / rel).exists() and not (ROOT / tool / rel).exists():
        if rel in PENDING_PAGES:
            pytest.skip(f"{rel} is being built alongside the guides and is not in the folder yet")
        assert False, f"{tool}/README.md mentions `{rel}` but it does not exist"


def test_root_readme_links_every_tool_readme():
    """'Details:' pointers are real Markdown links, so they are clickable on GitHub."""
    text = read(ROOT_README)
    for tool in TOOLS:
        assert f"[{tool}/README.md]({tool}/README.md)" in text, \
            f"root README should link {tool}/README.md as a Markdown link, not a code span"


def advanced_modules():
    found = []
    for tool in TOOLS:
        readme = ROOT / tool / "README.md"
        if not readme.exists():
            continue
        body = section(read(readme), ADVANCED_HEADING)
        for mod in MODULE_CMD.findall(body):
            if mod == "pytest":
                continue
            if (tool, mod) not in found:
                found.append((tool, mod))
    return found


@pytest.mark.parametrize("tool,module", advanced_modules())
def test_advanced_command_runs(tool, module):
    package = module.split(".")[0]
    assert (ROOT / package).is_dir(), f"{tool}/README.md names `python -m {module}` but {package}/ is no folder"
    if "." in module:
        sub = ROOT / package / (module.split(".", 1)[1].replace(".", "/") + ".py")
        assert sub.exists(), f"{module} has no file {sub.relative_to(ROOT)}"
        if "argparse" not in read(sub):
            return  # a plain script with no --help (it would run for real); the file exists, enough
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-m", module, "--help"], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"python -m {module} --help exited {proc.returncode}: {proc.stderr[-500:]}"
    assert "usage" in proc.stdout.lower()


def test_advanced_sections_found():
    mods = advanced_modules()
    packages = {m.split(".")[0] for _, m in mods}
    assert packages >= set(TOOLS), f"Advanced sections cover only {sorted(packages)}"


@pytest.mark.parametrize("tool", TOOLS)
def test_advanced_section_defines_terminal(tool):
    body = section(read(ROOT / tool / "README.md"), ADVANCED_HEADING)
    assert "terminal (the text window where you type commands" in body, \
        f"{tool}: the Advanced section should say what a terminal is where it first uses the word"


def forbidden_strings():
    candidates = []
    for var in ("FORBIDDEN_STRINGS_FILE", "TOOLBOX_FORBIDDEN_STRINGS"):
        if os.environ.get(var):
            candidates.append(Path(os.environ[var]))
    if Path("/tmp/claude-0").exists():  # the build scratchpad; absent anywhere else
        candidates += sorted(Path("/tmp/claude-0").glob("*/*/scratchpad/forbidden_strings.txt"))
    for c in candidates:
        if c.exists():
            return [l.strip() for l in read(c).splitlines() if l.strip()]
    return None


@pytest.mark.parametrize("guide", GUIDES, ids=[str(g.relative_to(ROOT)) for g in GUIDES])
def test_guide_has_no_forbidden_string(guide):
    text = read(guide)
    name = guide.relative_to(ROOT)
    assert not EMAIL.search(text), f"{name} contains an e-mail address"
    assert "wheel_calculator.html" not in text, f"{name}: stale file name; the page is wheel_planner/wheel.html"
    words = forbidden_strings()
    if words is None:
        pytest.skip("no forbidden-strings list available (set FORBIDDEN_STRINGS_FILE to check)")
    hits = [w for w in words if w.lower() in text.lower()]
    assert not hits, f"forbidden strings in {name}: {hits}"


def test_glossary_has_ten_terms():
    body = section(read(ROOT_README), "## Words you will see")
    assert body, "root README has no 'Words you will see' section"
    terms = re.findall(r"^- \*\*(.+?)\*\*", body, re.M)
    assert len(terms) >= 10, f"glossary has {len(terms)} terms: {terms}"


def test_repo_word_only_with_plain_word_or_in_advanced():
    text = read(ROOT_README)
    head, _, _advanced = text.partition("\n" + "## For the technically minded")
    for para in re.split(r"\n\s*\n", head):
        if re.search(r"\brepo(?:sitory)?\b", para, re.I):
            assert re.search(r"\b(folder|project)\b", para, re.I), f"'repo' without a plain word near it:\n{para}"


def test_root_readme_sections():
    text = read(ROOT_README)
    assert text.lstrip().startswith("# Start here")
    for heading in ("## Getting your own copy", "## Words you will see", "## Nothing is uploaded",
                    "## For the technically minded"):
        assert heading in text, f"root README lacks '{heading}'"
    copy = section(text, "## Getting your own copy")
    for phrase in ("Download ZIP", "Extract All", "index.html", "claude/lucid-dijkstra-gic3gd", "Code"):
        assert phrase in copy, f"'Getting your own copy' does not mention {phrase!r}"
    assert "python -m <folder>" in section(text, "## For the technically minded")
    assert "pytest" in section(text, "## For the technically minded")
    assert not JARGON.search(text), "undefined jargon in the root README"
    for tool in TOOLS:
        assert f"{tool}/README.md" in text, f"root README does not link {tool}/README.md"


def test_getting_your_own_copy_is_followable_without_an_account():
    """A first-timer only has the hosted link and the GitHub link that came with the toolbox.
    The section must say where the project page comes from, must not claim the hosted link opens
    it, and must include the nested-folder step that follows Extract All."""
    copy = section(read(ROOT_README), "## Getting your own copy")
    assert "the link you were given opens it directly" not in copy
    assert "YOUR-USER-NAME" not in copy, "a placeholder the reader cannot fill in"
    assert "github.com/noshir2/Claude-Repository" in copy, "print the public project address"
    assert "address bar" in copy
    assert "no sign-in" in copy
    assert "one more folder" in copy, "missing the nested-folder step after Extract All"
    steps = re.findall(r"^(\d+)\. ", copy, re.M)
    assert steps == [str(i) for i in range(1, len(steps) + 1)] and len(steps) >= 7


def test_root_readme_names_the_real_example_buttons():
    """The 'easiest way' names each page's first button, and each name is really on that page."""
    easy = section(read(ROOT_README), "## The easiest way")
    for tool, label in EXAMPLE_BUTTON.items():
        assert label in easy, f"root README's easiest way does not name the {tool} button {label!r}"
        page = ROOT / PAGE_FOR_TOOL[tool]
        if not page.exists():
            continue
        assert label in html_mod.unescape(read(page)), f"{PAGE_FOR_TOOL[tool]} has no {label!r}"


def test_glossary_matches_hub_browser_tab_entry():
    hub = ROOT / "index.html"
    if not hub.exists():
        pytest.skip("index.html is being built alongside the guides")
    m = re.search(r"<dt>Browser tab</dt>\s*<dd>(.*?)</dd>", read(hub), re.S)
    assert m, "index.html has no 'Browser tab' glossary entry"
    hub_text = html_mod.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    body = section(read(ROOT_README), "## Words you will see")
    m2 = re.search(r"^- \*\*Browser tab\*\*: (.*?)(?=^- \*\*|\n\n)", body, re.S | re.M)
    assert m2, "root README glossary has no 'Browser tab' entry"
    readme_text = re.sub(r"\s+", " ", m2.group(1)).strip()
    # Same story: the tools open in the same tab and the back link returns you.
    for phrase in ("same tab", "Back to the toolbox", "Back arrow"):
        assert phrase in hub_text and phrase in readme_text, f"'Browser tab' entries disagree on {phrase!r}"


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_readme_first_section(tool):
    text = read(ROOT / tool / "README.md")
    easy = section(text, "## The easy way")
    assert easy, f"{tool}/README.md has no 'The easy way' section"
    assert PAGE_FOR_TOOL[tool] in easy, f"{tool}: 'The easy way' does not name {PAGE_FOR_TOOL[tool]}"
    assert f"**{EXAMPLE_BUTTON[tool]}**" in easy, \
        f"{tool}: 'The easy way' does not name the page's first button **{EXAMPLE_BUTTON[tool]}**"
    assert re.search(r"^1\. ", easy, re.M) and re.search(r"^3\. ", easy, re.M), f"{tool}: fewer than three numbered steps"
    headings = re.findall(r"^## (.+)$", text, re.M)
    assert headings[0] == "The easy way", f"{tool}: first section is '{headings[0]}', not 'The easy way'"
    assert "Limits" in headings, f"{tool}: 'Limits' section missing"
    assert headings[-1] == "Advanced: the command-line version", f"{tool}: last section is '{headings[-1]}'"
    assert not JARGON.search(text), f"{tool}: undefined jargon (CLI/argparse/stdlib)"


@pytest.mark.parametrize("tool", TOOLS)
def test_easy_way_controls_exist_on_the_page(tool):
    """Every **bold** name in the numbered steps of 'The easy way' (buttons, tabs, boxes, section
    headings) is text the page really contains, so the guide never points at a control that is
    not there. Compared after HTML entities are decoded, case-sensitively, as the reader sees it."""
    page = ROOT / PAGE_FOR_TOOL[tool]
    if not page.exists():
        pytest.skip(f"{PAGE_FOR_TOOL[tool]} is being built alongside the guides")
    page_text = html_mod.unescape(read(page))
    steps = numbered_steps(section(read(ROOT / tool / "README.md"), "## The easy way"))
    names = [n.strip().rstrip(".:") for n in BOLD.findall(steps)]
    assert names, f"{tool}: no bold control names in the numbered steps"
    missing = [n for n in names if n not in page_text]
    assert not missing, f"{tool}: 'The easy way' names controls the page does not have: {missing}"


def test_version_line_agrees_across_the_three_guides():
    """A first-time user compares the Version date at the top of README.md with the one GitHub
    shows, so README.md, index.html and OPEN-ME-FIRST.txt must all carry the same date and the
    root README must say that updates stay on the same branch."""
    date = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
    readme = read(ROOT_README)
    m = re.search(r"^Version: (\d{4}-\d{2}-\d{2})", readme, re.M)
    assert m, "README.md has no 'Version: YYYY-MM-DD' line near the top"
    version = m.group(1)
    assert readme.index("Version: " + version) < readme.index("## The easiest way")
    hub = ROOT / "index.html"
    if hub.exists():
        m = re.search(r"Version: (\d{4}-\d{2}-\d{2})", read(hub))
        assert m and m.group(1) == version, f"index.html Version line differs from README.md ({version})"
    assert f"version {version}" in read(OPEN_ME_FIRST), "OPEN-ME-FIRST.txt lacks the version date"
    copy = section(readme, "## Getting your own copy")
    assert "same branch" in copy, "say whether updates stay on the same branch"
    assert "Version line" in copy, "say how to tell which branch is newest"
