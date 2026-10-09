"""A three-namespace test bed, as in the design's spike, built for each test.

    wp-dut (10.99.0.1) --veth-- [wp-box: bridge over o1 and n1] --veth-- wp-net (10.99.0.2)
                           o1 is the outbound adapter (towards the device under test)

Needs root and Linux. Touches no real interface. Torn down whatever happens.
"""

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wanpire.engine import Engine

PROBE = str(Path(__file__).with_name("probe.py"))
DUT, NET, BOX = "wp-dut", "wp-net", "wp-box"
DUT_IP, NET_IP = "10.99.0.1", "10.99.0.2"
OUTBOUND = "o1"


def sh(*argv, check=True):
    return subprocess.run(argv, check=check, capture_output=True, text=True).stdout


def ns(name, *argv, check=True):
    return sh("ip", "netns", "exec", name, *argv, check=check)


def pytest_collection_modifyitems(config, items):
    if sys.platform != "linux" or os.geteuid() != 0:
        skip = pytest.mark.skip(reason="namespace tests need root on Linux")
        for item in items:
            item.add_marker(skip)


def _down():
    for n in (DUT, NET, BOX):
        pids = sh("ip", "netns", "pids", n, check=False).split()
        if pids:
            sh("kill", *pids, check=False)
        sh("ip", "netns", "del", n, check=False)


@contextlib.contextmanager
def testbed():
    """Build the bed, yield an Engine for it, tear it down whatever happens."""
    _down()
    try:
        for n in (DUT, NET, BOX):
            sh("ip", "netns", "add", n)
        sh("ip", "link", "add", "d0", "netns", DUT, "type", "veth", "peer", "name", OUTBOUND, "netns", BOX)
        sh("ip", "link", "add", "n0", "netns", NET, "type", "veth", "peer", "name", "n1", "netns", BOX)
        ns(BOX, "ip", "link", "add", "br0", "type", "bridge")
        for i in (OUTBOUND, "n1"):
            ns(BOX, "ip", "link", "set", i, "master", "br0")
        for i in (OUTBOUND, "n1", "br0", "lo"):
            ns(BOX, "ip", "link", "set", i, "up")
        for n, dev, ip in ((DUT, "d0", DUT_IP), (NET, "n0", NET_IP)):
            ns(n, "ip", "addr", "add", f"{ip}/24", "dev", dev)
            ns(n, "ip", "link", "set", dev, "up")
            ns(n, "ip", "link", "set", "lo", "up")
        ns(DUT, "ping", "-c", "3", "-i", "0.2", "-W", "1", NET_IP)
        yield Engine(netns=BOX)
    finally:
        _down()


@pytest.fixture
def bed():
    with testbed() as engine:
        yield engine


def ping(src, dst, count=200, interval=0.01):
    """Round-trip statistics in ms: (avg, mdev, loss_pct)."""
    out = ns(src, "ping", "-q", "-c", str(count), "-i", str(interval), dst, check=False)
    loss = float(out.split("% packet loss")[0].rsplit(" ", 1)[1])
    rtt = out.split("rtt min/avg/max/mdev = ")[1].split()[0].split("/")
    return float(rtt[1]), float(rtt[3]), loss


def probe(src, dst_ns, dst_ip, count=10000, pps=1000, size=200):
    """Send numbered packets from one namespace to another; the receiver's summary."""
    seconds = count / pps + 3
    rx = subprocess.Popen(
        ["ip", "netns", "exec", dst_ns, sys.executable, PROBE, "rx", dst_ip, "7000", str(seconds)],
        stdout=subprocess.PIPE, text=True)
    import time
    time.sleep(0.5)
    ns(src, sys.executable, PROBE, "tx", dst_ip, "7000", str(pps), str(count), str(size))
    out, _ = rx.communicate(timeout=seconds + 10)
    return json.loads(out)
