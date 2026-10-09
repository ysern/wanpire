import json

import pytest

from wanpire.engine import CommandFailed, Engine, RefusedAdapter, ifb_name
from wanpire.model import Direction, Link

NETEM_STATS = [
    {
        "kind": "netem", "handle": "803d:", "root": True, "refcnt": 5,
        "options": {"limit": 2000, "delay": {"delay": 0.005, "jitter": 0, "correlation": 0},
                    "loss-random": {"loss": 0.05, "correlation": 0}, "ecn": False, "gap": 0},
        "bytes": 3884, "packets": 40, "drops": 2, "overlimits": 0, "requeues": 0,
        "backlog": 0, "qlen": 0,
    }
]
DEFAULT_STATS = [{"kind": "fq_codel", "handle": "0:", "root": True, "bytes": 1, "packets": 1,
                  "drops": 0, "backlog": 0, "qlen": 0}]


class FakeRunner:
    """Records every command; answers from a table of (argv prefix -> output or failure)."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def __call__(self, argv, check=True):
        self.calls.append(list(argv))
        for prefix, out in self.answers.items():
            if tuple(argv[: len(prefix)]) == prefix:
                if isinstance(out, Exception):
                    if check:
                        raise out
                    return ""
                return out
        return ""


def speed(n):
    return {("cat", "/sys/class/net/eth1/speed"): f"{n}\n"}


def engine(answers=None, **kw):
    r = FakeRunner({**speed(1000), **(answers or {})})
    return Engine(runner=r, **kw), r


def test_ifb_names_fit_the_kernel_limit():
    assert ifb_name("eth1") == "ifb-eth1"
    long = ifb_name("enx001122334455")
    assert len(long) <= 15 and long.startswith("wp")
    assert long == ifb_name("enx001122334455")


def test_apply_clears_first_then_adds_down_on_egress():
    e, r = engine()
    e.apply("eth1", Link(down=Direction(delay_ms=50)))
    first_add = next(i for i, c in enumerate(r.calls) if c[:3] == ["tc", "qdisc", "add"])
    deletes = [c for c in r.calls[:first_add] if "del" in c]
    assert ["tc", "qdisc", "del", "dev", "eth1", "root"] in deletes
    assert ["tc", "qdisc", "add", "dev", "eth1", "root", "netem", "delay", "50ms",
            "limit", "6250"] in r.calls


def test_apply_up_goes_through_an_ifb_on_the_same_adapter():
    e, r = engine()
    e.apply("eth1", Link(up=Direction(loss_pct=2)))
    assert ["ip", "link", "add", "ifb-eth1", "type", "ifb"] in r.calls
    assert ["ip", "link", "set", "ifb-eth1", "up"] in r.calls
    assert ["tc", "qdisc", "add", "dev", "ifb-eth1", "root", "netem", "loss", "random", "2%",
            "limit", "1000"] in r.calls
    assert ["tc", "qdisc", "add", "dev", "eth1", "handle", "ffff:", "ingress"] in r.calls
    assert ["tc", "filter", "add", "dev", "eth1", "parent", "ffff:", "protocol", "all",
            "prio", "1", "matchall", "action", "mirred", "egress", "redirect",
            "dev", "ifb-eth1"] in r.calls
    # nothing added on the egress, since down is clear
    assert not any(c[:6] == ["tc", "qdisc", "add", "dev", "eth1", "root"] for c in r.calls)


def test_apply_touches_no_other_adapter():
    e, r = engine()
    e.apply("eth1", Link(down=Direction(delay_ms=5), up=Direction(delay_ms=5)))
    devs = {c[c.index("dev") + 1] for c in r.calls if "dev" in c}
    links = {c[3] for c in r.calls if c[:3] in (["ip", "link", "add"], ["ip", "link", "set"],
                                                ["ip", "link", "del"])}
    assert devs | links <= {"eth1", "ifb-eth1"}


def test_the_queue_uses_the_adapter_line_rate():
    e, r = engine({**speed(100)})
    e.apply("eth1", Link(down=Direction(delay_ms=150)))
    add = next(c for c in r.calls if c[:3] == ["tc", "qdisc", "add"])
    assert add[add.index("limit") + 1] == "1875"


def test_an_unknown_line_rate_counts_as_a_gigabit():
    e, r = engine({("cat", "/sys/class/net/eth1/speed"): "-1\n"})
    e.apply("eth1", Link(down=Direction(delay_ms=150)))
    add = next(c for c in r.calls if c[:3] == ["tc", "qdisc", "add"])
    assert add[add.index("limit") + 1] == "18750"


def test_clear_removes_everything_and_tolerates_nothing_to_clear():
    gone = CommandFailed(["tc"], 2, "Cannot delete qdisc with handle of zero.")
    e, r = engine({("tc", "qdisc", "del"): gone, ("ip", "link", "del"): gone,
                   ("tc", "filter", "del"): gone})
    e.clear("eth1")
    assert ["tc", "qdisc", "del", "dev", "eth1", "root"] in r.calls
    assert ["tc", "qdisc", "del", "dev", "eth1", "ingress"] in r.calls
    assert ["ip", "link", "del", "ifb-eth1"] in r.calls


def test_a_real_failure_while_adding_is_raised_and_the_adapter_cleared():
    bad = CommandFailed(["tc"], 2, "Error: Specified qdisc kind is unknown.")
    e, r = engine({("tc", "qdisc", "add"): bad})
    with pytest.raises(CommandFailed, match="unknown"):
        e.apply("eth1", Link(down=Direction(delay_ms=5)))
    last = r.calls[-1]
    assert last[:2] in (["tc", "qdisc"], ["ip", "link"]) and "del" in last


def test_the_control_adapter_is_refused_and_untouched():
    e, r = engine(control_adapters={"wlan0"})
    with pytest.raises(RefusedAdapter, match="wlan0.*control"):
        e.apply("wlan0", Link(down=Direction(delay_ms=5)))
    with pytest.raises(RefusedAdapter):
        e.clear("wlan0")
    assert r.calls == []


def test_read_reports_each_direction_with_netem_drops():
    e, r = engine({
        ("tc", "-s", "-j", "qdisc", "show", "dev", "eth1"): json.dumps(NETEM_STATS),
        ("tc", "-s", "-j", "qdisc", "show", "dev", "ifb-eth1"): CommandFailed(["tc"], 1, "Cannot find device"),
    })
    state = e.read("eth1")
    assert state["down"] == {"applied": True, "packets": 40, "bytes": 3884, "dropped": 2,
                             "queued": 0, "limit": 2000}
    assert state["up"] == {"applied": False}


def test_read_a_default_qdisc_is_not_applied():
    e, r = engine({
        ("tc", "-s", "-j", "qdisc", "show", "dev", "eth1"): json.dumps(DEFAULT_STATS),
        ("tc", "-s", "-j", "qdisc", "show", "dev", "ifb-eth1"): CommandFailed(["tc"], 1, "x"),
    })
    assert e.read("eth1")["down"] == {"applied": False}
