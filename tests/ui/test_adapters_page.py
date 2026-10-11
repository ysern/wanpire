"""The Adapters / Roles page: the inbound and outbound drop-downs, the access point's fields
beside a Wi-Fi adapter, and Save (host-a-wifi-access-point)."""

from .conftest import sign_in


def open_roles(page):
    sign_in(page)
    page.goto(page.box.url + "/#adapters/adapters-list")
    page.wait_for_selector("#role-outbound option[value='wlan1']", state="attached")


def options(page, sel):
    return page.eval_on_selector_all(f"{sel} option", "os => os.map(o => o.value)")


def test_the_drop_downs_offer_the_line_adapters_set_to_the_current_roles(page):
    open_roles(page)
    assert options(page, "#role-inbound") == ["eth0", "eth1", "wlan1"]
    assert options(page, "#role-outbound") == ["eth0", "eth1", "wlan1"]
    assert page.input_value("#role-inbound") == "eth0"
    assert page.input_value("#role-outbound") == "eth1"
    assert page.is_hidden("#ap-inbound") and page.is_hidden("#ap-outbound")


def test_picking_a_wifi_adapter_shows_its_name_and_password(page):
    open_roles(page)
    page.select_option("#role-outbound", "wlan1")
    assert page.is_visible("#ap-outbound-ssid") and page.is_visible("#ap-outbound-pass")
    assert page.is_hidden("#ap-inbound")
    page.select_option("#role-outbound", "eth1")
    assert page.is_hidden("#ap-outbound")


def test_the_same_adapter_twice_is_refused_and_nothing_sent(page):
    open_roles(page)
    page.select_option("#role-inbound", "eth1")
    page.click("#roles-save")
    page.wait_for_selector("#role-error:has-text('must differ')")
    assert page.box.modes.calls == []


def test_a_short_password_is_refused_beside_it(page):
    open_roles(page)
    page.select_option("#role-outbound", "wlan1")
    page.fill("#ap-outbound-ssid", "lab-ap")
    page.fill("#ap-outbound-pass", "short")
    page.click("#roles-save")
    page.wait_for_selector("#ap-outbound-pass-error:has-text('8 to 63 printable ASCII')")
    assert page.box.modes.calls == []


def test_a_name_too_long_is_refused_beside_it(page):
    open_roles(page)
    page.select_option("#role-outbound", "wlan1")
    page.fill("#ap-outbound-ssid", "é" * 17)
    page.fill("#ap-outbound-pass", "eight888")
    page.click("#roles-save")
    page.wait_for_selector("#ap-outbound-ssid-error:has-text('1 to 32 bytes')")
    assert page.box.modes.calls == []


def test_saved(page):
    open_roles(page)
    page.select_option("#role-outbound", "wlan1")
    page.fill("#ap-outbound-ssid", "lab-ap")
    page.fill("#ap-outbound-pass", "correct horse")
    page.click("#roles-save")
    page.wait_for_selector("#roles-message:has-text('saved')")
    assert page.box.roles.config.outbound == ("wlan1",)
    assert page.box.roles.config.access_point("wlan1") == {"ssid": "lab-ap",
                                                           "passphrase": "correct horse"}
    page.wait_for_selector("#adapters-table tr:has(td:text-is('wlan1')) td:text-is('outbound')")


def test_the_current_access_point_fills_its_fields(page):
    page.box.roles.change("eth0", "wlan1", {"wlan1": {"ssid": "lab-ap",
                                                       "passphrase": "correct horse"}})
    open_roles(page)
    assert page.input_value("#role-outbound") == "wlan1"
    assert page.input_value("#ap-outbound-ssid") == "lab-ap"
    assert page.input_value("#ap-outbound-pass") == "correct horse"


def test_a_refusal_from_the_box_is_said(page):
    open_roles(page)
    page.box.engine.applied = True
    page.select_option("#role-inbound", "eth1")
    page.select_option("#role-outbound", "eth0")
    page.click("#roles-save")
    page.wait_for_selector("#roles-message:has-text('no link applied')")


def test_no_sideways_scroll_on_a_phone_with_the_wifi_fields(page):
    page.set_viewport_size({"width": 360, "height": 740})
    open_roles(page)
    page.select_option("#role-outbound", "wlan1")
    page.fill("#ap-outbound-pass", "short")
    page.click("#roles-save")
    page.wait_for_selector("#ap-outbound-pass-error:has-text('8 to 63')")
    assert page.evaluate("document.documentElement.scrollWidth") <= 360
