"""The REST API, against a recording engine and a broker on a fake clock. No root."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from wanpire import catalogue  # noqa: E402
from wanpire.adapters import Adapter  # noqa: E402
from wanpire.api import create_app  # noqa: E402
from wanpire.broker import Broker  # noqa: E402
from wanpire.config import config_from_dict  # noqa: E402
from wanpire.model import Direction, InvalidLink, Link  # noqa: E402

TOKEN = "t0ken"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


class RecordingEngine:
    def __init__(self):
        self.calls = []
        self.applied = False

    def apply(self, adapter, link, lifetime_s=None):
        self.calls.append(("apply", adapter, link, lifetime_s))
        self.applied = True

    def clear(self, adapter):
        self.calls.append(("clear", adapter))
        self.applied = False

    def renew(self, adapter, lifetime_s):
        self.calls.append(("renew", adapter, lifetime_s))

    def read(self, adapter):
        return {"down": {"applied": self.applied}, "up": {"applied": False}}


ADAPTERS = [Adapter("eth0", "ethernet", "aa:bb:cc:dd:ee:01", "up", 1000, False),
            Adapter("eth1", "usb-ethernet", "aa:bb:cc:dd:ee:02", "up", 1000, False),
            Adapter("wlan0", "wifi", "aa:bb:cc:dd:ee:03", "up", None, True)]
CONFIG = config_from_dict({"schema": "wanpire-config/1", "mode": "bridge",
                           "adapters": {"control": "wlan0", "inbound": "eth0",
                                        "outbound": ["eth1"]}})


@pytest.fixture
def box():
    engine, clock = RecordingEngine(), Clock()
    broker = Broker(clock=clock, on_clear=lambda: engine.clear("eth1"))
    app = create_app(engine=engine, broker=broker, config=CONFIG, token=TOKEN,
                     list_adapters=lambda: ADAPTERS, tick_s=None)
    client = TestClient(app)
    client.engine, client.clock, client.broker = engine, clock, broker
    return client


def ask(c, who="A", purpose="soak"):
    r = c.post("/api/v1/lease", json={"who": who, "purpose": purpose}, headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def t(ticket):
    return {**AUTH, "X-Wanpire-Ticket": ticket}


# -- the token ----------------------------------------------------------------------------

def test_no_token(box):
    r = box.get("/api/v1/status")
    assert r.status_code == 401


def test_a_wrong_token(box):
    assert box.get("/api/v1/status", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_status_with_the_token(box):
    ask(box)
    s = box.get("/api/v1/status", headers=AUTH).json()
    assert s["mode"] == "bridge" and s["outbound"] == "eth1"
    assert s["link"]["down"]["applied"] is False
    assert s["broker"]["holder"]["who"] == "A"


# -- the lease ----------------------------------------------------------------------------

def test_ask_queue_release_pass_on(box):
    a, b = ask(box, "A"), ask(box, "B")
    assert a["holds"] and not b["holds"] and b["position"] == 1
    assert box.delete("/api/v1/lease", headers=t(a["ticket"])).status_code == 204
    assert box.post("/api/v1/lease/poll", headers=t(b["ticket"])).json()["holds"]
    assert ("clear", "eth1") in box.engine.calls


def test_an_unknown_ticket_is_404(box):
    r = box.post("/api/v1/lease/poll", headers=t("nope"))
    assert r.status_code == 404 and "ask for the link again" in r.json()["error"]


def test_a_missing_ticket_is_400(box):
    assert box.post("/api/v1/lease/poll", headers=AUTH).status_code == 400


def test_ended_by_hand_is_410_once(box):
    a = ask(box)
    r = box.request("DELETE", "/api/v1/lease/holder", json={"reason": "the lab needs the line"},
                    headers=AUTH)
    assert r.status_code == 204
    r = box.post("/api/v1/lease/poll", headers=t(a["ticket"]))
    assert r.status_code == 410 and "the lab needs the line" in r.json()["error"]
    assert box.post("/api/v1/lease/poll", headers=t(a["ticket"])).status_code == 404


# -- the link -----------------------------------------------------------------------------

def test_apply_raw_figures(box):
    a = ask(box)
    r = box.put("/api/v1/link", json={"down": {"delay_ms": 50}, "up": {"loss_pct": 1}},
                headers=t(a["ticket"]))
    assert r.status_code == 200, r.text
    assert box.engine.calls[-1] == ("apply", "eth1",
                                    Link(down=Direction(delay_ms=50), up=Direction(loss_pct=1)),
                                    120)


def test_apply_from_two_ends(box):
    a = ask(box)
    r = box.put("/api/v1/link", json={"near": "london", "far": "new-york"},
                headers=t(a["ticket"]))
    assert r.status_code == 200, r.text
    link, _ = catalogue.preview("london", "new-york")
    assert box.engine.calls[-1][2] == link
    assert r.json()["account"]["path"]["origin"] == "table"
    assert r.json()["link"] == link.to_dict()


def test_apply_without_the_lease_is_409_naming_the_holder(box):
    ask(box, "A", "soak")
    b = ask(box, "B")
    r = box.put("/api/v1/link", json={"down": {"delay_ms": 5}}, headers=t(b["ticket"]))
    assert r.status_code == 409 and "A" in r.json()["error"] and "soak" in r.json()["error"]
    assert not any(c[0] == "apply" for c in box.engine.calls)


def test_an_invalid_link_is_422(box):
    a = ask(box)
    r = box.put("/api/v1/link", json={"down": {"loss_pct": 120}}, headers=t(a["ticket"]))
    assert r.status_code == 422 and "loss_pct" in r.json()["error"]


def test_an_unknown_end_is_422(box):
    a = ask(box)
    r = box.put("/api/v1/link", json={"near": "atlantis", "far": "london"},
                headers=t(a["ticket"]))
    assert r.status_code == 422 and "atlantis" in r.json()["error"]


def test_figures_and_ends_together_are_422(box):
    a = ask(box)
    r = box.put("/api/v1/link", json={"near": "london", "far": "tokyo", "down": {}},
                headers=t(a["ticket"]))
    assert r.status_code == 422


def test_engine_failure_is_500_with_the_reason(box):
    from wanpire.engine import CommandFailed

    def boom(*a, **k):
        raise CommandFailed(["tc"], 2, "RTNETLINK answers: No such device")
    box.engine.apply = boom
    a = ask(box)
    r = box.put("/api/v1/link", json={"down": {"delay_ms": 5}}, headers=t(a["ticket"]))
    assert r.status_code == 500 and "No such device" in r.json()["error"]


def test_clear_needs_the_lease(box):
    ask(box)
    b = ask(box, "B")
    assert box.delete("/api/v1/link", headers=t(b["ticket"])).status_code == 409


def test_clear(box):
    a = ask(box)
    assert box.delete("/api/v1/link", headers=t(a["ticket"])).status_code == 204
    assert box.engine.calls[-1] == ("clear", "eth1")


def test_reading_the_link_needs_no_ticket(box):
    r = box.get("/api/v1/link", headers=AUTH)
    assert r.status_code == 200 and r.json()["down"]["applied"] is False


# -- the dead-man -------------------------------------------------------------------------

def test_the_holders_poll_renews_the_dead_man(box):
    a = ask(box)
    box.put("/api/v1/link", json={"down": {"delay_ms": 5}}, headers=t(a["ticket"]))
    box.post("/api/v1/lease/poll", headers=t(a["ticket"]))
    assert box.engine.calls[-1] == ("renew", "eth1", 120)


def test_no_link_no_renewal(box):
    a = ask(box)
    box.post("/api/v1/lease/poll", headers=t(a["ticket"]))
    assert not any(c[0] == "renew" for c in box.engine.calls)


# -- reading ------------------------------------------------------------------------------

def test_endpoints(box):
    r = box.get("/api/v1/endpoints", headers=AUTH).json()
    london = next(e for e in r if e["id"] == "london")
    assert "mobile-4g" in london["channels"] and london["default_channel"] == "generic"


def test_one_endpoint(box):
    assert box.get("/api/v1/endpoints/tokyo", headers=AUTH).json()["name"] == "Tokyo"
    assert box.get("/api/v1/endpoints/atlantis", headers=AUTH).status_code == 404


def test_preview_changes_nothing(box):
    r = box.post("/api/v1/preview", json={"near": "london:consumer-fibre",
                                          "far": "los-angeles:mobile-4g"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["account"]["path"]["origin"] == "table"
    assert box.engine.calls == []


def test_adapters_with_roles(box):
    rows = {a["name"]: a for a in box.get("/api/v1/adapters", headers=AUTH).json()}
    assert rows["eth1"]["role"] == "outbound" and rows["wlan0"]["role"] == "control"


def test_invalid_link_from_the_model_is_the_same_message():
    with pytest.raises(InvalidLink, match="loss_pct"):
        Direction(loss_pct=120)
