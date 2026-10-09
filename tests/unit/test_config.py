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


def test_wifi_as_a_bridge_port_is_refused():
    with pytest.raises(InvalidConfig, match="Wi-Fi client cannot be a bridge port"):
        config_from_dict(doc(inbound="wlan0", control="eth1", outbound=("eth0",)), BOX)


def test_control_on_a_bridge_port_is_refused():
    with pytest.raises(InvalidConfig, match="control cannot be a bridge port"):
        config_from_dict(doc(control="eth0"), BOX)


def test_wifi_outbound_is_not_built_yet():
    with pytest.raises(InvalidConfig, match="access point.*not built"):
        config_from_dict(doc(mode="router", control="eth0", inbound="eth0",
                             outbound=("wlan0",)), BOX)


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
