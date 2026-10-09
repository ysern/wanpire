"""The link-engine and link-model scenarios that need real packets. Root, Linux."""

import json
import statistics

import pytest

from wanpire.model import Direction, Link

from .conftest import BOX, DUT, DUT_IP, NET, NET_IP, OUTBOUND, ns, ping, probe

pytestmark = pytest.mark.netns


def qdiscs(dev):
    return [{k: q.get(k) for k in ("kind", "root")}
            for q in json.loads(ns(BOX, "tc", "-j", "qdisc", "show", "dev", dev) or "[]")]


def links():
    return {l["ifname"] for l in json.loads(ns(BOX, "ip", "-j", "link", "show"))}


def test_delay_each_way(bed):
    base, _, _ = ping(DUT, NET_IP)
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=50), up=Direction(delay_ms=50)))
    avg, _, loss = ping(DUT, NET_IP)
    assert loss == 0
    assert avg - base == pytest.approx(100, abs=1)


def test_other_adapters_untouched(bed):
    before = qdiscs("n1")
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=5), up=Direction(delay_ms=5)))
    assert qdiscs("n1") == before
    bed.clear(OUTBOUND)
    assert qdiscs("n1") == before


def test_reordering_does_not_linger(bed):
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=20, reorder_pct=25)))
    bed.apply(OUTBOUND, Link(down=Direction(loss_pct=2)))
    r = probe(NET, DUT, DUT_IP)
    assert r["out_of_order"] == 0
    assert 1.0 <= r["loss_pct"] <= 3.0


def test_clear_after_apply(bed):
    before_q, before_l = qdiscs(OUTBOUND), links()
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=5), up=Direction(loss_pct=1)))
    assert qdiscs(OUTBOUND) != before_q
    bed.clear(OUTBOUND)
    assert qdiscs(OUTBOUND) == before_q
    assert links() == before_l


def test_clear_twice(bed):
    bed.clear(OUTBOUND)
    bed.clear(OUTBOUND)


def test_counting_the_engines_own_drops(bed):
    bed.apply(OUTBOUND, Link(down=Direction(loss_pct=5)))
    probe(NET, DUT, DUT_IP)
    down = bed.read(OUTBOUND)["down"]
    assert down["applied"]
    assert 400 <= down["dropped"] <= 600


def test_jitter_alone_does_not_reorder(bed):
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=50, jitter_ms=10)))
    r = probe(NET, DUT, DUT_IP)
    assert r["out_of_order"] == 0
    # the spread, one way only, from a slow ping so that keeping order rarely binds
    _, mdev, _ = ping(DUT, NET_IP, count=300, interval=0.05)
    assert mdev == pytest.approx(10, rel=0.2)


def test_reordering_when_asked(bed):
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=20, reorder_pct=25)))
    assert probe(NET, DUT, DUT_IP)["out_of_order"] > 0


def test_three_per_cent_in_bursts_of_three(bed):
    bed.apply(OUTBOUND, Link(down=Direction(burst_loss_pct=3, burst_length=3)))
    r = probe(NET, DUT, DUT_IP)
    assert 2.0 <= r["loss_pct"] <= 4.0
    assert 2.0 <= r["mean_burst"] <= 4.5


def test_a_long_delay_at_a_high_rate(bed):
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=150, rate_mbit=100)))
    ns(DUT, "iperf3", "-s", "-D", "-1", "-p", "5201")
    import time
    time.sleep(0.5)
    ns(NET, "iperf3", "-c", DUT_IP, "-u", "-b", "95M", "-l", "1400", "-t", "15")
    assert bed.read(OUTBOUND)["down"]["dropped"] == 0


def test_one_tcp_flow_does_not_fill_a_delay_sized_queue(bed):
    """The bandwidth is a bottleneck with a bounded queue (tbf), not netem's delay-sized one."""
    import subprocess
    import time
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=40, rate_mbit=20)))
    ns(DUT, "iperf3", "-s", "-D", "-1", "-p", "5202")
    time.sleep(0.5)
    pinger = subprocess.Popen(["ip", "netns", "exec", DUT, "ping", "-c", "60", "-i", "0.2",
                               NET_IP], stdout=subprocess.PIPE, text=True)
    out = ns(NET, "iperf3", "-c", DUT_IP, "-p", "5202", "-t", "15", "-J")
    pings, _ = pinger.communicate(timeout=30)
    mbit = json.loads(out)["end"]["sum_received"]["bits_per_second"] / 1e6
    rtts = [float(line.split("time=")[1].split()[0]) for line in pings.splitlines()
            if "time=" in line]
    assert mbit >= 0.9 * 20
    assert max(rtts) <= 40 + 50 + 15
    assert bed.read(OUTBOUND)["down"]["dropped"] == 0  # drops above 20 Mbit/s are tbf's


def test_not_renewed(bed):
    import time
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=5)), lifetime_s=5)
    assert bed.read(OUTBOUND)["down"]["applied"]
    time.sleep(7)
    assert not bed.read(OUTBOUND)["down"]["applied"]


def test_renewed(bed):
    import time
    bed.apply(OUTBOUND, Link(down=Direction(delay_ms=5)), lifetime_s=5)
    for _ in range(5):
        time.sleep(2)
        bed.renew(OUTBOUND, lifetime_s=5)
    assert bed.read(OUTBOUND)["down"]["applied"]
    bed.clear(OUTBOUND)
