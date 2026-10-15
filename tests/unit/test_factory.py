"""The reset to the install state: the configuration from the factory copy, the account gone
(reset-the-box-to-its-install-state). No root, no network."""

import json

import pytest

from wanpire.account import Account
from wanpire.config import InvalidConfig, load_config
from wanpire.factory import NoFactoryCopy, reset

FACTORY = {"schema": "wanpire-config/1", "mode": "bridge",
           "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]},
           "wifi": {"country": "GB"}}
CHANGED = {"schema": "wanpire-config/1", "mode": "router",
           "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["wlan1"]},
           "router": {"address": "10.5.0.1/24"},
           "access_points": {"wlan1": {"ssid": "lab-ap", "passphrase": "correct horse"}},
           "wifi": {"country": "GB"}}


@pytest.fixture
def box(tmp_path):
    """A box configured and used since the install: other roles, an access point, an account."""
    (tmp_path / "factory.json").write_text(json.dumps(FACTORY))
    (tmp_path / "wanpire.json").write_text(json.dumps(CHANGED))
    Account(tmp_path / "account").set("admin", "correct horse")
    return tmp_path


def paths(box):
    return str(box / "wanpire.json"), str(box / "account"), str(box / "factory.json")


def test_reset_restores_the_configuration_and_removes_the_account(box):
    cfg = reset(*paths(box))
    assert (cfg.mode, cfg.outbound, cfg.access_points) == ("bridge", ("eth1",), {})
    back = load_config(str(box / "wanpire.json"))
    assert back.to_dict() == FACTORY | {"router": {"address": "10.77.0.1/24"}}
    assert not Account(box / "account").exists()
    assert json.loads((box / "factory.json").read_text()) == FACTORY  # the copy stays


def test_without_a_factory_copy_it_refuses_and_changes_nothing(box):
    (box / "factory.json").unlink()
    with pytest.raises(NoFactoryCopy, match="run the install again"):
        reset(*paths(box))
    assert json.loads((box / "wanpire.json").read_text()) == CHANGED
    assert Account(box / "account").exists()


def test_an_invalid_copy_is_refused_and_changes_nothing(box):
    (box / "factory.json").write_text(json.dumps(dict(FACTORY, adapters={
        "control": "wlan0", "inbound": "eth0", "outbound": ["eth0"]})))
    with pytest.raises(InvalidConfig, match="outbound shares its adapter with nothing"):
        reset(*paths(box))
    (box / "factory.json").write_text("{not json")
    with pytest.raises(InvalidConfig, match="not valid JSON"):
        reset(*paths(box))
    assert json.loads((box / "wanpire.json").read_text()) == CHANGED
    assert Account(box / "account").exists()


def test_the_copy_is_not_checked_against_the_adapters(box):
    # the box may have other adapters now; a missing line adapter leaves the line waiting
    (box / "factory.json").write_text(json.dumps(dict(FACTORY, adapters={
        "control": "wlan0", "inbound": "eth0", "outbound": ["wlx1"]})))
    assert reset(*paths(box)).outbound == ("wlx1",)
