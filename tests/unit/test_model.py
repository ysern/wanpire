import pytest

from wanpire.model import Direction, InvalidLink, Link


def test_an_empty_direction_is_no_impairment():
    d = Direction()
    assert d.is_clear()


def test_a_direction_with_any_setting_is_not_clear():
    assert not Direction(delay_ms=1).is_clear()
    assert not Direction(loss_pct=0.1).is_clear()


def test_two_directions_are_independent():
    link = Link(down=Direction(delay_ms=150), up=Direction(delay_ms=20))
    assert link.down.delay_ms == 150
    assert link.up.delay_ms == 20


def test_a_link_defaults_to_clear_both_ways():
    link = Link()
    assert link.down.is_clear() and link.up.is_clear()


@pytest.mark.parametrize(
    "kwargs, names",
    [
        ({"delay_ms": -1}, ["delay_ms", "0", "10000"]),
        ({"delay_ms": 10001}, ["delay_ms", "0", "10000"]),
        ({"delay_ms": 10, "jitter_ms": -1}, ["jitter_ms"]),
        ({"loss_pct": 120}, ["loss_pct", "0", "100"]),
        ({"duplicate_pct": -0.1}, ["duplicate_pct", "0", "100"]),
        ({"delay_ms": 10, "reorder_pct": 101}, ["reorder_pct", "0", "100"]),
        ({"rate_mbit": 0}, ["rate_mbit", "positive"]),
        ({"burst_loss_pct": 3, "burst_length": 0.5}, ["burst_length", "1"]),
        ({"delay_ms": 5, "jitter_ms": 6}, ["jitter_ms", "delay_ms"]),
        ({"delay_ms": 5, "jitter_ms": 1, "distribution": "gaussian"}, ["distribution", "normal"]),
    ],
)
def test_invalid_figures_are_refused_with_a_reason(kwargs, names):
    with pytest.raises(InvalidLink) as e:
        Direction(**kwargs)
    for n in names:
        assert n in str(e.value)


def test_only_one_loss_model_at_once():
    with pytest.raises(InvalidLink, match="only one loss model"):
        Direction(loss_pct=1, burst_loss_pct=3, burst_length=3)


def test_burst_loss_needs_a_burst_length():
    with pytest.raises(InvalidLink, match="burst_length"):
        Direction(burst_loss_pct=3)


def test_reordering_needs_a_delay():
    with pytest.raises(InvalidLink, match="reorder_pct.*delay_ms"):
        Direction(reorder_pct=5)


def test_a_link_round_trips_through_a_dict():
    link = Link(down=Direction(delay_ms=50, jitter_ms=5), up=Direction(loss_pct=1))
    assert Link.from_dict(link.to_dict()) == link


def test_unknown_settings_are_refused():
    with pytest.raises(InvalidLink, match="latency"):
        Link.from_dict({"down": {"latency": 5}})
