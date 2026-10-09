import pytest

from wanpire.model import Direction
from wanpire.netem import gilbert_elliott, netem_args, queue_limit, tbf_args


def opts(d, line_rate_mbit=1000):
    return netem_args(d, line_rate_mbit=line_rate_mbit)


def test_no_impairment_is_an_empty_netem():
    assert opts(Direction()) == ["limit", "1000"]


def test_fixed_delay():
    a = opts(Direction(delay_ms=50))
    assert a[:2] == ["delay", "50ms"]


def test_jitter_is_normal_by_default():
    a = opts(Direction(delay_ms=50, jitter_ms=10))
    i = a.index("delay")
    assert a[i : i + 5] == ["delay", "50ms", "10ms", "distribution", "normal"]


def test_jitter_keeps_order_by_setting_a_rate():
    a = opts(Direction(delay_ms=50, jitter_ms=10), line_rate_mbit=1000)
    assert a[a.index("rate") + 1] == "1000mbit"


def test_jitter_with_a_bandwidth_keeps_order_at_the_line_rate():
    # the bandwidth is tbf's job; netem's rate only keeps order
    a = opts(Direction(delay_ms=50, jitter_ms=10, rate_mbit=20), line_rate_mbit=1000)
    assert a[a.index("rate") + 1] == "1000mbit"
    assert a.count("rate") == 1


def test_jitter_with_reordering_asked_sets_no_rate():
    a = opts(Direction(delay_ms=50, jitter_ms=10, reorder_pct=5))
    assert "rate" not in a


def test_other_distributions_pass_through():
    a = opts(Direction(delay_ms=50, jitter_ms=10, distribution="pareto"))
    assert a[a.index("distribution") + 1] == "pareto"


def test_random_loss():
    a = opts(Direction(loss_pct=2))
    assert a[a.index("loss") : a.index("loss") + 3] == ["loss", "random", "2%"]


def test_loss_correlation_is_never_emitted():
    a = opts(Direction(loss_pct=2))
    i = a.index("loss")
    # "loss random 2%" and nothing percent-like after it that is not another keyword
    assert not a[i + 3 :] or not a[i + 3].endswith("%")


def test_gilbert_elliott_from_mean_and_burst_length():
    p, r = gilbert_elliott(loss_pct=3.2258, burst_length=3.3333)
    assert p == pytest.approx(1.0, rel=1e-3)
    assert r == pytest.approx(30.0, rel=1e-3)


def test_burst_loss_uses_gemodel():
    a = opts(Direction(burst_loss_pct=3, burst_length=3))
    i = a.index("loss")
    assert a[i : i + 2] == ["loss", "gemodel"]
    p, r = gilbert_elliott(3, 3)
    assert a[i + 2 : i + 6] == [f"{p:.4f}%", f"{r:.4f}%", "100%", "0%"]


def test_reorder_always_has_a_gap():
    a = opts(Direction(delay_ms=20, reorder_pct=25))
    i = a.index("reorder")
    assert a[i + 1] == "25%"
    assert a[a.index("gap") + 1] == "5"


def test_duplicate():
    a = opts(Direction(duplicate_pct=1))
    assert a[a.index("duplicate") + 1] == "1%"


def test_bandwidth_alone_sets_no_netem_rate():
    assert "rate" not in opts(Direction(rate_mbit=50))


def test_the_bandwidth_is_a_tbf_with_the_default_queue():
    assert tbf_args(Direction(rate_mbit=20)) == ["rate", "20mbit", "burst", "32768",
                                                  "latency", "50ms"]


def test_the_tbf_queue_is_queue_ms():
    assert tbf_args(Direction(rate_mbit=20, queue_ms=120))[-1] == "120ms"


def test_the_tbf_burst_covers_one_timer_tick_at_high_rates():
    # 1,000 Mbit/s at 250 Hz: 500,000 bytes per tick
    assert tbf_args(Direction(rate_mbit=1000))[3] == "500000"


def test_no_bandwidth_no_tbf():
    assert tbf_args(Direction(delay_ms=5)) is None


def test_queue_floor_is_1000():
    assert queue_limit(Direction(delay_ms=1), line_rate_mbit=1000) == 1000


def test_queue_holds_the_delay_at_the_line_rate_with_margin():
    # 150 ms at 100 Mbit/s of 1,500-byte packets: 1,250 packets, x1.5 = 1,875
    assert queue_limit(Direction(delay_ms=150), line_rate_mbit=100) == 1875


def test_queue_ignores_the_bandwidth_which_tbf_enforces():
    assert queue_limit(Direction(delay_ms=150, rate_mbit=20), line_rate_mbit=100) == 1875


def test_queue_counts_three_jitters():
    # (100 + 30) ms at 100 Mbit/s: 1,083.3 packets, x1.5 -> 1,625
    assert queue_limit(Direction(delay_ms=100, jitter_ms=10), 100) == 1625


def test_queue_uses_line_rate_without_bandwidth():
    # 150 ms at 1,000 Mbit/s: 12,500 packets, x1.5 = 18,750
    assert queue_limit(Direction(delay_ms=150), line_rate_mbit=1000) == 18750


def test_queue_is_capped_by_the_memory_budget():
    assert queue_limit(Direction(delay_ms=10000), line_rate_mbit=1000) == 32768


def test_the_limit_is_in_the_options():
    a = opts(Direction(delay_ms=150, rate_mbit=20), line_rate_mbit=100)
    assert a[a.index("limit") + 1] == "1875"
