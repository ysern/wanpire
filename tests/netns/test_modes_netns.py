"""The line-modes scenarios, with real packets in namespaces. Root, Linux.

    wp-dut (d0) --veth-- (o1) [wp-box] (i1) --veth-- (n0) wp-net
                          outbound      inbound
"""

import contextlib
import json
import subprocess
import sys

import pytest

from wanpire.config import config_from_dict

from .conftest import ns, sh

pytestmark = pytest.mark.netns

DUT, NET, BOX = "wp-dut", "wp-net", "wp-box"


def _down():
    for n in (DUT, NET, BOX):
        pids = sh("ip", "netns", "pids", n, check=False).split()
        if pids:
            sh("kill", *pids, check=False)
        sh("ip", "netns", "del", n, check=False)


@contextlib.contextmanager
def bed():
    _down()
    try:
        for n in (DUT, NET, BOX):
            sh("ip", "netns", "add", n)
        sh("ip", "link", "add", "d0", "netns", DUT, "type", "veth", "peer", "name", "o1",
           "netns", BOX)
        sh("ip", "link", "add", "n0", "netns", NET, "type", "veth", "peer", "name", "i1",
           "netns", BOX)
        for n, dev in ((DUT, "d0"), (NET, "n0"), (BOX, "o1"), (BOX, "i1")):
            ns(n, "ip", "link", "set", dev, "up")
            ns(n, "ip", "link", "set", "lo", "up")
        yield
    finally:
        _down()


def config(mode):
    return config_from_dict({"schema": "wanpire-config/1", "mode": mode,
                             "adapters": {"control": "lo", "inbound": "i1",
                                          "outbound": ["o1"]}})


@pytest.fixture
def modes(tmp_path):
    from wanpire.modes import Modes
    with bed():
        yield Modes(netns=BOX, state_dir=str(tmp_path))


def reaches(src, dst):
    out = ns(src, "ping", "-c", "2", "-i", "0.2", "-W", "1", dst, check=False)
    return " 0% packet loss" in out


def addresses(netns, dev):
    out = json.loads(ns(netns, "ip", "-j", "addr", "show", "dev", dev))
    return [a["local"] for a in out[0]["addr_info"] if a.get("scope") == "global"]


def dnsmasq_in_box():
    box = set(sh("ip", "netns", "pids", BOX).split())
    return box & set(sh("sh", "-c", "pgrep -x dnsmasq || true").split())


# -- bridge -------------------------------------------------------------------------------

def bridge_hosts():
    ns(DUT, "ip", "addr", "add", "10.98.0.1/24", "dev", "d0")
    ns(NET, "ip", "addr", "add", "10.98.0.2/24", "dev", "n0")


def test_bridge_a_device_reaches_the_other_side(modes):
    bridge_hosts()
    assert not reaches(DUT, "10.98.0.2")
    modes.up(config("bridge"))
    assert reaches(DUT, "10.98.0.2")
    for dev in ("o1", "i1", "wpbr0"):
        assert addresses(BOX, dev) == []
    link = json.loads(ns(BOX, "ip", "-j", "-d", "link", "show", "wpbr0"))[0]
    assert link["linkinfo"]["info_data"]["stp_state"] == 0


def test_bridge_a_port_with_an_address_is_refused_and_kept(modes):
    from wanpire.modes import ModeRefused
    bridge_hosts()
    ns(BOX, "ip", "addr", "add", "10.98.0.9/24", "dev", "i1")
    with pytest.raises(ModeRefused, match=r"i1.*10\.98\.0\.9"):
        modes.up(config("bridge"))
    assert addresses(BOX, "i1") == ["10.98.0.9"]
    assert "wpbr0" not in ns(BOX, "ip", "link", "show")


def test_bridge_torn_down(modes):
    bridge_hosts()
    modes.up(config("bridge"))
    modes.down(config("bridge"))
    assert "wpbr0" not in ns(BOX, "ip", "link", "show")
    assert not reaches(DUT, "10.98.0.2")


# -- router -------------------------------------------------------------------------------

UDHCPC_SCRIPT = """#!/bin/sh
case "$1" in
  bound|renew)
    ip addr flush dev "$interface"
    ip addr add "$ip/${mask:-24}" dev "$interface"
    [ -n "$router" ] && ip route replace default via "${router%% *}" dev "$interface"
    ;;
esac
"""

UDP_RX = ("import socket,sys;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
          "s.bind(('0.0.0.0',7100));s.settimeout(10);d,a=s.recvfrom(64);print(a[0])")
UDP_TX = ("import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
          "s.sendto(b'hi',('10.98.1.2',7100))")


def router_hosts():
    ns(NET, "ip", "addr", "add", "10.98.1.2/24", "dev", "n0")
    ns(BOX, "ip", "addr", "add", "10.98.1.1/24", "dev", "i1")


def dhcp(tmp_path):
    script = tmp_path / "udhcpc.sh"
    script.write_text(UDHCPC_SCRIPT)
    script.chmod(0o755)
    ns(DUT, "busybox", "udhcpc", "-i", "d0", "-n", "-q", "-t", "5", "-T", "1",
       "-s", str(script))
    return addresses(DUT, "d0")


def test_router_dhcp_and_nat(modes, tmp_path):
    router_hosts()
    modes.up(config("router"))
    got = dhcp(tmp_path)
    assert len(got) == 1 and got[0].startswith("10.77.0.")
    assert reaches(DUT, "10.98.1.2")
    rx = subprocess.Popen(["ip", "netns", "exec", NET, sys.executable, "-c", UDP_RX],
                          stdout=subprocess.PIPE, text=True)
    import time
    time.sleep(0.5)
    ns(DUT, sys.executable, "-c", UDP_TX)
    source, _ = rx.communicate(timeout=15)
    assert source.strip() == "10.98.1.1"  # the box's inbound address, not the device's


def test_router_torn_down_restores_forwarding(modes, tmp_path):
    router_hosts()
    assert ns(BOX, "sysctl", "-n", "net.ipv4.ip_forward").strip() == "0"
    modes.up(config("router"))
    assert ns(BOX, "sysctl", "-n", "net.ipv4.ip_forward").strip() == "1"
    modes.down(config("router"))
    assert ns(BOX, "sysctl", "-n", "net.ipv4.ip_forward").strip() == "0"
    assert addresses(BOX, "o1") == []
    assert "wanpire" not in ns(BOX, "nft", "list", "tables")
    assert not dnsmasq_in_box()


@pytest.mark.parametrize("mode", ["bridge", "router"])
def test_twice(modes, mode, tmp_path):
    (bridge_hosts if mode == "bridge" else router_hosts)()
    cfg = config(mode)
    modes.up(cfg)
    modes.up(cfg)
    modes.down(cfg)
    modes.down(cfg)
    assert "wpbr0" not in ns(BOX, "ip", "link", "show")
    assert addresses(BOX, "o1") == []
    assert ns(BOX, "sysctl", "-n", "net.ipv4.ip_forward").strip() == "0"
    assert not dnsmasq_in_box()
