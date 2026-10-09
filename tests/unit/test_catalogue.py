"""The shipped presets, the path table and the fitted formula, as an installed wanpire finds them."""

import json

import pytest

from wanpire import catalogue
from wanpire.presets import InvalidPreset

jsonschema = pytest.importorskip("jsonschema")

CITIES = {"london", "los-angeles", "new-york", "vancouver", "sydney", "mumbai", "tokyo"}
LICENCES = {"CC0-1.0", "CC-BY-4.0", "MIT"}


def test_the_seven_cities_ship():
    assert CITIES <= set(catalogue.endpoint_ids())


def test_every_shipped_preset_matches_the_published_schema():
    schema = catalogue.endpoint_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    for eid in catalogue.endpoint_ids():
        jsonschema.validate(catalogue.endpoint_document(eid), schema)


def test_every_shipped_preset_loads():
    for eid in catalogue.endpoint_ids():
        assert catalogue.endpoint(eid).id == eid


def test_every_source_is_redistributable_or_our_own():
    for eid in catalogue.endpoint_ids():
        for c in catalogue.endpoint_document(eid)["channels"].values():
            for s in c["sources"]:
                assert s["licence"] in LICENCES, (eid, s)


def test_the_table_names_its_source_and_licence():
    src = catalogue.path_table().source
    assert src["licence"] == "CC-BY-4.0"
    assert src["attribution"] and src["dataset_date"] and src["url"]


def test_the_default_channel_is_generic():
    end, channel = catalogue.resolve("london")
    assert (end.id, channel.kind) == ("london", "generic")


def test_an_end_with_a_channel():
    _, channel = catalogue.resolve("tokyo:mobile-4g")
    assert channel.kind == "mobile-4g"


def test_an_unknown_channel_lists_londons():
    with pytest.raises(InvalidPreset, match="consumer-fibre"):
        catalogue.resolve("london:carrier-pigeon")


def test_an_unknown_endpoint_lists_the_shipped_ones():
    with pytest.raises(InvalidPreset, match="los-angeles"):
        catalogue.resolve("atlantis")


def test_a_preset_from_a_users_file(tmp_path):
    doc = catalogue.endpoint_document("london")
    doc.update(id="my-office", name="My office")
    f = tmp_path / "office.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    end, channel = catalogue.resolve(f"{f}:cable")
    assert (end.id, channel.kind) == ("my-office", "cable")


def test_london_to_tokyo_comes_from_the_table():
    p = catalogue.path("london", "tokyo")
    assert p.origin == "table"
    t = catalogue.path_table()
    assert p.rtt_ms == pytest.approx(t.mean_rtt("uk-south", "jp-east"), abs=5)


def test_the_formula_is_fitted_within_15_percent_median():
    f = catalogue.formula()
    t = catalogue.path_table()
    errors = []
    for a, row in t.rtt.items():
        for b in row:
            if a < b:
                sa, sb = t.sites[a], t.sites[b]
                from wanpire.presets import great_circle_km
                if great_circle_km(sa["lat"], sa["lon"], sb["lat"], sb["lon"]) < 300:
                    continue
                want = t.mean_rtt(a, b)
                got, _ = f.rtt(sa["lat"], sa["lon"], sa["region"],
                               sb["lat"], sb["lon"], sb["region"])
                errors.append(abs(got - want) / want)
    errors.sort()
    assert errors[len(errors) // 2] < 0.15


def test_preview_london_consumer_fibre_to_los_angeles_4g():
    link, account = catalogue.preview("london:consumer-fibre", "los-angeles:mobile-4g")
    assert link.down.delay_ms > 70  # half of a transatlantic-and-continent round trip at least
    assert link.down.rate_mbit == 8  # the 4G end's upload limits what reaches London
    assert account["path"]["origin"] == "table"
    assert account["near"] == {"endpoint": "london", "channel": "consumer-fibre"}
