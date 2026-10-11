"""The REST API, against a recording engine and a broker on a fake clock. No root."""

import base64

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from wanpire import catalogue  # noqa: E402
from wanpire.account import Account  # noqa: E402
from wanpire.adapters import Adapter  # noqa: E402
from wanpire.api import create_app  # noqa: E402
from wanpire.broker import Broker  # noqa: E402
from wanpire.config import config_from_dict  # noqa: E402
from wanpire.model import Direction, InvalidLink, Link  # noqa: E402

USER, PASSWORD = "admin", "correct horse"


def basic(user, password):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


AUTH = basic(USER, PASSWORD)


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


def make_box(path, with_account=True):
    engine, clock = RecordingEngine(), Clock()
    broker = Broker(clock=clock, on_clear=lambda: engine.clear("eth1"))
    account = Account(path)
    if with_account:
        account.set(USER, PASSWORD)
    app = create_app(engine=engine, broker=broker, config=CONFIG, account=account,
                     list_adapters=lambda: ADAPTERS, tick_s=None, fail_delay_s=0)
    client = TestClient(app)
    client.engine, client.clock, client.broker, client.account = engine, clock, broker, account
    return client


@pytest.fixture
def box(tmp_path):
    return make_box(tmp_path / "account")


@pytest.fixture
def new_box(tmp_path):
    """A box as installed: no account yet."""
    return make_box(tmp_path / "account", with_account=False)


def ask(c, who="A", purpose="soak"):
    r = c.post("/api/v1/lease", json={"who": who, "purpose": purpose}, headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def t(ticket):
    return {**AUTH, "X-Wanpire-Ticket": ticket}


# -- the account: the first visit ------------------------------------------------------

def test_a_new_box_says_it_needs_an_account(new_box):
    r = new_box.get("/api/v1/setup")
    assert r.status_code == 200 and r.json() == {"needed": True}


def test_a_new_box_refuses_everything_else(new_box):
    r = new_box.get("/api/v1/status")
    assert r.status_code == 403
    assert "account" in r.json()["error"] and "web page" in r.json()["error"]


def test_the_first_visit_makes_the_account_and_signs_in(new_box):
    r = new_box.post("/api/v1/setup", json={"user": "admin", "password": "twelve chars"})
    assert r.status_code == 201 and r.json() == {"user": "admin"}
    assert new_box.get("/api/v1/status").status_code == 200  # the cookie alone
    assert new_box.account.verify("admin", "twelve chars")
    assert new_box.get("/api/v1/setup").json() == {"needed": False}


def test_the_account_is_made_once(new_box):
    new_box.post("/api/v1/setup", json={"user": "admin", "password": "twelve chars"})
    r = new_box.post("/api/v1/setup", json={"user": "eve", "password": "twelve chars"})
    assert r.status_code == 409
    assert new_box.account.user == "admin"


@pytest.mark.parametrize("body, says", [
    ({"user": "admin", "password": "short"}, "8 characters"),
    ({"user": "two words", "password": "twelve chars"}, "user name"),
    ({"password": "twelve chars"}, "user name"),
])
def test_an_invalid_account_is_refused(new_box, body, says):
    r = new_box.post("/api/v1/setup", json=body)
    assert r.status_code == 422 and says in r.json()["error"]
    assert not new_box.account.exists()


# -- the account: credentials -------------------------------------------------------------

def test_no_credentials(box):
    r = box.get("/api/v1/status")
    assert r.status_code == 401


def test_a_wrong_password(box):
    assert box.get("/api/v1/status", headers=basic(USER, "wrong horse")).status_code == 401
    assert box.get("/api/v1/status", headers=basic("root", PASSWORD)).status_code == 401


def test_a_bearer_token_is_no_longer_taken(box):
    assert box.get("/api/v1/status", headers={"Authorization": "Bearer x"}).status_code == 401


def test_status_with_basic(box):
    ask(box)
    s = box.get("/api/v1/status", headers=AUTH).json()
    assert s["mode"] == "bridge" and s["outbound"] == "eth1"
    assert s["link"]["down"]["applied"] is False
    assert s["broker"]["holder"]["who"] == "A"


def test_setup_on_a_box_with_an_account_needs_nothing(box):
    assert box.get("/api/v1/setup").json() == {"needed": False}


# -- the account: a browser's session -----------------------------------------------------

def test_signing_in_sets_a_private_cookie(box):
    r = box.post("/api/v1/session", json={"user": USER, "password": PASSWORD})
    assert r.status_code == 200 and r.json() == {"user": USER}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert box.get("/api/v1/status").status_code == 200
    assert box.get("/api/v1/session").json() == {"user": USER}


def test_signing_in_with_a_wrong_password(box):
    r = box.post("/api/v1/session", json={"user": USER, "password": "wrong horse"})
    assert r.status_code == 401
    assert box.get("/api/v1/status").status_code == 401


def test_no_session(box):
    assert box.get("/api/v1/session").status_code == 401


def test_signing_out(box):
    box.post("/api/v1/session", json={"user": USER, "password": PASSWORD})
    assert box.delete("/api/v1/session").status_code == 204
    assert box.get("/api/v1/status").status_code == 401


def test_a_forged_cookie_is_refused(box):
    box.cookies.set("wanpire_session", "made-up")
    assert box.get("/api/v1/status").status_code == 401


def test_changing_the_password(box):
    box.post("/api/v1/session", json={"user": USER, "password": PASSWORD})
    second = TestClient(box.app)
    second.post("/api/v1/session", json={"user": USER, "password": PASSWORD})
    r = box.put("/api/v1/account/password", json={"current": PASSWORD, "new": "battery staple"})
    assert r.status_code == 204
    assert box.get("/api/v1/status").status_code == 200  # this session kept
    assert second.get("/api/v1/status").status_code == 401  # every other one ended
    assert box.get("/api/v1/status", headers=AUTH).status_code == 401
    assert box.get("/api/v1/status", headers=basic(USER, "battery staple")).status_code == 200


def test_changing_the_password_needs_the_current_one(box):
    box.post("/api/v1/session", json={"user": USER, "password": PASSWORD})
    r = box.put("/api/v1/account/password",
                json={"current": "wrong horse", "new": "battery staple"})
    assert r.status_code == 401
    assert box.account.verify(USER, PASSWORD)


def test_a_new_password_too_short(box):
    r = box.put("/api/v1/account/password", json={"current": PASSWORD, "new": "short"},
                headers=AUTH)
    assert r.status_code == 422


def _touch(path):
    import os
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


def test_a_password_set_over_ssh_is_seen_at_once(box):
    Account(box.account.path).set(USER, "battery staple")  # `sudo wanpire account set admin`
    _touch(box.account.path)
    assert box.get("/api/v1/status", headers=AUTH).status_code == 401
    assert box.get("/api/v1/status", headers=basic(USER, "battery staple")).status_code == 200


def test_a_reset_over_ssh_makes_the_box_new_again(box):
    Account(box.account.path).reset()  # `sudo wanpire account reset`
    assert box.get("/api/v1/status", headers=AUTH).status_code == 403
    assert box.get("/api/v1/setup").json() == {"needed": True}


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


def applied(box):
    return box.get("/api/v1/status", headers=AUTH).json()["applied"]


def test_the_status_names_no_link_at_first(box):
    assert applied(box) is None


def test_the_status_names_the_ends_applied(box):
    a = ask(box)
    box.put("/api/v1/link", json={"near": "london", "far": "los-angeles:mobile-4g"},
            headers=t(a["ticket"]))
    assert applied(box) == {"near": "london:generic", "far": "los-angeles:mobile-4g"}


def test_the_status_says_figures(box):
    a = ask(box)
    box.put("/api/v1/link", json={"down": {"delay_ms": 40}, "up": {"delay_ms": 40}},
            headers=t(a["ticket"]))
    assert applied(box) == {"figures": True}


def test_the_status_forgets_the_link_once_cleared(box):
    a = ask(box)
    box.put("/api/v1/link", json={"near": "london", "far": "tokyo"}, headers=t(a["ticket"]))
    box.delete("/api/v1/link", headers=t(a["ticket"]))
    assert applied(box) is None


def test_the_status_forgets_the_link_the_broker_cleared(box):
    a = ask(box)
    box.put("/api/v1/link", json={"near": "london", "far": "tokyo"}, headers=t(a["ticket"]))
    box.request("DELETE", "/api/v1/lease/holder", json={"reason": "bench needed"}, headers=AUTH)
    assert box.engine.applied is False
    assert applied(box) is None


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
