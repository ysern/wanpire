"""The main configuration and the rules on mapping adapters to roles. No root, no network."""

import pytest

from wanpire.adapters import Adapter
from wanpire.config import InvalidConfig, config_from_dict


def adapter(name, kind):
    return Adapter(name=name, kind=kind, mac="00:00:00:00:00:00", state="up", speed_mbit=1000,
                   can_be_ap=kind == "wifi")


BOX = {a.name: a for a in (adapter("eth0", "ethernet"), adapter("eth1", "usb-ethernet"),
                           adapter("wlan0", "wifi"))}


def doc(mode="bridge", control="wlan0", inbound="eth0", outbound=("eth1",), **over):
    d = {"schema": "wanpire-config/1", "mode": mode,
         "adapters": {"control": control, "inbound": inbound, "outbound": list(outbound)}}
    d.update(over)
    return d


def test_a_valid_configuration():
    c = config_from_dict(doc(), BOX)
    assert (c.mode, c.control, c.inbound, c.outbound) == ("bridge", "wlan0", "eth0", ("eth1",))
    assert c.role("eth1") == "outbound" and c.role("wlan0") == "control"


def test_two_outbound_adapters_are_refused():
    with pytest.raises(InvalidConfig, match="one outbound adapter"):
        config_from_dict(doc(outbound=("eth1", "eth0")), BOX)


def test_outbound_also_control_is_refused_with_why():
    with pytest.raises(InvalidConfig, match="outbound shares its adapter with nothing.*impairment"):
        config_from_dict(doc(mode="router", control="eth1"), BOX)


def test_outbound_also_inbound_is_refused():
    with pytest.raises(InvalidConfig, match="outbound shares its adapter with nothing"):
        config_from_dict(doc(mode="router", inbound="eth1"), BOX)


def test_control_and_inbound_may_share_in_router_mode():
    c = config_from_dict(doc(mode="router", control="eth0", inbound="eth0"), BOX)
    assert c.role("eth0") == "control+inbound"


def test_a_missing_adapter_is_named_with_the_ones_the_box_has():
    with pytest.raises(InvalidConfig, match=r"eth9.*eth0, eth1, wlan0"):
        config_from_dict(doc(outbound=("eth9",)), BOX)


def test_control_on_a_bridge_port_is_refused():
    with pytest.raises(InvalidConfig, match="control cannot be a bridge port"):
        config_from_dict(doc(control="eth0"), BOX)


# -- Wi-Fi adapters in a role are access points (host-a-wifi-access-point) -------------------

AP_BOX = dict(BOX, wlan1=adapter("wlan1", "wifi"),
              wlan2=Adapter(name="wlan2", kind="wifi", mac="00:00:00:00:00:00", state="down",
                            speed_mbit=None, can_be_ap=False))
AP = {"ssid": "lab-ap", "passphrase": "correct horse"}
WIFI = {"country": "GB"}


def ap_doc(mode="bridge", inbound="eth0", outbound=("wlan1",), aps=None, wifi=WIFI, **over):
    d = doc(mode=mode, inbound=inbound, outbound=outbound, **over)
    d["access_points"] = {"wlan1": AP} if aps is None else aps
    if wifi is not None:
        d["wifi"] = wifi
    return d


def test_a_wifi_access_point_as_a_bridge_port():
    c = config_from_dict(ap_doc(), AP_BOX)
    assert c.outbound == ("wlan1",) and c.country == "GB"
    assert c.access_point("wlan1") == AP and c.access_point("eth0") is None
    assert c.access_point_adapters == ("wlan1",)


def test_a_wifi_access_point_as_outbound_in_router_mode():
    c = config_from_dict(ap_doc(mode="router"), AP_BOX)
    assert c.access_point_adapters == ("wlan1",)


def test_a_radio_that_cannot_be_an_access_point_is_refused():
    with pytest.raises(InvalidConfig, match="wlan2 cannot be an access point"):
        config_from_dict(ap_doc(outbound=("wlan2",), aps={"wlan2": AP}), AP_BOX)


def test_a_wifi_outbound_without_its_network_is_refused():
    with pytest.raises(InvalidConfig, match="wlan1 needs a network name and a password"):
        config_from_dict(ap_doc(aps={}), AP_BOX)


# -- a Wi-Fi inbound adapter is a client of a network (the owner, 2026-10-11) ----------------

NET = {"ssid": "upstream", "passphrase": "correct horse"}


def client_doc(mode="router", inbound="wlan1", outbound=("eth1",), nets=None, **over):
    d = doc(mode=mode, inbound=inbound, outbound=outbound, **over)
    d["wifi_clients"] = {"wlan1": NET} if nets is None else nets
    return d


def test_a_wifi_inbound_joins_a_network_in_router_mode():
    c = config_from_dict(client_doc(), AP_BOX)
    assert c.client_adapter == "wlan1" and c.wifi_client("wlan1") == NET
    assert c.access_point_adapters == () and c.access_point("wlan1") is None
    assert c.to_dict()["wifi_clients"] == {"wlan1": NET}


def test_a_wifi_inbound_needs_no_country_and_no_ap_mode():
    c = config_from_dict(client_doc(inbound="wlan2", nets={"wlan2": NET}), AP_BOX)
    assert c.client_adapter == "wlan2" and c.country is None


def test_a_wifi_inbound_in_bridge_mode_is_refused_with_why():
    with pytest.raises(InvalidConfig, match="a Wi-Fi client cannot be a bridge port.*router mode"):
        config_from_dict(client_doc(mode="bridge"), AP_BOX)


def test_a_wifi_inbound_without_its_network_is_refused():
    with pytest.raises(InvalidConfig, match="wlan1 needs the network to join"):
        config_from_dict(client_doc(nets={}), AP_BOX)


def test_an_access_point_for_the_inbound_adapter_does_not_count_as_its_network():
    d = client_doc(nets={})
    d["access_points"] = {"wlan1": AP}
    with pytest.raises(InvalidConfig, match="wlan1 needs the network to join"):
        config_from_dict(d, AP_BOX)


@pytest.mark.parametrize("passphrase", ["", "eight888", "x" * 63, "ab" * 32])
def test_a_client_password_inside_the_rules(passphrase):
    net = {"ssid": "upstream", "passphrase": passphrase}
    c = config_from_dict(client_doc(nets={"wlan1": net}), AP_BOX)
    assert c.wifi_client("wlan1") == net


@pytest.mark.parametrize("passphrase", ["seven77", "x" * 64, "ab" * 32 + "a", "g" * 64,
                                        "café-latte", None])
def test_a_client_password_outside_the_rules_is_refused(passphrase):
    with pytest.raises(InvalidConfig, match="8 to 63 printable ASCII.*64 hexadecimal.*empty"):
        config_from_dict(client_doc(nets={"wlan1": {"ssid": "up", "passphrase": passphrase}}),
                         AP_BOX)


@pytest.mark.parametrize("ssid", ["", "x" * 33])
def test_a_client_network_name_outside_the_rules_is_refused(ssid):
    with pytest.raises(InvalidConfig, match="1 to 32 bytes"):
        config_from_dict(client_doc(nets={"wlan1": {"ssid": ssid, "passphrase": ""}}), AP_BOX)


def test_the_control_adapter_never_joins_a_network_here():
    with pytest.raises(InvalidConfig, match="control"):
        config_from_dict(doc(mode="router", control="wlan1", inbound="eth0", outbound=("eth1",),
                             wifi_clients={"wlan1": NET}), AP_BOX)


def test_a_wifi_client_inbound_and_an_access_point_outbound_in_router_mode():
    d = client_doc(outbound=("wlan2",), nets={"wlan1": NET})
    box = dict(AP_BOX, wlan2=adapter("wlan2", "wifi"))
    d["access_points"], d["wifi"] = {"wlan2": AP}, WIFI
    c = config_from_dict(d, box)
    assert c.client_adapter == "wlan1" and c.access_point_adapters == ("wlan2",)


@pytest.mark.parametrize("passphrase", ["seven77", "x" * 64, "tab\there!", "café-latte"])
def test_a_password_outside_the_rules_is_refused(passphrase):
    with pytest.raises(InvalidConfig, match="8 to 63 printable ASCII"):
        config_from_dict(ap_doc(aps={"wlan1": {"ssid": "lab", "passphrase": passphrase}}),
                         AP_BOX)


@pytest.mark.parametrize("passphrase", ["eight888", "x" * 63, "with spaces ~!"])
def test_a_password_inside_the_rules(passphrase):
    c = config_from_dict(ap_doc(aps={"wlan1": {"ssid": "lab", "passphrase": passphrase}}),
                         AP_BOX)
    assert c.access_point("wlan1")["passphrase"] == passphrase


@pytest.mark.parametrize("ssid", ["", "x" * 33, "é" * 17, 7])
def test_a_name_outside_the_rules_is_refused(ssid):
    with pytest.raises(InvalidConfig, match="1 to 32 bytes"):
        config_from_dict(ap_doc(aps={"wlan1": {"ssid": ssid, "passphrase": "eight888"}}),
                         AP_BOX)


def test_a_name_of_32_bytes_in_utf8_is_accepted():
    ssid = "é" * 16
    c = config_from_dict(ap_doc(aps={"wlan1": {"ssid": ssid, "passphrase": "eight888"}}),
                         AP_BOX)
    assert c.access_point("wlan1")["ssid"] == ssid


@pytest.mark.parametrize("wifi", [None, {}, {"country": "00"}, {"country": "gb"},
                                  {"country": "GBR"}])
def test_an_access_point_needs_the_country(wifi):
    with pytest.raises(InvalidConfig, match="regulatory country"):
        config_from_dict(ap_doc(wifi=wifi), AP_BOX)


def test_the_control_adapter_is_never_an_access_point():
    with pytest.raises(InvalidConfig, match="control"):
        config_from_dict(ap_doc(mode="router", control="wlan1", inbound="eth0",
                                outbound=("eth1",)), AP_BOX)


def test_a_wired_configuration_needs_no_wifi_settings():
    c = config_from_dict(doc(), AP_BOX)
    assert c.access_point_adapters == () and c.country is None
    assert c.client_adapter is None and "wifi_clients" not in c.to_dict()


def test_settings_for_an_adapter_in_no_role_are_kept_but_unused():
    c = config_from_dict(doc(access_points={"wlan1": AP}), AP_BOX)
    assert c.access_point_adapters == ()
    assert c.to_dict()["access_points"] == {"wlan1": AP}


def test_the_roles_are_written_back(tmp_path):
    from wanpire.config import load_config, save_config
    path = tmp_path / "wanpire.json"
    c = config_from_dict(doc(mode="router", router={"address": "10.5.0.1/24"}), AP_BOX)
    c2 = config_from_dict(dict(c.to_dict(), adapters={"control": "wlan0", "inbound": "eth0",
                                                      "outbound": ["wlan1"]},
                               access_points={"wlan1": AP}, wifi=WIFI), AP_BOX)
    save_config(c2, str(path))
    back = load_config(str(path), AP_BOX)
    assert (back.mode, back.control, back.inbound, back.outbound) == (
        "router", "wlan0", "eth0", ("wlan1",))
    assert back.router_address == "10.5.0.1/24" and back.access_point("wlan1") == AP
    assert back.country == "GB"
    import os
    import stat
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert not [p for p in tmp_path.iterdir() if p.name != "wanpire.json"]


def test_an_unknown_mode():
    with pytest.raises(InvalidConfig, match="bridge, router"):
        config_from_dict(doc(mode="hub"), BOX)


def test_the_schema_tag():
    with pytest.raises(InvalidConfig, match="wanpire-config/1"):
        config_from_dict(doc(schema="x"), BOX)


def test_without_an_adapter_list_only_the_mapping_rules_apply():
    assert config_from_dict(doc(outbound=("eth9",))).outbound == ("eth9",)


def test_router_defaults_and_its_own_address():
    c = config_from_dict(doc(mode="router", control="wlan0"), BOX)
    assert c.router_address == "10.77.0.1/24"
    c = config_from_dict(doc(mode="router", router={"address": "10.5.0.1/24"}), BOX)
    assert c.router_address == "10.5.0.1/24"


def test_a_router_address_must_be_a_private_host_address():
    with pytest.raises(InvalidConfig, match="router.address"):
        config_from_dict(doc(mode="router", router={"address": "10.5.0.0/24"}), BOX)
    with pytest.raises(InvalidConfig, match="private"):
        config_from_dict(doc(mode="router", router={"address": "8.8.8.1/24"}), BOX)
