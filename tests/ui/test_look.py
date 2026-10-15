"""The page's look: sections, nothing fetched elsewhere, no sideways scroll and WCAG AA contrast
at 360, 720 and 1,280 px in both themes, and the house style's measured points (spec: web-ui,
the look's requirements; the rules are .claude/skills/web-ui-house-style/SKILL.md)."""

import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from .conftest import sign_in

SECTIONS = ["link", "broker", "adapters", "endpoints", "settings"]  # the header's order (U9)
PAGES = [("link", "link-set"), ("link", "link-traffic"), ("broker", "broker-queue"),
         ("adapters", "adapters-list"), ("endpoints", "endpoints-places"),
         ("settings", "settings-access")]

# Every visible text's contrast with what is behind it. Behind a gradient, both ends count.
CONTRAST_JS = r"""
() => {
  const parse = (s) => (s.match(/rgba?\([^)]*\)/g) || []).map((c) => {
    const n = c.match(/[\d.]+/g).map(Number);
    return {r: n[0], g: n[1], b: n[2], a: n.length > 3 ? n[3] : 1};
  });
  const lum = (c) => [c.r, c.g, c.b].map((v) => {
    v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  }).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => {
    const x = lum(a), y = lum(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  };
  const behind = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage.includes("gradient")) {
        return parse(cs.backgroundImage);
      }
      const bg = parse(cs.backgroundColor)[0];
      if (bg && bg.a > 0) return [bg];
    }
    return [{r: 255, g: 255, b: 255, a: 1}];
  };
  const failures = [];
  let checked = 0;
  for (const el of document.querySelectorAll("body *")) {
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own || !el.checkVisibility || !el.checkVisibility()) continue;
    if (el.closest(":disabled, [aria-disabled=true]")) continue;  // inactive: exempt
    const cs = getComputedStyle(el);
    const fg = parse(cs.color)[0];
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    checked++;
    for (const bg of behind(el)) {
      const r = ratio(fg, bg);
      if (r < need) failures.push(`${el.tagName}#${el.id}.${el.className} "${el.textContent.trim().slice(0, 30)}" ${r.toFixed(2)} < ${need}`);
    }
  }
  return {checked, failures};
}
"""


def go(page, section, sub=None):
    page.click(f"#nav-{section}")
    if sub:
        page.click(f"#sub-{sub}")
        expect(page.locator(f"#page-{sub}")).to_be_visible()


# -- sections -------------------------------------------------------------------------------

def test_the_header_band_carries_the_sections(page):
    sign_in(page)
    for s in SECTIONS:
        expect(page.locator(f"#nav-{s}")).to_be_visible()
    order = page.eval_on_selector_all(".sections a", "as => as.map(a => a.id)")
    assert order == [f"nav-{s}" for s in SECTIONS]
    expect(page.locator("#nav-link")).to_have_attribute("aria-current", "page")
    expect(page.locator("#nav-link")).to_contain_text("Link")
    go(page, "broker")
    expect(page.locator("#nav-broker")).to_have_attribute("aria-current", "page")
    expect(page.locator("#nav-link")).not_to_have_attribute("aria-current", "page")
    expect(page.locator("#queue")).to_be_visible()


def test_the_side_menu_marks_the_current_page(page):
    sign_in(page)
    expect(page.locator("#sub-link-set")).to_have_attribute("aria-current", "page")
    go(page, "link", "link-traffic")
    expect(page.locator("#sub-link-traffic")).to_have_attribute("aria-current", "page")
    expect(page.locator("#sub-link-traffic")).to_have_text("Traffic")
    expect(page.locator("#page-link-traffic h2")).to_have_text("Traffic")
    expect(page.locator("#sub-link-set")).not_to_have_attribute("aria-current", "page")
    expect(page.locator("#c-down-packets")).to_be_visible()
    expect(page.locator("#near-endpoint")).to_be_hidden()


def test_one_primary_button_per_section(page):
    sign_in(page)
    for sec in page.locator("section.panel").all():
        assert sec.locator("button.primary").count() <= 1


def test_adapters_and_endpoints_are_listed(page):
    sign_in(page)
    go(page, "adapters")
    expect(page.locator("#adapters-table")).to_contain_text("eth1")
    expect(page.locator("#adapters-table")).to_contain_text("outbound")
    go(page, "endpoints")
    expect(page.locator("#places")).to_contain_text("Tokyo")


def test_a_place_opens_to_its_channels(page):
    sign_in(page)
    go(page, "endpoints")
    london = page.locator("#places details[data-id='london']")
    expect(london.locator("summary")).to_contain_text("London")
    expect(london.locator("summary")).to_contain_text("12 channels")
    expect(london.locator(".channel")).to_have_count(0)  # closed, and not loaded yet
    assert london.get_attribute("open") is None
    london.locator("summary").click()
    expect(london.locator(".channel")).to_have_count(12)
    first = london.locator(".channel").first
    expect(first).to_contain_text("generic")
    expect(first).to_contain_text("default")
    expect(first).to_contain_text("A typical connection in London")
    for label in ("Delay, ms", "Jitter, ms", "Loss, %", "Bandwidth, Mbit/s", "Down", "Up"):
        expect(first).to_contain_text(label)
    expect(first).to_contain_text("50.9")  # London generic's bandwidth down
    assert page.locator("#page-endpoints-places input, #page-endpoints-places select, "
                        "#page-endpoints-places button").count() == 0


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_an_open_place_is_readable(browser, box, width, scheme):
    context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = context.new_page()
    page.set_default_timeout(5000)
    page.box = box
    try:
        sign_in(page)
        expect(page.locator("#mode")).to_have_text("bridge")
        page.goto(box.url + "/#endpoints")
        page.locator("#places details[data-id='tokyo'] summary").click()
        expect(page.locator("#places details[data-id='tokyo'] .channel")).to_have_count(12)
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        result = page.evaluate(CONTRAST_JS)
        assert result["failures"] == [], result["failures"]
    finally:
        context.close()


def test_nothing_is_fetched_from_elsewhere(page):
    urls = []
    page.on("request", lambda r: urls.append(r.url))
    sign_in(page)
    for section, sub in PAGES:
        go(page, section, sub)
    assert urls
    assert all(u.startswith(page.box.url) for u in urls), [u for u in urls
                                                           if not u.startswith(page.box.url)]


# -- widths and themes ----------------------------------------------------------------------

@pytest.mark.parametrize("width", [360, 720, 1280])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_no_sideways_scroll_and_aa_contrast(browser, box, width, scheme):
    context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = context.new_page()
    page.set_default_timeout(5000)
    page.box = box
    try:
        box.engine.applied = True
        box.engine.packets = 1000
        page.goto(box.url + "/")
        expect(page.locator("#password")).to_be_visible()
        result = page.evaluate(CONTRAST_JS)
        assert result["failures"] == [], f"sign-in: {result['failures']}"
        sign_in(page)
        page.select_option("#far-channel", "mobile-4g")
        expect(page.locator("#down-delay_ms")).not_to_have_text("-")
        page.fill("#purpose", "contrast check")
        page.click("#ask")
        expect(page.locator("#lease-state")).to_contain_text("You hold the link")
        for section, sub in PAGES:
            go(page, section, sub)
            assert page.evaluate("document.documentElement.scrollWidth") <= width, sub
            result = page.evaluate(CONTRAST_JS)
            assert result["checked"] > 5, sub
            assert result["failures"] == [], f"{sub}: {result['failures']}"
    finally:
        context.close()


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_band_is_readable_calm_and_live(browser, box, live, scheme):
    context = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme=scheme)
    page = context.new_page()
    page.set_default_timeout(5000)
    page.box = box
    try:
        box.engine.applied = live
        sign_in(page)
        expect(page.locator("#mode")).to_have_text("bridge")
        expect(page.locator("#band-link")).to_have_text("link applied" if live else "no link")
        result = page.evaluate(CONTRAST_JS)
        band = [f for f in result["failures"] if "band" in f or "ring" in f or "brand" in f]
        assert result["failures"] == [], f"live={live}: {result['failures']} {band}"
    finally:
        context.close()


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_setup_card_is_readable(browser, new_box, width, scheme):
    context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = context.new_page()
    page.set_default_timeout(5000)
    try:
        page.goto(new_box.url + "/")
        expect(page.locator("#setup")).to_be_visible()
        page.fill("#setup-password", "short")
        page.fill("#setup-again", "short")
        page.click("#setup-save")
        expect(page.locator("#setup-error")).to_contain_text("8 characters")
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        result = page.evaluate(CONTRAST_JS)
        assert result["checked"] > 5
        assert result["failures"] == [], f"setup: {result['failures']}"
    finally:
        context.close()


def test_the_sign_in_card_is_centred(page):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(page.box.url + "/")
    card = page.locator("#signin").bounding_box()
    assert abs((card["x"] + card["width"] / 2) - 640) < 4
    assert 380 <= card["width"] <= 460


# -- screenshots for a review, kept out of git ---------------------------------------------

SHOTS = Path(__file__).parent / "shots"


@pytest.mark.skipif(not os.environ.get("WANPIRE_SHOTS"), reason="set WANPIRE_SHOTS=<stage> to render")
@pytest.mark.parametrize("width", [360, 720, 1280])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_screenshots_for_a_review(browser, box, new_box, width, scheme):
    """Renders every page at this width and theme into tests/ui/shots/<stage>/ for the house-style
    review (the skill's section 15). Not a test of anything: it only draws."""
    stage = os.environ["WANPIRE_SHOTS"]
    out = SHOTS / stage
    out.mkdir(parents=True, exist_ok=True)
    shot = lambda page, name: page.screenshot(path=str(out / f"{name}-{width}-{scheme}.png"),  # noqa: E731
                                              full_page=True)
    context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = context.new_page()
    page.set_default_timeout(5000)
    page.box = box
    try:
        page.goto(new_box.url + "/")
        expect(page.locator("#setup")).to_be_visible()
        shot(page, "setup")
        page.goto(box.url + "/")
        expect(page.locator("#password")).to_be_visible()
        shot(page, "signin")
        sign_in(page)
        expect(page.locator("#mode")).to_have_text("bridge")
        shot(page, "link-set-calm")
        page.select_option("#far-channel", "mobile-4g")
        expect(page.locator("#down-delay_ms")).not_to_have_text("-")
        page.fill("#purpose", "a review")
        page.click("#ask")
        expect(page.locator("#lease-state")).to_contain_text("You hold the link")
        page.click("#apply")
        expect(page.locator("#band")).to_have_class("band live")
        for section, sub in PAGES:
            go(page, section, sub)
            if sub == "endpoints-places":
                page.locator("#places details[data-id='tokyo'] summary").click()
                expect(page.locator("#places details[data-id='tokyo'] .channel")).to_have_count(12)
            shot(page, sub)
    finally:
        context.close()


# -- the house style's measured points (spec: "The page follows the house style") ------------

REPO = "https://github.com/ysern/wanpire"

TOKEN_JS = """(name) => {
  const e = document.createElement("span");
  e.style.color = `var(${name})`;
  document.body.append(e);
  const c = getComputedStyle(e).color;
  e.remove();
  return c;
}"""


def token(page, name):
    """A custom property's colour as the browser states it, `rgb(r, g, b)`."""
    return page.evaluate(TOKEN_JS, name)


def box_of(page, selector):
    return page.locator(selector).first.bounding_box()


def style_of(page, selector, prop):
    return page.locator(selector).first.evaluate(f"e => getComputedStyle(e).{prop}")


def test_the_band_has_two_rows_on_the_column(page):
    page.set_viewport_size({"width": 1280, "height": 900})
    sign_in(page)
    expect(page.locator("#mode")).to_have_text("bridge")
    band, brand, link = box_of(page, "#band"), box_of(page, ".brand"), box_of(page, "#band-link")
    sections, inner = box_of(page, ".sections"), box_of(page, ".band-inner")
    assert 160 <= band["height"] <= 180, band
    assert link["y"] >= brand["y"] + brand["height"] - 1, "the link line is under the mark"
    assert abs(link["x"] - brand["x"]) < 2, "aligned to the mark's left"
    assert sections["y"] >= link["y"] + link["height"] - 1, "the sections are a row of their own"
    pad = float(style_of(page, ".band-inner", "paddingLeft").rstrip("px"))
    first = box_of(page, ".sections a:first-child")
    assert abs(first["x"] - (inner["x"] + pad)) < 2, "the first section starts at the column"
    # left-aligned, each as far from the next as the band is from the frame below it
    frame_gap = box_of(page, ".frame")["y"] - (band["y"] + band["height"])
    boxes = [page.locator(".sections a").nth(i).bounding_box()
             for i in range(page.locator(".sections a").count())]
    for a, b in zip(boxes, boxes[1:]):
        assert abs(b["x"] - (a["x"] + a["width"]) - frame_gap) < 2, (a, b, frame_gap)
    assert "mono" not in style_of(page, "#band-link", "fontFamily")
    assert style_of(page, "#band-link", "fontSize") == "14px"
    assert style_of(page, "#band-link", "fontWeight") == "400"
    page.hover("#nav-broker")
    assert style_of(page, "#nav-broker .label", "textDecorationLine") == "underline"


def test_the_menu_is_on_the_tint_as_tall_as_the_content(page):
    sign_in(page)
    go(page, "link", "link-traffic")
    nav = "#side-link"
    assert style_of(page, nav, "backgroundColor") == token(page, "--tint")
    side, main = box_of(page, nav), box_of(page, "main")
    assert abs(side["height"] - main["height"]) <= 1, (side, main)
    assert abs(side["x"] + side["width"] + 24 - main["x"]) <= 1, "24 px between the menu and the content"
    group = box_of(page, f"{nav} .group")
    assert abs(group["width"] - side["width"]) < 1, "the open group is the menu's full width"
    assert style_of(page, f"{nav} .group", "backgroundColor") == token(page, "--accent")
    assert 39 <= group["height"] <= 41
    assert 39 <= box_of(page, "#sub-link-traffic")["height"] <= 41
    assert style_of(page, "#sub-link-traffic", "fontWeight") == "700"
    assert style_of(page, "#sub-link-traffic", "color") == token(page, "--text")
    assert style_of(page, "#sub-link-set", "color") == token(page, "--muted")
    assert style_of(page, "#sub-link-set", "fontWeight") == "400"


def test_the_accent_marks_two_things(page):
    sign_in(page)
    go(page, "endpoints")
    page.locator("#places details[data-id='tokyo'] summary").click()
    expect(page.locator("#places details[data-id='tokyo'] .channel")).to_have_count(12)
    accent = token(page, "--accent")
    painted = page.evaluate("""(accent) => [...document.querySelectorAll("body *")]
      .filter((e) => e.checkVisibility() && getComputedStyle(e).backgroundColor === accent)
      .map((e) => e.tagName + "." + e.className)""", accent)
    assert len(painted) == 2, painted
    assert style_of(page, ".tag", "backgroundColor") != accent
    assert style_of(page, ".tag", "fontSize") == "13px"


def test_panels_measure(page):
    sign_in(page)
    expect(page.locator("#mode")).to_have_text("bridge")
    panels = page.locator("#page-link-set section.panel")
    boxes = [panels.nth(i).bounding_box() for i in range(panels.count())]
    for i in range(panels.count()):
        pad = float(panels.nth(i).evaluate("e => getComputedStyle(e).paddingTop").rstrip("px"))
        assert 36 <= pad <= 44, pad
    for a, b in zip(boxes, boxes[1:]):
        assert abs(b["y"] - (a["y"] + a["height"]) - 16) < 1, "16 px between panels"


def test_one_kind_of_button(page):
    from .test_web_ui import agent_asks
    agent_asks(page.box)
    sign_in(page)
    danger = token(page, "--danger")
    for section, sub in PAGES:
        go(page, section, sub)
        assert page.locator(f"#page-{sub} .secondary").count() == 0, sub
        for sec in page.locator(f"#page-{sub} section.panel").all():
            assert sec.locator("button:not(.action):not(.eye):not([hidden])").count() <= 1, sub
        for b in page.locator(f"#page-{sub} button.primary").all():
            if not b.is_visible():
                continue
            assert 28 <= b.bounding_box()["height"] <= 30, sub
            assert b.evaluate("e => getComputedStyle(e).textTransform") == "uppercase"
            assert b.evaluate("e => getComputedStyle(e).fontWeight") == "400"
    go(page, "link", "link-set")
    assert style_of(page, "#clear", "color") == danger
    go(page, "broker")
    expect(page.locator("#end-lease")).to_be_visible()
    assert style_of(page, "#end-lease", "color") == danger
    assert "action" in page.locator("#end-lease").get_attribute("class")
    head = box_of(page, "#page-broker-queue .head")
    assert abs(box_of(page, "#end-lease")["y"] - head["y"]) < 12, "in the section's head"
    go(page, "settings")
    assert "primary" in page.locator("#signout").get_attribute("class")
    assert style_of(page, "#release", "fontWeight") == "400"
    assert style_of(page, "#lease-state", "fontWeight") == "400"


def test_tables_measure(page):
    sign_in(page)
    go(page, "broker")
    rows = page.locator("#queue tbody tr")
    expect(rows).to_have_count(1)
    assert rows.first.locator("td").count() == 1, "the empty queue is one pill with one line"
    assert style_of(page, "#queue tbody td", "color") == token(page, "--muted")
    expect(rows.first).to_contain_text("Nobody")
    assert 50 <= rows.first.bounding_box()["height"] <= 62
    go(page, "link", "link-set")
    page.fill("#purpose", "a row")
    page.click("#ask")
    expect(page.locator("#lease-state")).to_contain_text("You hold the link")
    go(page, "broker")
    expect(page.locator("#queue tbody")).to_contain_text("web: admin")
    assert 50 <= box_of(page, "#queue tbody tr")["height"] <= 62
    go(page, "adapters")
    expect(page.locator("#adapters-table")).to_contain_text("---")
    assert 50 <= box_of(page, "#adapters-table tbody tr")["height"] <= 62


def test_the_footer_is_the_last_panels_action_row(page):
    sign_in(page)
    foot = page.locator("main footer")
    expect(foot).to_be_visible()
    action = foot.locator("a.foot-action")
    assert action.get_attribute("href") == REPO
    expect(action).to_have_text("Source")
    assert action.locator("svg").count() == 1
    assert style_of(page, "a.foot-action", "textTransform") == "uppercase"
    assert style_of(page, "a.foot-action", "color") == token(page, "--text")
    assert style_of(page, "footer .foot-row", "borderTopWidth") == "1px"
    assert style_of(page, "footer .foot-row", "borderTopColor") == token(page, "--hair")
    last = page.locator("#page-link-set section.panel").last.bounding_box()
    fb = foot.bounding_box()
    assert abs(fb["y"] - (last["y"] + last["height"])) < 1, "joined to the last panel"
    assert style_of(page, "main footer", "backgroundColor") == token(page, "--panel")
    row, act = box_of(page, "footer .foot-row"), action.bounding_box()
    assert abs((act["x"] + act["width"]) - (row["x"] + row["width"])) < 1, "right-aligned"


def test_the_sign_in_page_wears_the_band(page):
    page.goto(page.box.url + "/")
    expect(page.locator("#password")).to_be_visible()
    bg = style_of(page, ".signin-wrap", "backgroundImage")
    assert "gradient" in bg and token(page, "--band-1") in bg and token(page, "--band-2") in bg
    expect(page.locator(".signin-top .name")).to_have_text("wanpire")
    assert style_of(page, ".signin-top .name", "color") == token(page, "--band-ink")
    assert style_of(page, "#signin", "paddingLeft") == "44px"


def test_a_password_can_be_shown(page):
    page.goto(page.box.url + "/")
    page.fill("#password", "secret")
    eye = page.locator("button.eye[aria-controls='password']")
    assert page.get_attribute("#password", "type") == "password"
    eye.click()
    assert page.get_attribute("#password", "type") == "text"
    assert eye.get_attribute("aria-pressed") == "true"
    eye.click()
    assert page.get_attribute("#password", "type") == "password"


def test_the_dialog_for_ending_a_lease(page):
    from .test_web_ui import agent_asks
    agent_asks(page.box)
    sign_in(page)
    go(page, "broker")
    page.click("#end-lease")
    dialog = page.locator("#end-dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("agent-7")
    assert dialog.locator("button.primary").count() == 1
    assert "action" in dialog.locator("#end-cancel").get_attribute("class")
    assert style_of(page, "#end-dialog .dialog-head", "backgroundColor") == token(page, "--tint")
    assert dialog.evaluate("d => getComputedStyle(d, '::backdrop').backgroundColor") == "rgba(0, 0, 0, 0.45)"
    page.click("#end-cancel")
    expect(dialog).to_be_hidden()
    assert page.box.broker.status()["holder"]["who"] == "agent-7"
