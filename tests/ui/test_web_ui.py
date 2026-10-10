"""The web UI in a headless browser, against the real app (spec: web-ui)."""

import re

import httpx
import pytest
from playwright.sync_api import expect

from .conftest import AUTH, LEASE_TTL_S, PASSWORD, USER, sign_in


def agent_asks(box, who="agent-7", purpose="soak test"):
    r = httpx.post(box.url + "/api/v1/lease", json={"who": who, "purpose": purpose},
                   headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()["ticket"]


def pick(page, near="london", near_channel=None, far="los-angeles", far_channel="mobile-4g"):
    page.select_option("#near-endpoint", near)
    if near_channel:
        page.select_option("#near-channel", near_channel)
    page.select_option("#far-endpoint", far)
    if far_channel:
        page.select_option("#far-channel", far_channel)


# -- served, the first visit and signing in -------------------------------------------------

def test_the_page_is_served_without_credentials(box):
    r = httpx.get(box.url + "/")
    assert r.status_code == 200
    assert "<title>wanpire</title>" in r.text
    assert httpx.get(box.url + "/api/v1/status").status_code == 401


def set_up(page, user="admin", password="twelve chars", again=None):
    page.goto(page.box.url + "/")
    page.fill("#setup-user", user)
    page.fill("#setup-password", password)
    page.fill("#setup-again", password if again is None else again)
    page.click("#setup-save")


def test_a_new_box_asks_to_make_the_account(new_page):
    new_page.goto(new_page.box.url + "/")
    expect(new_page.locator("#setup")).to_be_visible()
    expect(new_page.locator("#signin")).to_be_hidden()
    set_up(new_page)
    expect(new_page.locator("#setup")).to_be_hidden()
    expect(new_page.locator("#mode")).to_have_text("bridge")
    assert new_page.box.account.verify("admin", "twelve chars")
    new_page.goto(new_page.box.url + "/#settings")
    expect(new_page.locator("#me")).to_have_text("admin")


def test_setting_up_with_two_passwords_that_differ(new_page):
    set_up(new_page, again="twelve charz")
    expect(new_page.locator("#setup-error")).to_contain_text("differ")
    assert not new_page.box.account.exists()


def test_setting_up_with_a_short_password(new_page):
    set_up(new_page, password="short")
    expect(new_page.locator("#setup-error")).to_contain_text("8 characters")
    assert not new_page.box.account.exists()


def test_signing_in(page):
    page.goto(page.box.url + "/")
    expect(page.locator("#signin")).to_be_visible()
    expect(page.locator("#setup")).to_be_hidden()
    sign_in(page)
    expect(page.locator("#signin")).to_be_hidden()
    expect(page.locator("#mode")).to_have_text("bridge")
    expect(page.locator("#link-state")).to_have_text("no impairment")


def test_a_wrong_password_is_refused_and_asked_again(page):
    sign_in(page, password="wrong horse")
    expect(page.locator("#signin-error")).to_contain_text("refused")
    expect(page.locator("#password")).to_be_visible()


def test_coming_back_needs_no_sign_in(page):
    sign_in(page)
    expect(page.locator("#mode")).to_have_text("bridge")
    page.reload()
    expect(page.locator("#mode")).to_have_text("bridge")
    expect(page.locator("#signin")).to_be_hidden()


def test_no_credential_is_kept_in_the_browsers_storage(page):
    sign_in(page)
    expect(page.locator("#mode")).to_have_text("bridge")
    kept = page.evaluate("JSON.stringify([localStorage, sessionStorage])")
    assert PASSWORD not in kept and "token" not in kept.lower()
    cookies = page.context.cookies()
    assert cookies and all(c["httpOnly"] for c in cookies)
    assert page.evaluate("document.cookie") == ""


def test_signing_out(page):
    sign_in(page)
    expect(page.locator("#mode")).to_have_text("bridge")
    page.goto(page.box.url + "/#settings")
    page.click("#signout")
    expect(page.locator("#signin")).to_be_visible()
    page.reload()
    expect(page.locator("#signin")).to_be_visible()


def test_changing_the_password(page):
    sign_in(page)
    page.goto(page.box.url + "/#settings")
    page.fill("#pw-current", PASSWORD)
    page.fill("#pw-new", "battery staple")
    page.fill("#pw-again", "battery staple")
    page.click("#pw-save")
    expect(page.locator("#pw-message")).to_contain_text("changed")
    assert page.box.account.verify(USER, "battery staple")
    expect(page.locator("#mode")).to_have_text("bridge")  # still signed in


def test_changing_the_password_with_a_wrong_current_one(page):
    sign_in(page)
    page.goto(page.box.url + "/#settings")
    page.fill("#pw-current", "wrong horse")
    page.fill("#pw-new", "battery staple")
    page.fill("#pw-again", "battery staple")
    page.click("#pw-save")
    expect(page.locator("#pw-message")).to_contain_text("refused")
    expect(page.locator("#signin")).to_be_hidden()  # a wrong current password signs nobody out
    assert page.box.account.verify(USER, PASSWORD)


def test_a_reset_over_ssh_brings_the_first_visit_back(page):
    sign_in(page)
    expect(page.locator("#mode")).to_have_text("bridge")
    page.box.account.reset()  # `sudo wanpire account reset` on the box
    page.reload()
    expect(page.locator("#setup")).to_be_visible()


# -- the status line and the counters -------------------------------------------------------

def test_the_status_names_the_holder_and_the_queue(page):
    agent_asks(page.box, "agent-7", "soak test")
    agent_asks(page.box, "agent-8", "latency sweep")
    sign_in(page)
    expect(page.locator("#holder")).to_contain_text("agent-7")
    expect(page.locator("#holder")).to_contain_text("soak test")
    expect(page.locator("#holder")).to_contain_text(re.compile(r"\d+ s"))
    expect(page.locator("#queue-count")).to_have_text("1 waiting")
    expect(page.locator("#queue")).to_contain_text("agent-8")
    expect(page.locator("#queue")).to_contain_text("latency sweep")


def test_the_counters_are_shown(page):
    page.box.engine.applied = True
    page.box.engine.packets = 1000
    sign_in(page)
    expect(page.locator("#link-state")).to_have_text("impaired")
    expect(page.locator("#c-down-packets")).to_have_text("1,000")
    expect(page.locator("#c-down-dropped")).to_have_text("3")
    expect(page.locator("#c-down-shaper_dropped")).to_have_text("2")
    expect(page.locator("#c-up-packets")).to_have_text("0")


# -- endpoints, channels and the preview ----------------------------------------------------

def test_endpoints_and_their_channels_are_offered(page):
    sign_in(page)
    expect(page.locator("#near-endpoint option[value=london]")).to_have_text("London")
    expect(page.locator("#far-endpoint option[value=tokyo]")).to_have_text("Tokyo")
    page.select_option("#far-endpoint", "los-angeles")
    expect(page.locator("#far-channel")).to_have_value("generic")
    expect(page.locator("#far-channel option[value=mobile-4g]")).to_have_count(1)


def test_the_preview_shows_the_figures_and_leaves_the_link_alone(page):
    sign_in(page)
    pick(page)
    expect(page.locator("#down-delay_ms")).to_have_text("98.8")
    expect(page.locator("#up-rate_mbit")).to_have_text("8.9")
    expect(page.locator("#path")).to_contain_text("142.1 ms")
    expect(page.locator("#path")).to_contain_text("table")
    assert page.box.engine.calls == []


# -- the lease ------------------------------------------------------------------------------

def test_ask_apply_clear_release(page):
    sign_in(page)
    pick(page)
    expect(page.locator("#apply")).to_be_disabled()
    page.fill("#purpose", "trying a call")
    page.click("#ask")
    expect(page.locator("#lease-state")).to_contain_text("You hold the link")
    expect(page.locator("#holder")).to_contain_text("web: admin")
    page.click("#apply")
    expect(page.locator("#message")).to_contain_text("Applied")
    applied = [c for c in page.box.engine.calls if c[0] == "apply"]
    assert len(applied) == 1
    assert applied[0][2].down.delay_ms == pytest.approx(98.8)
    page.click("#clear")
    expect(page.locator("#message")).to_contain_text("Cleared")
    page.click("#release")
    expect(page.locator("#lease-state")).to_contain_text("You do not hold the link")
    assert page.box.broker.status()["holder"] is None


def test_queued_then_granted(page):
    ticket = agent_asks(page.box)
    sign_in(page)
    page.fill("#purpose", "trying a call")
    page.click("#ask")
    expect(page.locator("#lease-state")).to_contain_text("1st in the queue")
    expect(page.locator("#apply")).to_be_disabled()
    httpx.request("DELETE", page.box.url + "/api/v1/lease",
                  headers={**AUTH, "X-Wanpire-Ticket": ticket})
    expect(page.locator("#lease-state")).to_contain_text(
        "You hold the link", timeout=LEASE_TTL_S * 1000 * 2)
    expect(page.locator("#apply")).to_be_enabled()


def test_ended_elsewhere_is_said_with_its_reason(page):
    sign_in(page)
    page.fill("#purpose", "trying a call")
    page.click("#ask")
    expect(page.locator("#lease-state")).to_contain_text("You hold the link")
    page.box.broker.end_lease("bench needed")
    expect(page.locator("#lease-state")).to_contain_text(
        "bench needed", timeout=LEASE_TTL_S * 1000 * 2)
    expect(page.locator("#ask")).to_be_enabled()


# -- ending another's lease -----------------------------------------------------------------

def test_ending_another_lease_cancelled(page):
    agent_asks(page.box)
    sign_in(page)
    expect(page.locator("#holder")).to_contain_text("agent-7")
    page.click("#nav-broker")
    page.once("dialog", lambda d: d.dismiss())
    page.click("#end-lease")
    page.wait_for_timeout(300)
    assert page.box.broker.status()["holder"]["who"] == "agent-7"


def test_ending_another_lease_confirmed(page):
    ticket = agent_asks(page.box)
    sign_in(page)
    expect(page.locator("#holder")).to_contain_text("agent-7")
    page.click("#nav-broker")
    page.once("dialog", lambda d: d.accept("bench needed"))
    page.click("#end-lease")
    expect(page.locator("#holder")).to_have_text("nobody")
    r = httpx.post(page.box.url + "/api/v1/lease/poll",
                   headers={**AUTH, "X-Wanpire-Ticket": ticket})
    assert r.status_code == 410
    assert "bench needed" in r.json()["error"]


def test_no_end_lease_button_for_your_own(page):
    sign_in(page)
    page.fill("#purpose", "trying a call")
    page.click("#ask")
    expect(page.locator("#lease-state")).to_contain_text("You hold the link")
    page.click("#nav-broker")
    expect(page.locator("#queue")).to_contain_text("web: admin")
    expect(page.locator("#end-lease")).to_be_hidden()


# -- the look -------------------------------------------------------------------------------

def test_no_sideways_scroll_on_a_phone(page):
    page.set_viewport_size({"width": 360, "height": 740})
    page.box.engine.applied = True
    sign_in(page)
    pick(page)
    expect(page.locator("#down-delay_ms")).to_have_text("98.8")
    width = page.evaluate("document.documentElement.scrollWidth")
    assert width <= 360


def test_dark_mode_follows_the_preference(page):
    sign_in(page)
    page.emulate_media(color_scheme="light")
    light = page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.emulate_media(color_scheme="dark")
    dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert light != dark
    assert dark != "rgba(0, 0, 0, 0)"
