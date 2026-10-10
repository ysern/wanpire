"""The page's look: sections, nothing fetched elsewhere, no sideways scroll and WCAG AA contrast
at 720 and 1,280 px in both themes (spec: web-ui, the look's requirements)."""

import pytest
from playwright.sync_api import expect

from .conftest import sign_in

SECTIONS = ["link", "endpoints", "broker", "adapters", "settings"]
PAGES = [("link", "link-set"), ("link", "link-counters"), ("endpoints", "endpoints-places"),
         ("broker", "broker-queue"), ("adapters", "adapters-list"), ("settings", "settings-access")]

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
    expect(page.locator("#nav-link")).to_have_attribute("aria-current", "page")
    expect(page.locator("#nav-link")).to_contain_text("Link")
    go(page, "broker")
    expect(page.locator("#nav-broker")).to_have_attribute("aria-current", "page")
    expect(page.locator("#nav-link")).not_to_have_attribute("aria-current", "page")
    expect(page.locator("#queue")).to_be_visible()


def test_the_side_menu_marks_the_current_page(page):
    sign_in(page)
    expect(page.locator("#sub-link-set")).to_have_attribute("aria-current", "page")
    go(page, "link", "link-counters")
    expect(page.locator("#sub-link-counters")).to_have_attribute("aria-current", "page")
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
    expect(page.locator("#endpoints-table")).to_contain_text("Tokyo")


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

@pytest.mark.parametrize("width", [720, 1280])
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
