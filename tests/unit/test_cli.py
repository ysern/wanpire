import json

import pytest

from wanpire import cli
from wanpire.model import Direction, Link


class FakeEngine:
    def __init__(self):
        self.calls = []

    def apply(self, adapter, link, lifetime_s=120):
        self.calls.append(("apply", adapter, link, lifetime_s))

    def clear(self, adapter):
        self.calls.append(("clear", adapter))

    def renew(self, adapter, lifetime_s=120):
        self.calls.append(("renew", adapter, lifetime_s))

    def read(self, adapter):
        self.calls.append(("read", adapter))
        return {"down": {"applied": False}, "up": {"applied": False}}


@pytest.fixture
def fake(monkeypatch):
    f = FakeEngine()
    made = {}

    def make(netns=None, control=()):
        made.update(netns=netns, control=set(control))
        return f

    monkeypatch.setattr(cli, "make_engine", make)
    f.made = made
    return f


def test_apply_with_settings_per_direction(fake):
    assert cli.main(["apply", "--adapter", "eth1", "--down", "delay_ms=50,jitter_ms=5",
                     "--up", "loss_pct=1"]) == 0
    assert fake.calls == [("apply", "eth1",
                           Link(down=Direction(delay_ms=50, jitter_ms=5),
                                up=Direction(loss_pct=1)), 120)]


def test_apply_from_a_json_file(fake, tmp_path):
    p = tmp_path / "link.json"
    p.write_text(json.dumps({"down": {"delay_ms": 150}, "up": {"delay_ms": 150}}))
    cli.main(["apply", "--adapter", "eth1", "--file", str(p), "--lifetime", "30"])
    assert fake.calls[0][2] == Link(down=Direction(delay_ms=150), up=Direction(delay_ms=150))
    assert fake.calls[0][3] == 30


def test_lifetime_zero_means_no_dead_man(fake):
    cli.main(["apply", "--adapter", "eth1", "--down", "delay_ms=5", "--lifetime", "0"])
    assert fake.calls[0][3] is None


def test_distribution_is_text(fake):
    cli.main(["apply", "--adapter", "eth1", "--down", "delay_ms=50,jitter_ms=5,distribution=pareto"])
    assert fake.calls[0][2].down.distribution == "pareto"


def test_an_invalid_link_is_an_error_with_the_reason(fake, capsys):
    assert cli.main(["apply", "--adapter", "eth1", "--down", "loss_pct=120"]) == 2
    assert "loss_pct" in capsys.readouterr().err
    assert fake.calls == []


def test_clear_renew_show(fake, capsys):
    cli.main(["clear", "--adapter", "eth1"])
    cli.main(["renew", "--adapter", "eth1", "--lifetime", "60"])
    cli.main(["show", "--adapter", "eth1"])
    assert fake.calls == [("clear", "eth1"), ("renew", "eth1", 60), ("read", "eth1")]
    assert json.loads(capsys.readouterr().out)["down"] == {"applied": False}


def test_netns_and_control_reach_the_engine(fake):
    cli.main(["clear", "--adapter", "o1", "--netns", "wp-box", "--control", "wlan0"])
    assert fake.made == {"netns": "wp-box", "control": {"wlan0"}}


# -- two ends -----------------------------------------------------------------------------

def test_preview_needs_no_engine(monkeypatch, capsys):
    monkeypatch.setattr(cli, "make_engine", lambda **k: pytest.fail("preview made an engine"))
    assert cli.main(["preview", "london:consumer-fibre", "los-angeles:mobile-4g"]) == 0
    out = capsys.readouterr().out
    assert "down" in out and "up" in out and "table" in out


def test_preview_json_is_the_link_and_its_account(capsys):
    assert cli.main(["preview", "--json", "london", "new-york"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert set(doc) == {"link", "account"}
    assert doc["account"]["path"]["origin"] == "table"


def test_apply_from_two_ends_applies_what_preview_shows(fake, capsys):
    from wanpire import catalogue
    assert cli.main(["apply", "--adapter", "eth1", "london", "new-york"]) == 0
    link, _ = catalogue.preview("london", "new-york")
    assert fake.calls == [("apply", "eth1", link, 120)]


def test_ends_and_raw_figures_exclude_each_other(fake, capsys):
    assert cli.main(["apply", "--adapter", "eth1", "london", "tokyo", "--down", "delay_ms=5"]) == 2
    assert "either" in capsys.readouterr().err
    assert fake.calls == []


def test_one_end_alone_is_refused(fake, capsys):
    assert cli.main(["apply", "--adapter", "eth1", "london"]) == 2
    assert "two ends" in capsys.readouterr().err


def test_an_unknown_end_is_an_error(capsys):
    assert cli.main(["preview", "atlantis", "london"]) == 2
    assert "atlantis" in capsys.readouterr().err


def test_endpoints_lists_the_shipped_ones_and_their_channels(capsys):
    assert cli.main(["endpoints"]) == 0
    out = capsys.readouterr().out
    assert "london" in out and "mobile-4g" in out
