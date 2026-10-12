"""The access point's place in the two modes. No root: pyroute2 is replaced by a fake that
records what is asked of it, hostapd by a fake access point."""

import pytest

from wanpire.access_point import AccessPointFailed
from wanpire.config import Config
from wanpire.modes import Modes, ModeRefused

AP = {"ssid": "lab-ap", "passphrase": "correct horse"}


class FakeIPR:
    def __init__(self, names):
        self.index = {n: i for i, n in enumerate(names, start=2)}
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def link_lookup(self, ifname):
        return [self.index[ifname]] if ifname in self.index else []

    def get_addr(self, index):
        return []

    def link(self, action, **kw):
        self.calls.append(("link", action, kw))
        if action == "add":
            self.index[kw["ifname"]] = max(self.index.values()) + 1

    def addr(self, action, **kw):
        self.calls.append(("addr", action, kw))

    def name(self, idx):
        return {v: k for k, v in self.index.items()}[idx]


class FakeAP:
    def __init__(self, fail=False):
        self.started, self.stopped, self.fail = [], [], fail

    def start(self, adapter, ap, country, bridge=None):
        if self.fail:
            raise AccessPointFailed(f"the access point on {adapter} did not come up: no channel")
        self.started.append((adapter, ap["ssid"], country, bridge))

    def stop(self, adapter):
        self.stopped.append(adapter)


def modes(tmp_path, ipr, ap):
    m = Modes(state_dir=str(tmp_path), runner=lambda argv, check=True: "0\n", access_point=ap)
    m._ipr = lambda: ipr
    return m


def cfg(mode, inbound="eth0", out="wlan1", wifi=("wlan1",)):
    return Config(mode=mode, control="wlan0", inbound=inbound, outbound=(out,),
                  access_points={"wlan1": AP}, country="GB", wifi_roles=wifi)


def test_bridge_mode_starts_the_access_point_as_a_bridge_port(tmp_path):
    ipr, ap = FakeIPR(["eth0", "wlan0", "wlan1"]), FakeAP()
    modes(tmp_path, ipr, ap).up(cfg("bridge"))
    assert ap.started == [("wlan1", "lab-ap", "GB", "wpbr0")]
    masters = [ipr.name(kw["index"]) for _, action, kw in ipr.calls
               if action == "set" and "master" in kw]
    assert masters == ["eth0"]  # hostapd puts wlan1 in the bridge itself


def test_router_mode_starts_it_with_no_bridge_and_the_router_address(tmp_path):
    ipr, ap = FakeIPR(["eth0", "wlan0", "wlan1"]), FakeAP()
    m = modes(tmp_path, ipr, ap)
    m._nft_up = lambda c: None
    m._dhcp_up = lambda c: None
    m.up(cfg("router"))
    assert ap.started == [("wlan1", "lab-ap", "GB", None)]
    assert [kw["address"] for kind, action, kw in ipr.calls if kind == "addr"] == ["10.77.0.1"]


def test_a_wired_line_starts_no_access_point(tmp_path):
    ipr, ap = FakeIPR(["eth0", "eth1", "wlan0"]), FakeAP()
    modes(tmp_path, ipr, ap).up(Config(mode="bridge", control="wlan0", inbound="eth0",
                                       outbound=("eth1",)))
    assert ap.started == []


def test_down_stops_the_line_adapters_access_points_never_control(tmp_path):
    ipr, ap = FakeIPR(["eth0", "wlan0", "wlan1"]), FakeAP()
    m = modes(tmp_path, ipr, ap)
    m.down(cfg("bridge"))
    m.down(cfg("bridge"))
    assert set(ap.stopped) == {"eth0", "wlan1"} and "wlan0" not in ap.stopped


def test_an_access_point_that_does_not_come_up_fails_the_set_up(tmp_path):
    ipr = FakeIPR(["eth0", "wlan0", "wlan1"])
    with pytest.raises(ModeRefused, match="no channel"):
        modes(tmp_path, ipr, FakeAP(fail=True)).up(cfg("bridge"))


# -- a Wi-Fi inbound adapter joins a network as a client, in router mode ----------------------

NET = {"ssid": "upstream", "passphrase": ""}


class FakeClient:
    def __init__(self, fail=False, gateway="192.0.2.1"):
        self.started, self.stopped, self.fail, self.gw = [], [], fail, gateway

    def start(self, adapter, net, country):
        if self.fail:
            from wanpire.wifi_client import WifiClientFailed
            raise WifiClientFailed(f"{adapter} did not join {net['ssid']}: wrong key")
        self.started.append((adapter, net["ssid"]))

    def gateway(self, adapter):
        return self.gw

    def stop(self, adapter):
        self.stopped.append(adapter)


def client_modes(tmp_path, ipr, wifi_client, runner=None):
    calls = []
    m = Modes(state_dir=str(tmp_path), runner=runner or (
        lambda argv, check=True: calls.append(list(argv)) or "0\n"),
        access_point=FakeAP(), wifi_client=wifi_client)
    m._ipr = lambda: ipr
    m._nft_up = lambda c: None
    m._dhcp_up = lambda c: None
    m.calls = calls
    return m


def client_cfg():
    return Config(mode="router", control="wlan0", inbound="wlan1", outbound=("eth1",),
                  wifi_clients={"wlan1": NET}, wifi_roles=("wlan1",))


def test_router_mode_joins_the_network_and_routes_the_line_out_through_it(tmp_path):
    wc = FakeClient()
    m = client_modes(tmp_path, FakeIPR(["eth1", "wlan0", "wlan1"]), wc)
    m.up(client_cfg())
    assert wc.started == [("wlan1", "upstream")]
    assert ["ip", "-4", "route", "replace", "default", "via", "192.0.2.1", "dev", "wlan1",
            "table", "4077"] in m.calls
    assert ["ip", "-4", "rule", "add", "iif", "eth1", "lookup", "4077", "priority",
            "4077"] in m.calls
    for call in m.calls:
        assert "wlan0" not in call


def test_a_network_not_joined_fails_the_set_up(tmp_path):
    m = client_modes(tmp_path, FakeIPR(["eth1", "wlan0", "wlan1"]), FakeClient(fail=True))
    with pytest.raises(ModeRefused, match="wlan1 did not join upstream"):
        m.up(client_cfg())


def test_no_gateway_fails_the_set_up(tmp_path):
    m = client_modes(tmp_path, FakeIPR(["eth1", "wlan0", "wlan1"]), FakeClient(gateway=None))
    with pytest.raises(ModeRefused, match="no gateway"):
        m.up(client_cfg())


def test_down_leaves_the_network_and_removes_the_route(tmp_path):
    wc = FakeClient()
    m = client_modes(tmp_path, FakeIPR(["eth1", "wlan0", "wlan1"]), wc)
    m.down(client_cfg())
    m.down(client_cfg())
    assert wc.stopped == ["wlan1", "wlan1"] and "wlan0" not in wc.stopped
    assert ["ip", "-4", "rule", "del", "priority", "4077"] in m.calls
    assert ["ip", "-4", "route", "flush", "table", "4077"] in m.calls


def test_a_wired_router_line_joins_nothing(tmp_path):
    wc = FakeClient()
    m = client_modes(tmp_path, FakeIPR(["eth0", "eth1", "wlan0"]), wc)
    m.up(Config(mode="router", control="wlan0", inbound="eth0", outbound=("eth1",)))
    assert wc.started == [] and not [c for c in m.calls if "rule" in c]
