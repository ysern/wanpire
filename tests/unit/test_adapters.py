"""The adapter list, from a fake sysfs tree and a recorded ``iw``. No root, no network."""

import os

import pytest

from wanpire.adapters import list_adapters

IW_AP = """Wiphy phy0
\tSupported interface modes:
\t\t * IBSS
\t\t * managed
\t\t * AP
\t\t * P2P-client
\tBand 1:
"""
IW_NO_AP = """Wiphy phy0
\tSupported interface modes:
\t\t * managed
\tBand 1:
\t\tCapabilities: 0x1020 (AP isolation is not a mode)
"""


def make_net(tmp_path, name, mac="aa:bb:cc:dd:ee:01", state="up", speed="1000", device=None,
             wifi=False):
    d = tmp_path / "class" / "net" / name
    d.mkdir(parents=True)
    (d / "address").write_text(mac + "\n")
    (d / "operstate").write_text(state + "\n")
    if speed is not None:
        (d / "speed").write_text(speed + "\n")
    if device:
        target = tmp_path / "devices" / device
        target.mkdir(parents=True)
        os.symlink(target, d / "device")
    if wifi:
        (d / "wireless").mkdir()
        (d / "phy80211").mkdir()
        (d / "phy80211" / "name").write_text("phy0\n")
    return d


@pytest.fixture
def sysfs(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("no symlinks")
    try:
        make_net(tmp_path, "eth0", device="platform/fd580000.ethernet")
        make_net(tmp_path, "eth1", mac="aa:bb:cc:dd:ee:02", speed="100",
                 device="platform/scb/pcie/usb2/2-1/2-1:1.0")
        make_net(tmp_path, "wlan0", mac="aa:bb:cc:dd:ee:03", speed=None,
                 device="platform/mmc/mmc1:0001:1", wifi=True)
        make_net(tmp_path, "br0", state="down", speed="-1")
        make_net(tmp_path, "lo", mac="00:00:00:00:00:00", state="unknown")
    except OSError:
        pytest.skip("cannot create symlinks here")
    return tmp_path / "class" / "net"


def iw(answer):
    def run(argv, check=True):
        assert argv[:2] == ["iw", "phy"]
        return answer
    return run


def test_a_box_with_a_usb_adapter(sysfs):
    by = {a.name: a for a in list_adapters(str(sysfs), runner=iw(IW_AP))}
    assert set(by) == {"eth0", "eth1", "wlan0", "br0"}  # no loopback
    assert by["eth0"].kind == "ethernet"
    assert by["eth1"].kind == "usb-ethernet"
    assert by["wlan0"].kind == "wifi" and by["wlan0"].can_be_ap
    assert by["br0"].kind == "virtual"
    assert not by["eth0"].can_be_ap


def test_facts(sysfs):
    by = {a.name: a for a in list_adapters(str(sysfs), runner=iw(IW_AP))}
    assert by["eth1"].mac == "aa:bb:cc:dd:ee:02"
    assert by["eth1"].speed_mbit == 100
    assert by["eth0"].state == "up"
    assert by["wlan0"].speed_mbit is None
    assert by["br0"].speed_mbit is None  # -1 means unknown


def test_a_radio_without_ap_mode(sysfs):
    by = {a.name: a for a in list_adapters(str(sysfs), runner=iw(IW_NO_AP))}
    assert not by["wlan0"].can_be_ap


def test_iw_missing_means_no_ap(sysfs):
    def fail(argv, check=True):
        raise FileNotFoundError("iw")
    by = {a.name: a for a in list_adapters(str(sysfs), runner=fail)}
    assert not by["wlan0"].can_be_ap


def test_roles_from_a_configuration(sysfs):
    from wanpire.config import config_from_dict
    adapters = list_adapters(str(sysfs), runner=iw(IW_AP))
    cfg = config_from_dict({"schema": "wanpire-config/1", "mode": "bridge",
                            "adapters": {"control": "wlan0", "inbound": "eth0",
                                         "outbound": ["eth1"]}},
                           {a.name: a for a in adapters})
    roles = {a.name: cfg.role(a.name) for a in adapters}
    assert roles == {"eth0": "inbound", "eth1": "outbound", "wlan0": "control", "br0": None}
