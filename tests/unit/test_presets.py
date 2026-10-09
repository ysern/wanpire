"""Endpoint presets, the path between two ends, and combining them into a link. No I/O."""

import copy
import math

import pytest

from wanpire.model import Direction
from wanpire.presets import (
    KINDS,
    Formula,
    InvalidPreset,
    PathTable,
    combine,
    endpoint_from_dict,
    great_circle_km,
    path_between,
)

GENERIC = {
    "kind": "generic",
    "description": "A typical connection",
    "down": {"delay_ms": 5, "jitter_ms": 1, "loss_pct": 0.1, "rate_mbit": 50},
    "up": {"delay_ms": 5, "jitter_ms": 1, "loss_pct": 0.1, "rate_mbit": 10},
    "sources": [{"name": "test", "licence": "MIT"}],
}


def preset(**over):
    data = {
        "schema": "wanpire-endpoint/1",
        "id": "here",
        "name": "Here",
        "location": {"lat": 51.5, "lon": -0.13, "country": "GB", "region": "europe"},
        "default_channel": "generic",
        "channels": {"generic": copy.deepcopy(GENERIC)},
    }
    data.update(over)
    return data


def at(id_, lat, lon, region, **over):
    return endpoint_from_dict(preset(
        id=id_, name=id_, location={"lat": lat, "lon": lon, "country": "XX", "region": region},
        **over))


# -- endpoint presets ---------------------------------------------------------------------

def test_a_valid_preset_loads_with_its_default_channel():
    e = endpoint_from_dict(preset())
    assert e.id == "here"
    assert e.channel(None).kind == "generic"
    assert e.channel(None).down == Direction(delay_ms=5, jitter_ms=1, loss_pct=0.1, rate_mbit=50)


def test_a_preset_with_no_channel_is_refused():
    with pytest.raises(InvalidPreset, match="at least one channel"):
        endpoint_from_dict(preset(channels={}))


def test_figures_outside_the_models_ranges_name_preset_channel_and_setting():
    data = preset()
    data["channels"]["generic"]["down"]["loss_pct"] = 120
    with pytest.raises(InvalidPreset, match=r"here.*generic.*loss_pct"):
        endpoint_from_dict(data)


def test_an_unknown_kind_is_refused_with_the_known_ones():
    data = preset()
    data["channels"]["x"] = dict(copy.deepcopy(GENERIC), kind="carrier-x")
    with pytest.raises(InvalidPreset, match="mobile-4g"):
        endpoint_from_dict(data)


def test_a_preset_without_a_generic_channel_is_refused():
    data = preset(default_channel="m")
    data["channels"] = {"m": dict(copy.deepcopy(GENERIC), kind="mobile-4g")}
    with pytest.raises(InvalidPreset, match="generic"):
        endpoint_from_dict(data)


def test_a_channel_needs_a_source():
    data = preset()
    data["channels"]["generic"]["sources"] = []
    with pytest.raises(InvalidPreset, match="source"):
        endpoint_from_dict(data)


def test_a_channel_carries_only_access_settings():
    data = preset()
    data["channels"]["generic"]["down"]["reorder_pct"] = 5
    with pytest.raises(InvalidPreset, match="reorder_pct"):
        endpoint_from_dict(data)


def test_the_default_channel_must_exist():
    with pytest.raises(InvalidPreset, match="default_channel"):
        endpoint_from_dict(preset(default_channel="nope"))


def test_an_unknown_channel_lists_the_known_ones():
    e = endpoint_from_dict(preset())
    with pytest.raises(InvalidPreset, match="generic"):
        e.channel("carrier-pigeon")


def test_the_schema_tag_is_checked():
    with pytest.raises(InvalidPreset, match="wanpire-endpoint/1"):
        endpoint_from_dict(preset(schema="something/2"))


def test_kinds_are_the_designs_list():
    assert KINDS == ("generic", "media-private-network", "enterprise-fibre", "business-fibre",
                     "consumer-fibre", "cable", "dsl", "fixed-wireless", "mobile-4g",
                     "mobile-5g", "satellite-leo", "satellite-geo")


# -- the formula --------------------------------------------------------------------------

def test_great_circle_london_to_san_francisco():
    assert great_circle_km(51.51, -0.13, 37.78, -122.42) == pytest.approx(8620, abs=30)


def test_the_formula_uses_the_region_pairs_factor_and_the_router_term():
    f = Formula(router_ms=5, global_factor=1.5, factors={("europe", "north-america"): 2.0})
    rtt, how = f.rtt(0, 0, "north-america", 0, 9, "europe")  # 9 degrees on the equator
    km = great_circle_km(0, 0, 0, 9)
    assert rtt == pytest.approx(2 * km * 2.0 / 200 + 5)
    assert "europe/north-america" in how


def test_an_unfitted_region_pair_uses_the_global_factor_and_says_so():
    f = Formula(router_ms=5, global_factor=1.5, factors={})
    rtt, how = f.rtt(0, 0, "africa", 0, 9, "oceania")
    assert rtt == pytest.approx(2 * great_circle_km(0, 0, 0, 9) * 1.5 / 200 + 5)
    assert "global" in how


# -- the path -----------------------------------------------------------------------------

TABLE = PathTable(
    sites={
        "lon": {"lat": 51.51, "lon": -0.13, "region": "europe", "metro": "London"},
        "tyo": {"lat": 35.68, "lon": 139.77, "region": "east-asia", "metro": "Tokyo"},
    },
    rtt={"lon": {"tyo": 230}, "tyo": {"lon": 234}},
    source={"name": "test", "licence": "CC-BY-4.0"},
)
FORMULA = Formula(router_ms=6, global_factor=1.6, factors={})


def test_a_measured_path_in_the_preset_wins():
    near = at("here", 51.5, -0.1, "europe", paths={"tokyo": {"rtt_ms": 100, "source": "test"}})
    far = at("tokyo", 35.7, 139.7, "east-asia")
    p = path_between(near, far, TABLE, FORMULA)
    assert (p.rtt_ms, p.origin) == (100, "preset")


def test_the_far_ends_measured_path_counts_too():
    near = at("here", 51.5, -0.1, "europe")
    far = at("tokyo", 35.7, 139.7, "east-asia", paths={"here": {"rtt_ms": 101, "source": "t"}})
    assert path_between(near, far, TABLE, FORMULA).rtt_ms == 101


def test_two_ends_near_table_sites_take_the_tables_mean():
    near = at("london", 51.5, -0.12, "europe")
    far = at("tokyo", 35.69, 139.69, "east-asia")
    p = path_between(near, far, TABLE, FORMULA)
    assert p.origin == "table"
    assert p.rtt_ms == pytest.approx(232, abs=5)


def test_an_anchored_end_is_corrected_by_the_formulas_difference():
    near = at("bristol", 51.45, -2.59, "europe")  # ~170 km west of the London site
    far = at("tokyo", 35.68, 139.77, "east-asia")
    p = path_between(near, far, TABLE, FORMULA)
    want = 232 + (FORMULA.rtt(51.45, -2.59, "europe", 35.68, 139.77, "east-asia")[0]
                  - FORMULA.rtt(51.51, -0.13, "europe", 35.68, 139.77, "east-asia")[0])
    assert p.rtt_ms == pytest.approx(want)


def test_an_end_far_from_every_site_uses_the_formula():
    near = at("pacific", 0, -150, "oceania")
    far = at("london", 51.5, -0.12, "europe")
    p = path_between(near, far, TABLE, FORMULA)
    assert p.origin == "formula"
    assert p.rtt_ms == pytest.approx(FORMULA.rtt(0, -150, "oceania", 51.5, -0.12, "europe")[0])


def test_two_ends_at_one_site_use_the_formula():
    near = at("a", 51.5, -0.1, "europe")
    far = at("b", 51.52, -0.14, "europe")
    assert path_between(near, far, TABLE, FORMULA).origin == "formula"


# -- combining ----------------------------------------------------------------------------

def ch(kind="generic", down=None, up=None):
    data = preset()
    data["channels"]["generic"].update(kind=kind, down=down, up=up)
    return endpoint_from_dict(data).channel(None)


def test_london_consumer_fibre_to_los_angeles_4g():
    near = ch(down={"delay_ms": 5, "jitter_ms": 3, "loss_pct": 0.1, "rate_mbit": 500},
              up={"delay_ms": 5, "jitter_ms": 3, "loss_pct": 0.1, "rate_mbit": 100})
    far = ch(down={"delay_ms": 25, "jitter_ms": 4, "loss_pct": 1, "rate_mbit": 50},
             up={"delay_ms": 25, "jitter_ms": 4, "loss_pct": 1, "rate_mbit": 10})
    link = combine(near, far, 140)
    assert link.down == Direction(delay_ms=100, jitter_ms=5, loss_pct=1.099, rate_mbit=10)
    assert link.up == Direction(delay_ms=100, jitter_ms=5, loss_pct=1.099, rate_mbit=50)


def test_burst_loss_is_kept_with_the_longer_burst():
    near = ch(down={"loss_pct": 1}, up={"loss_pct": 1})
    far = ch(down={"burst_loss_pct": 2, "burst_length": 4},
             up={"burst_loss_pct": 2, "burst_length": 4})
    link = combine(near, far, 0)
    assert link.down.loss_pct == 0
    assert (link.down.burst_loss_pct, link.down.burst_length) == (pytest.approx(2.98), 4)


def test_no_rate_on_either_side_is_no_limit():
    link = combine(ch(down={}, up={}), ch(down={}, up={}), 50)
    assert link.down.rate_mbit is None
    assert link.down.delay_ms == 25


def test_asymmetric_channels_cross_over():
    near = ch(down={"delay_ms": 1}, up={"delay_ms": 2})
    far = ch(down={"delay_ms": 10}, up={"delay_ms": 20})
    link = combine(near, far, 0)
    assert link.down.delay_ms == 21  # far sends (up 20) to near (down 1)
    assert link.up.delay_ms == 12  # near sends (up 2) to far (down 10)


def test_jitters_add_in_quadrature():
    link = combine(ch(down={"delay_ms": 10, "jitter_ms": 6}, up={}),
                   ch(down={}, up={"delay_ms": 10, "jitter_ms": 8}), 0)
    assert link.down.jitter_ms == pytest.approx(10)
    assert math.isclose(link.up.jitter_ms, 0)
