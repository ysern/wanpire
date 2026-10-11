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
