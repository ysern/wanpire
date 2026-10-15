"""The stylesheet keeps to the house style's tokens and values (spec: web-ui, "The page follows
the house style"; the rules are `.claude/skills/web-ui-house-style/SKILL.md`, section 13). Read
as text, no browser: the causes a screenshot hides."""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "src" / "wanpire" / "web"
SIZES_PX = {13, 14, 16, 20, 22, 24}
WEIGHTS = {400, 700}
RADII_PX = {0, 5, 6, 8, 10}


def sheet_without_tokens():
    css = re.sub(r"/\*.*?\*/", "", (WEB / "style.css").read_text(encoding="utf-8"), flags=re.S)
    # the two :root blocks hold the palette; everything else must refer to it
    roots = re.findall(r":root\s*\{[^}]*\}", css)
    assert len(roots) == 2, "a light and a dark :root block"
    for r in roots:
        css = css.replace(r, "")
    return css


def rules(css):
    """(selector, declarations) pairs, media queries flattened."""
    css = re.sub(r"@media[^{]*\{", "", css)
    return [(s.strip(), d) for s, d in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def values(css, prop):
    return [v.strip() for v in re.findall(rf"(?<![\w-]){prop}\s*:\s*([^;]+);", css)]


def test_every_colour_outside_the_tokens_is_a_token():
    css = sheet_without_tokens()
    literal = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
    assert literal == [], literal
    named = re.findall(r":\s*(white|black|red|grey|gray|blue|green|yellow|orange)\b", css)
    assert named == [], named


def test_weights_sizes_and_fonts_are_the_rules():
    css = sheet_without_tokens()
    weights = {int(w) for w in values(css, "font-weight") if w.isdigit()}
    weights |= {int(w) for w in re.findall(r"font\s*:\s*(\d{3})\s", css)}
    assert weights <= WEIGHTS, weights - WEIGHTS
    sizes = {int(s) for s in re.findall(r"font-size\s*:\s*(\d+)px", css)}
    sizes |= {int(s) for s in re.findall(r"font\s*:\s*(?:\d{3}\s+)?(\d+)px", css)}
    assert sizes <= SIZES_PX, sizes - SIZES_PX
    assert not re.search(r"monospace|Menlo|Consolas|SF Mono", css), "monospace is the browser's, for code only"
    assert "@import" not in css and "@font-face" not in css and "url(" not in css


def test_radii_are_the_rules():
    css = sheet_without_tokens()
    seen = set()
    for v in values(css, "border-radius"):
        for n, unit in re.findall(r"(\d+(?:\.\d+)?)(px|%)", v):
            seen.add((float(n), unit))
    wrong = {s for s in seen if not ((s[1] == "px" and s[0] in RADII_PX) or s == (50.0, "%"))}
    assert wrong == set(), wrong


def test_no_shadow_on_panels_cards_rows_or_the_menu():
    flat = re.compile(r"\.panel|\.card|\.table|\btd\b|\.place|\.side|\.channel|\.pill|footer")
    shadowed = [s for s, d in rules(sheet_without_tokens()) if "box-shadow" in d and flat.search(s)]
    assert shadowed == [], shadowed


def test_motion_is_short():
    css = sheet_without_tokens()
    durations = [float(d) for d in re.findall(r"transition\s*:[^;]*?(\d*\.?\d+)s", css)]
    assert durations, "the band and the chevrons move"
    assert all(0.2 <= d <= 0.3 for d in durations), durations


def test_the_page_paints_nothing_itself_and_fetches_nothing():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'<symbol id="i-mark".*?</symbol>', "", html, flags=re.S)  # the logo's own colours
    assert not re.search(r'style="[^"]*(#[0-9a-fA-F]{3,8}|rgb|color)', html)
    assert not re.search(r'(fill|stroke)="#', html), "icons take their colour from the stylesheet"
    assert not re.search(r'<(link|script)[^>]+(href|src)="(https?:)?//', html)
    assert "@import" not in html
