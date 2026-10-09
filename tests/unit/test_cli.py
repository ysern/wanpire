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


# -- adapters and modes -------------------------------------------------------------------

from wanpire.adapters import Adapter  # noqa: E402

ADAPTERS = [Adapter("eth0", "ethernet", "aa:bb:cc:dd:ee:01", "up", 1000, False),
            Adapter("eth1", "usb-ethernet", "aa:bb:cc:dd:ee:02", "up", 1000, False),
            Adapter("wlan0", "wifi", "aa:bb:cc:dd:ee:03", "up", None, True)]


@pytest.fixture
def box(monkeypatch, tmp_path):
    cfg = tmp_path / "wanpire.json"
    cfg.write_text(json.dumps({"schema": "wanpire-config/1", "mode": "bridge",
                               "adapters": {"control": "wlan0", "inbound": "eth0",
                                            "outbound": ["eth1"]}}))
    calls = []

    class FakeModes:
        def up(self, c):
            calls.append(("up", c.mode))

        def down(self, c):
            calls.append(("down", c.mode))

    monkeypatch.setattr(cli, "list_adapters", lambda: ADAPTERS)
    monkeypatch.setattr(cli, "make_modes", lambda: FakeModes())
    return str(cfg), calls


def test_adapters_lists_roles(box, capsys):
    path, _ = box
    assert cli.main(["adapters", "--config", path, "--json"]) == 0
    rows = {a["name"]: a for a in json.loads(capsys.readouterr().out)}
    assert rows["eth1"]["role"] == "outbound" and rows["eth1"]["kind"] == "usb-ethernet"
    assert rows["wlan0"]["can_be_ap"] is True


def test_adapters_without_a_configuration(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "list_adapters", lambda: ADAPTERS)
    assert cli.main(["adapters", "--config", str(tmp_path / "none.json")]) == 0
    assert "eth0" in capsys.readouterr().out


def test_up_and_down(box):
    path, calls = box
    assert cli.main(["up", "--config", path]) == 0
    assert cli.main(["down", "--config", path]) == 0
    assert calls == [("up", "bridge"), ("down", "bridge")]


def test_up_refuses_an_invalid_mapping(box, capsys, tmp_path):
    _, calls = box
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "wanpire-config/1", "mode": "bridge",
                               "adapters": {"control": "wlan0", "inbound": "eth0",
                                            "outbound": ["eth0"]}}))
    assert cli.main(["up", "--config", str(bad)]) == 2
    assert "outbound shares its adapter with nothing" in capsys.readouterr().err
    assert calls == []
