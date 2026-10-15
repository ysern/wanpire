"""Reading and changing the roles: the Roles object and GET/PUT /api/v1/roles. No root: the
modes and the file are recorded."""

import base64

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from wanpire.account import Account  # noqa: E402
from wanpire.adapters import Adapter  # noqa: E402
from wanpire.api import create_app  # noqa: E402
from wanpire.broker import Broker  # noqa: E402
from wanpire.config import config_from_dict, load_config  # noqa: E402
from wanpire.modes import ModeRefused  # noqa: E402
from wanpire.roles import Roles  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(b"admin:correct horse").decode()}
AP = {"ssid": "lab-ap", "passphrase": "correct horse"}


def adapter(name, kind, can_be_ap=None):
    return Adapter(name=name, kind=kind, mac="00:00:00:00:00:00", state="up", speed_mbit=None,
                   can_be_ap=kind == "wifi" if can_be_ap is None else can_be_ap)


ADAPTERS = [adapter("eth0", "ethernet"), adapter("eth1", "usb-ethernet"),
            adapter("wlan0", "wifi"), adapter("wlan1", "wifi"), adapter("wpbr0", "virtual")]
BY_NAME = {a.name: a for a in ADAPTERS}
DOC = {"schema": "wanpire-config/1", "mode": "bridge",
       "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]},
       "wifi": {"country": "GB"}}


class RecordingModes:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    def up(self, cfg):
        self.calls.append(("up", cfg.inbound, cfg.outbound[0]))
        if self.fail_on and cfg.outbound[0] == self.fail_on:
            raise ModeRefused("the access point on wlan1 did not come up: no channel")

    def down(self, cfg):
        self.calls.append(("down", cfg.inbound, cfg.outbound[0]))


class Engine:
    def __init__(self):
        self.applied, self.calls = False, []

    def read(self, adapter):
        return {"down": {"applied": self.applied}, "up": {"applied": False}}

    def apply(self, adapter, link, lifetime_s=None):
        self.calls.append(("apply", adapter))
        self.applied = True

    def clear(self, adapter):
        self.calls.append(("clear", adapter))
        self.applied = False

    def renew(self, adapter, lifetime_s):
        pass


@pytest.fixture
def roles(tmp_path):
    path = tmp_path / "wanpire.json"
    cfg = config_from_dict(DOC, BY_NAME)
    r = Roles(cfg, list_adapters=lambda: ADAPTERS, modes=RecordingModes(), path=str(path))
    r.path_obj = path
    return r


def box(tmp_path, roles, engine=None):
    engine = engine or Engine()
    broker = Broker(on_clear=lambda: engine.clear(roles.config.outbound[0]))
    account = Account(tmp_path / "account")
    account.set("admin", "correct horse")
    app = create_app(engine=engine, broker=broker, config=roles.config, account=account,
                     list_adapters=lambda: ADAPTERS, tick_s=None, fail_delay_s=0,
                     with_mcp=False, roles=roles)
    c = TestClient(app)
    c.engine, c.broker = engine, broker
    return c


def test_the_offered_adapters_leave_out_virtual_ones_and_a_wifi_control(roles):
    assert roles.offered() == ["eth0", "eth1", "wlan1"]


def test_a_wired_control_adapter_stays_offered(tmp_path):
    cfg = config_from_dict(dict(DOC, mode="router", adapters={
        "control": "eth0", "inbound": "eth0", "outbound": ["eth1"]}), BY_NAME)
    r = Roles(cfg, list_adapters=lambda: ADAPTERS, modes=RecordingModes(),
              path=str(tmp_path / "w.json"))
    assert r.offered() == ["eth0", "eth1", "wlan0", "wlan1"]


def test_reading_the_roles(tmp_path, roles):
    got = box(tmp_path, roles).get("/api/v1/roles", headers=AUTH).json()
    assert (got["mode"], got["control"], got["inbound"], got["outbound"]) == (
        "bridge", "wlan0", "eth0", "eth1")
    assert [a["name"] for a in got["offered"]] == ["eth0", "eth1", "wlan1"]
    assert {a["name"]: a["kind"] for a in got["offered"]}["wlan1"] == "wifi"
    assert got["access_points"] == {} and got["country"] == "GB"


def test_one_adapter_in_both_roles_is_refused_and_nothing_changes(tmp_path, roles):
    c = box(tmp_path, roles)
    r = c.put("/api/v1/roles", json={"inbound": "eth1", "outbound": "eth1"}, headers=AUTH)
    assert r.status_code == 422 and "must be different adapters" in r.json()["error"]
    assert roles.modes.calls == [] and not roles.path_obj.exists()


def test_a_bad_password_is_refused(tmp_path, roles):
    r = box(tmp_path, roles).put("/api/v1/roles", headers=AUTH, json={
        "inbound": "eth0", "outbound": "wlan1",
        "access_points": {"wlan1": {"ssid": "lab-ap", "passphrase": "short"}}})
    assert r.status_code == 422 and "8 to 63 printable ASCII" in r.json()["error"]
    assert roles.modes.calls == []


def test_an_adapter_not_offered_is_refused(tmp_path, roles):
    r = box(tmp_path, roles).put("/api/v1/roles", headers=AUTH, json={
        "inbound": "eth0", "outbound": "wlan0", "access_points": {"wlan0": AP}})
    assert r.status_code == 422 and "wlan0" in r.json()["error"]


def test_outbound_becomes_an_access_point(tmp_path, roles):
    c = box(tmp_path, roles)
    r = c.put("/api/v1/roles", headers=AUTH, json={
        "inbound": "eth0", "outbound": "wlan1", "access_points": {"wlan1": AP}})
    assert r.status_code == 200, r.text
    assert r.json()["outbound"] == "wlan1" and r.json()["access_points"] == {"wlan1": AP}
    assert roles.modes.calls == [("down", "eth0", "eth1"), ("up", "eth0", "wlan1")]
    saved = load_config(str(roles.path_obj), BY_NAME)
    assert saved.outbound == ("wlan1",) and saved.access_point("wlan1") == AP
    status = c.get("/api/v1/status", headers=AUTH).json()
    assert status["outbound"] == "wlan1"
    rows = {a["name"]: a["role"] for a in c.get("/api/v1/adapters", headers=AUTH).json()}
    assert rows["wlan1"] == "outbound" and rows["eth1"] is None


def test_the_link_follows_the_new_outbound(tmp_path, roles):
    c = box(tmp_path, roles)
    c.put("/api/v1/roles", headers=AUTH, json={
        "inbound": "eth0", "outbound": "wlan1", "access_points": {"wlan1": AP}})
    ticket = c.post("/api/v1/lease", json={"who": "A", "purpose": "p"},
                    headers=AUTH).json()["ticket"]
    c.put("/api/v1/link", json={"near": "london", "far": "london"},
          headers={**AUTH, "X-Wanpire-Ticket": ticket})
    assert c.engine.calls[-1] == ("apply", "wlan1")


def test_a_link_applied_refuses_a_change(tmp_path, roles):
    c = box(tmp_path, roles)
    c.engine.applied = True
    r = c.put("/api/v1/roles", headers=AUTH, json={"inbound": "eth1", "outbound": "eth0"})
    assert r.status_code == 409 and "no link applied and no lease held" in r.json()["error"]
    assert roles.modes.calls == []


def test_a_lease_held_refuses_a_change(tmp_path, roles):
    c = box(tmp_path, roles)
    c.post("/api/v1/lease", json={"who": "A", "purpose": "p"}, headers=AUTH)
    r = c.put("/api/v1/roles", headers=AUTH, json={"inbound": "eth1", "outbound": "eth0"})
    assert r.status_code == 409


def test_a_failed_set_up_puts_the_old_roles_back(tmp_path):
    path = tmp_path / "wanpire.json"
    cfg = config_from_dict(DOC, BY_NAME)
    modes = RecordingModes(fail_on="wlan1")
    roles = Roles(cfg, list_adapters=lambda: ADAPTERS, modes=modes, path=str(path))
    r = box(tmp_path, roles).put("/api/v1/roles", headers=AUTH, json={
        "inbound": "eth0", "outbound": "wlan1", "access_points": {"wlan1": AP}})
    assert r.status_code == 500 and "no channel" in r.json()["error"]
    assert modes.calls == [("down", "eth0", "eth1"), ("up", "eth0", "wlan1"),
                           ("down", "eth0", "wlan1"), ("up", "eth0", "eth1")]
    assert roles.config.outbound == ("eth1",)
    assert load_config(str(path), BY_NAME).outbound == ("eth1",)


def test_other_access_points_are_kept(tmp_path):
    cfg = config_from_dict(dict(DOC, access_points={"wlan1": AP}), BY_NAME)
    roles = Roles(cfg, list_adapters=lambda: ADAPTERS, modes=RecordingModes(),
                  path=str(tmp_path / "w.json"))
    new = roles.change("eth1", "eth0", {})
    assert new.access_points == {"wlan1": AP}


# -- a Wi-Fi inbound adapter joins a network as a client (the owner, 2026-10-11) -------------

NET = {"ssid": "upstream", "passphrase": ""}


def test_reading_the_roles_names_no_network_to_join(tmp_path, roles):
    got = box(tmp_path, roles).get("/api/v1/roles", headers=AUTH).json()
    assert got["wifi_clients"] == {}


def test_a_wifi_inbound_in_bridge_mode_is_refused_with_why(tmp_path, roles):
    r = box(tmp_path, roles).put("/api/v1/roles", headers=AUTH, json={
        "inbound": "wlan1", "outbound": "eth1", "wifi_clients": {"wlan1": NET}})
    assert r.status_code == 422
    assert "cannot be a bridge port" in r.json()["error"] and "router mode" in r.json()["error"]
    assert roles.modes.calls == [] and not roles.path_obj.exists()


@pytest.fixture
def router_roles(tmp_path):
    cfg = config_from_dict(dict(DOC, mode="router"), BY_NAME)
    r = Roles(cfg, list_adapters=lambda: ADAPTERS, modes=RecordingModes(),
              path=str(tmp_path / "wanpire.json"))
    r.path_obj = tmp_path / "wanpire.json"
    return r


def test_a_wifi_inbound_joins_a_network_in_router_mode(tmp_path, router_roles):
    r = box(tmp_path, router_roles).put("/api/v1/roles", headers=AUTH, json={
        "inbound": "wlan1", "outbound": "eth1", "wifi_clients": {"wlan1": NET},
        "access_points": {"wlan1": AP}})
    assert r.status_code == 200, r.text
    assert r.json()["inbound"] == "wlan1" and r.json()["wifi_clients"] == {"wlan1": NET}
    assert r.json()["access_points"] == {}  # an access point is only ever an outbound one
    saved = load_config(str(router_roles.path_obj), BY_NAME)
    assert saved.client_adapter == "wlan1" and saved.wifi_client("wlan1") == NET
    assert router_roles.modes.calls == [("down", "eth0", "eth1"), ("up", "wlan1", "eth1")]


def test_a_bad_client_password_is_refused(tmp_path, router_roles):
    r = box(tmp_path, router_roles).put("/api/v1/roles", headers=AUTH, json={
        "inbound": "wlan1", "outbound": "eth1",
        "wifi_clients": {"wlan1": {"ssid": "upstream", "passphrase": "short"}}})
    assert r.status_code == 422 and "64 hexadecimal" in r.json()["error"]


def test_wifi_clients_must_be_a_mapping(tmp_path, router_roles):
    r = box(tmp_path, router_roles).put("/api/v1/roles", headers=AUTH, json={
        "inbound": "wlan1", "outbound": "eth1", "wifi_clients": ["wlan1"]})
    assert r.status_code == 422 and "wifi_clients" in r.json()["error"]


# -- the line down for an adapter that is not plugged in (serve-with-the-line-down) ----------

DOWN_DOC = dict(DOC, adapters={"control": "wlan0", "inbound": "eth0", "outbound": ["wlx1"]})
DOWN_REASON = "outbound adapter wlx1 is not plugged in"


def down_roles(tmp_path, present=None, modes=None):
    """Roles as `wanpire serve` makes them with the USB stick `wlx1` out: the configuration
    loaded without the adapter check, `wlx1` missing. ``present`` is the box's adapter list,
    which a test may add the stick to."""
    present = ADAPTERS if present is None else present
    cfg = config_from_dict(DOWN_DOC)
    r = Roles(cfg, list_adapters=lambda: present, modes=modes or RecordingModes(),
              path=str(tmp_path / "wanpire.json"), missing=("wlx1",))
    r.path_obj = tmp_path / "wanpire.json"
    return r


def test_the_line_view_down_names_the_missing_adapter_and_why(tmp_path):
    r = down_roles(tmp_path)
    assert r.line_up is False and r.missing == ("wlx1",)
    assert r.line_view() == {"up": False, "missing": ["wlx1"], "reason": DOWN_REASON}


def test_the_line_view_up(roles):
    assert roles.line_up is True and roles.line_view() == {"up": True}


def test_watch_brings_the_line_up_once_the_adapter_appears(tmp_path):
    present = list(ADAPTERS)
    r = down_roles(tmp_path, present)
    r.watch()
    assert not r.line_up and r.modes.calls == []
    present.append(adapter("wlx1", "usb-ethernet"))
    r.watch()
    assert r.line_up and r.modes.calls == [("up", "eth0", "wlx1")]
    assert r.line_view() == {"up": True}
    r.watch()
    assert r.modes.calls == [("up", "eth0", "wlx1")]  # once


def test_watch_checks_the_wifi_rules_once_the_adapter_is_there(tmp_path):
    # a Wi-Fi outbound adapter is an access point: the loaded configuration could not know the
    # adapter's kind while it was out, so the rules run when it appears
    present = list(ADAPTERS) + [adapter("wlx1", "wifi")]
    r = down_roles(tmp_path, present)
    r.watch()
    assert not r.line_up and r.modes.calls == []
    assert r.line_view()["missing"] == [] and "network name" in r.line_view()["reason"]


def test_a_refused_set_up_leaves_the_line_down_with_the_refusal(tmp_path):
    present = list(ADAPTERS) + [adapter("wlx1", "usb-ethernet")]
    r = down_roles(tmp_path, present, modes=RecordingModes(fail_on="wlx1"))
    r.watch()
    assert not r.line_up
    assert r.line_view() == {"up": False, "missing": [],
                             "reason": "the access point on wlan1 did not come up: no channel"}
    r.watch()  # tried again at the next tick
    assert r.modes.calls == [("up", "eth0", "wlx1")] * 2


def test_a_change_while_down_brings_the_line_up(tmp_path):
    r = down_roles(tmp_path)
    r.change("eth0", "eth1", {})
    assert r.line_up and r.line_view() == {"up": True}
    assert r.modes.calls == [("down", "eth0", "wlx1"), ("up", "eth0", "eth1")]
    assert load_config(str(r.path_obj), BY_NAME).outbound == ("eth1",)


def test_a_failed_change_while_down_leaves_the_old_file_and_the_line_down(tmp_path):
    r = down_roles(tmp_path, modes=RecordingModes(fail_on="wlan1"))
    with pytest.raises(ModeRefused, match="no channel"):
        r.change("eth0", "wlan1", {"wlan1": AP})
    assert not r.line_up and r.config.outbound == ("wlx1",)
    assert r.line_view() == {"up": False, "missing": ["wlx1"], "reason": DOWN_REASON}
    assert load_config(str(r.path_obj)).outbound == ("wlx1",)
    assert r.modes.calls == [("down", "eth0", "wlx1"), ("up", "eth0", "wlan1"),
                             ("down", "eth0", "wlan1")]  # old is not set up: wlx1 is out


def test_the_roles_view_names_the_missing_adapter(tmp_path):
    got = box(tmp_path, down_roles(tmp_path)).get("/api/v1/roles", headers=AUTH).json()
    assert got["outbound"] == "wlx1" and got["missing"] == ["wlx1"]


def test_the_roles_view_names_nothing_missing(tmp_path, roles):
    assert box(tmp_path, roles).get("/api/v1/roles", headers=AUTH).json()["missing"] == []
