"""The web UI in a headless browser, against the real app (spec: web-ui)."""

import re

import httpx
import pytest
from playwright.sync_api import expect

from .conftest import LEASE_TTL_S, TOKEN, sign_in

AUTH = {"Authorization": f"Bearer {TOKEN}"}


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


# -- served, and the token ------------------------------------------------------------------

def test_the_page_is_served_without_the_token(box):
    r = httpx.get(box.url + "/")
    assert r.status_code == 200
    assert "<title>wanpire</title>" in r.text
    assert httpx.get(box.url + "/api/v1/status").status_code == 401


def test_a_first_visit_asks_for_the_token(page):
    page.goto(page.box.url + "/")
    expect(page.locator("#token")).to_be_visible()
    sign_in(page)
    expect(page.locator("#token")).to_be_hidden()
    expect(page.locator("#mode")).to_have_text("bridge")
    expect(page.locator("#link-state")).to_have_text("no impairment")


def test_a_wrong_token_is_refused_and_asked_again(page):
    sign_in(page, token="wrong")
    expect(page.locator("#token-error")).to_contain_text("refused")
    expect(page.locator("#token")).to_be_visible()


def test_the_token_is_remembered(page):
    sign_in(page)
    expect(page.locator("#mode")).to_have_text("bridge")
    page.reload()
    expect(page.locator("#mode")).to_have_text("bridge")
    expect(page.locator("#token")).to_be_hidden()


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
    sign_in(page, name="ana")
    pick(page)
    expect(page.locator("#apply")).to_be_disabled()
    page.fill("#purpose", "trying a call")
    page.click("#ask")
    expect(page.locator("#lease-state")).to_contain_text("You hold the link")
    expect(page.locator("#holder")).to_contain_text("web: ana")
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
    expect(page.locator("#queue")).to_contain_text("web: ana")
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
