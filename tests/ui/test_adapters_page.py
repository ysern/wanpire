"""The Adapters / Roles page: the inbound and outbound drop-downs, the network to join beside a
Wi-Fi inbound adapter, the access point's fields beside a Wi-Fi outbound one, and Save
(host-a-wifi-access-point)."""

from wanpire.config import config_from_dict

from .conftest import CONFIG, sign_in


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
    assert page.is_hidden("#net-inbound") and page.is_hidden("#ap-outbound")


def test_picking_a_wifi_adapter_shows_its_name_and_password(page):
    open_roles(page)
    page.select_option("#role-outbound", "wlan1")
    assert page.is_visible("#ap-outbound-ssid") and page.is_visible("#ap-outbound-pass")
    assert page.is_hidden("#net-inbound")
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


# -- a Wi-Fi inbound adapter joins a network as a client (the owner, 2026-10-11) -------------

def router_mode(page):
    page.box.roles.config = config_from_dict(dict(CONFIG.to_dict(), mode="router"),
                                             {a.name: a for a in page.box.roles.list_adapters()})


def test_picking_a_wifi_inbound_shows_the_network_to_join(page):
    open_roles(page)
    page.select_option("#role-inbound", "wlan1")
    assert page.is_visible("#net-inbound-ssid") and page.is_visible("#net-inbound-pass")
    assert "join" in page.inner_text("label[for='net-inbound-ssid']").lower()
    assert page.is_hidden("#ap-outbound")


def test_a_wifi_inbound_in_bridge_mode_is_refused_and_nothing_sent(page):
    open_roles(page)
    page.select_option("#role-inbound", "wlan1")
    page.fill("#net-inbound-ssid", "upstream")
    page.click("#roles-save")
    page.wait_for_selector("#role-error:has-text('router mode')")
    assert page.box.modes.calls == []


def test_a_client_password_outside_the_rules_is_refused_beside_it(page):
    router_mode(page)
    open_roles(page)
    page.select_option("#role-inbound", "wlan1")
    page.fill("#net-inbound-ssid", "upstream")
    page.fill("#net-inbound-pass", "short")
    page.click("#roles-save")
    page.wait_for_selector("#net-inbound-pass-error:has-text('64 hexadecimal')")
    assert page.box.modes.calls == []


def test_an_open_network_to_join_is_saved_in_router_mode(page):
    router_mode(page)
    open_roles(page)
    page.select_option("#role-inbound", "wlan1")
    page.fill("#net-inbound-ssid", "upstream")
    page.click("#roles-save")
    page.wait_for_selector("#roles-message:has-text('saved')")
    assert page.box.roles.config.inbound == "wlan1"
    assert page.box.roles.config.wifi_client("wlan1") == {"ssid": "upstream", "passphrase": ""}
    page.wait_for_selector("#adapters-table tr:has(td:text-is('wlan1')) td:text-is('inbound')")
