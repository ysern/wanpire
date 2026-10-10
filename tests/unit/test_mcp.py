"""The MCP server: in process, over real streamable HTTP, and over stdio (spec: mcp-server)."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("mcp")
import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from mcp import Client  # noqa: E402
from mcp.client.stdio import StdioServerParameters  # noqa: E402

from wanpire.account import Account  # noqa: E402
from wanpire.adapters import Adapter  # noqa: E402
from wanpire.api import create_app  # noqa: E402
from wanpire.broker import Broker  # noqa: E402
from wanpire.config import config_from_dict  # noqa: E402

USER, PASSWORD = "admin", "correct horse"
AUTH = {"Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()}
TOOLS = {"wanpire_status", "wanpire_endpoints", "wanpire_lease", "wanpire_poll",
         "wanpire_describe", "wanpire_apply", "wanpire_clear", "wanpire_counters",
         "wanpire_release"}

ADAPTERS = [Adapter("eth0", "ethernet", "aa:bb:cc:dd:ee:01", "up", 1000, False),
            Adapter("eth1", "usb-ethernet", "aa:bb:cc:dd:ee:02", "up", 1000, False),
            Adapter("wlan0", "wifi", "aa:bb:cc:dd:ee:03", "up", None, True)]
CONFIG = config_from_dict({"schema": "wanpire-config/1", "mode": "bridge",
                           "adapters": {"control": "wlan0", "inbound": "eth0",
                                        "outbound": ["eth1"]}})


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
        if not self.applied:
            return {"down": {"applied": False}, "up": {"applied": False}}
        return {"down": {"applied": True, "packets": 42, "bytes": 4200, "dropped": 1,
                         "queued": 0, "limit": 1000},
                "up": {"applied": True, "packets": 7, "bytes": 700, "dropped": 0,
                       "queued": 0, "limit": 1000}}


class Box:
    def __init__(self):
        self.engine = RecordingEngine()
        self.broker = Broker(on_clear=lambda: self.engine.clear("eth1"))
        self.account = Account(Path(tempfile.mkdtemp()) / "account")
        self.account.set(USER, PASSWORD)
        self.app = create_app(engine=self.engine, broker=self.broker, config=CONFIG,
                              account=self.account, list_adapters=lambda: ADAPTERS,
                              tick_s=None, fail_delay_s=0)
        self.mcp = self.app.state.mcp

    def rest_ask(self, who="person", purpose="web page"):
        with TestClient(self.app) as c:
            r = c.post("/api/v1/lease", json={"who": who, "purpose": purpose}, headers=AUTH)
            return r.json()["ticket"]


@pytest.fixture
def box():
    return Box()


def run(coro):
    return asyncio.run(coro)


def data(result):
    """A tool result's JSON, whether it came structured or as text."""
    s = result.structured_content
    if isinstance(s, dict):
        return s.get("result", s) if set(s) == {"result"} else s
    return json.loads(result.content[0].text)


async def call(target, name, args=None):
    async with Client(target) as c:
        return await c.call_tool(name, args or {})


def tool(target, name, args=None):
    r = run(call(target, name, args))
    assert not r.is_error, r.content[0].text
    return data(r)


def tool_error(target, name, args=None) -> str:
    r = run(call(target, name, args))
    assert r.is_error
    return r.content[0].text


# -- in process -----------------------------------------------------------------------------

def test_the_tools_listed(box):
    async def go():
        async with Client(box.mcp) as c:
            return {t.name for t in (await c.list_tools()).tools}
    names = run(go())
    assert names == TOOLS
    assert not any("end_" in n or "holder" in n for n in names)


def test_status(box):
    s = tool(box.mcp, "wanpire_status")
    assert s["mode"] == "bridge"
    assert s["broker"]["holder"] is None


def test_endpoints(box):
    eps = tool(box.mcp, "wanpire_endpoints")["endpoints"]
    london = next(e for e in eps if e["id"] == "london")
    assert "mobile-4g" in london["channels"]


def test_describe_changes_nothing(box):
    d = tool(box.mcp, "wanpire_describe", {"near": "london", "far": "los-angeles:mobile-4g"})
    assert d["link"]["down"]["delay_ms"] == pytest.approx(98.8)
    assert d["account"]["path"]["origin"] == "table"
    assert box.engine.calls == []


def test_lease_free(box):
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    assert a["holds"] is True
    assert a["ticket"]
    assert a["poll_every_s"] == 40  # a third of the 120 s lease
    assert "apply" in a["next"]


def test_the_same_broker_queued_then_granted(box):
    person = box.rest_ask()
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    assert a["holds"] is False and a["position"] == 1
    assert a["poll_every_s"] == 20  # a third of the 60 s queue TTL
    assert "wait" in a["next"]
    with TestClient(box.app) as c:
        c.delete("/api/v1/lease", headers={**AUTH, "X-Wanpire-Ticket": person})
    p = tool(box.mcp, "wanpire_poll", {"ticket": a["ticket"]})
    assert p["holds"] is True


def test_release(box):
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    r = tool(box.mcp, "wanpire_release", {"ticket": a["ticket"]})
    assert r["released"] is True
    assert box.broker.status()["holder"] is None


def test_apply_from_ends_then_counters_then_clear(box):
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    out = tool(box.mcp, "wanpire_apply",
               {"ticket": a["ticket"], "near": "london", "far": "los-angeles:mobile-4g"})
    assert out["link"]["down"]["delay_ms"] == pytest.approx(98.8)
    applied = [c for c in box.engine.calls if c[0] == "apply"]
    assert applied[0][2].down.delay_ms == pytest.approx(98.8)
    assert applied[0][3] == 120  # the lease's TTL drives the dead-man
    c = tool(box.mcp, "wanpire_counters")
    assert c["down"]["packets"] == 42
    tool(box.mcp, "wanpire_clear", {"ticket": a["ticket"]})
    assert box.engine.calls[-1] == ("clear", "eth1")


def test_apply_from_figures(box):
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    tool(box.mcp, "wanpire_apply", {"ticket": a["ticket"], "down": {"delay_ms": 150},
                                    "up": {"delay_ms": 150, "loss_pct": 1}})
    link = box.engine.calls[-1][2]
    assert link.down.delay_ms == 150 and link.up.loss_pct == 1


def test_apply_needs_ends_or_figures(box):
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    msg = tool_error(box.mcp, "wanpire_apply", {"ticket": a["ticket"]})
    assert "near" in msg and "down" in msg


def test_ended_by_hand_says_why(box):
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    box.broker.end_lease("bench needed")
    msg = tool_error(box.mcp, "wanpire_apply",
                     {"ticket": a["ticket"], "near": "london", "far": "tokyo"})
    assert "lease ended" in msg.lower()
    assert "bench needed" in msg


def test_not_the_holder_names_the_holder(box):
    box.rest_ask(who="person", purpose="web page")
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    msg = tool_error(box.mcp, "wanpire_apply",
                     {"ticket": a["ticket"], "near": "london", "far": "tokyo"})
    assert "person" in msg


def test_an_invalid_link(box):
    a = tool(box.mcp, "wanpire_lease", {"who": "agent-1", "purpose": "soak"})
    msg = tool_error(box.mcp, "wanpire_apply",
                     {"ticket": a["ticket"], "down": {"delay_ms": -5}})
    assert "invalid" in msg.lower()


# -- /mcp over real HTTP --------------------------------------------------------------------

def test_mcp_route_needs_the_account(box):
    with TestClient(box.app) as c:
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401


def test_mcp_route_refuses_a_wrong_password(box):
    wrong = {"Authorization": "Basic " + base64.b64encode(f"{USER}:nope".encode()).decode()}
    with TestClient(box.app) as c:
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                   headers=wrong)
    assert r.status_code == 401


def test_mcp_route_does_not_take_the_web_pages_cookie(box):
    # another site's page could make a signed-in browser post here; it would carry the cookie
    with TestClient(box.app) as c:
        assert c.post("/api/v1/session", json={"user": USER, "password": PASSWORD}).is_success
        assert c.get("/api/v1/status").status_code == 200
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401


def test_mcp_route_on_a_box_without_an_account(box):
    box.account.reset()
    with TestClient(box.app) as c:
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                   headers=AUTH)
    assert r.status_code == 403


class Served:
    """The app on a free port, in a thread, as `wanpire serve` runs it."""

    def __init__(self, app):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port,
                                                    log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            assert time.monotonic() < deadline, "the test server did not start"
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(5)


def test_an_mcp_client_over_http_with_the_account(box):
    import httpx2
    from mcp.client.streamable_http import streamable_http_client

    with Served(box.app) as s:
        async def go():
            async with httpx2.AsyncClient(headers=AUTH) as http:
                transport = streamable_http_client(s.url + "/mcp", http_client=http)
                async with Client(transport) as c:
                    r = await c.call_tool("wanpire_status", {})
                    return data(r)
        st = run(go())
    assert st["mode"] == "bridge"
    assert "broker" in st


# -- over stdio on a host -------------------------------------------------------------------

def test_stdio_without_a_password_refuses(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ("WANPIRE_PASSWORD",)}
    env["WANPIRE_USER"] = USER
    r = subprocess.run([sys.executable, "-m", "wanpire.cli", "mcp", "--url",
                        "http://127.0.0.1:9", "--password-file", str(tmp_path / "none")],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode != 0
    assert "WANPIRE_USER" in r.stderr and "WANPIRE_PASSWORD" in r.stderr


def test_stdio_reads_the_password_from_a_file(box, tmp_path):
    f = tmp_path / "password"
    f.write_text(PASSWORD + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "WANPIRE_PASSWORD"}
    with Served(box.app) as s:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "wanpire.cli", "mcp", "--url", s.url, "--password-file", str(f)],
            env={**env, "WANPIRE_USER": USER})
        st = tool(params, "wanpire_status")
    assert st["mode"] == "bridge"


def test_stdio_calls_the_box(box):
    with Served(box.app) as s:
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "wanpire.cli", "mcp", "--url", s.url],
            env={**os.environ, "WANPIRE_USER": USER, "WANPIRE_PASSWORD": PASSWORD})
        st = tool(params, "wanpire_status")
        a = tool(params, "wanpire_lease", {"who": "agent-2", "purpose": "stdio"})
    assert st["mode"] == "bridge"
    assert a["holds"] is True
    assert box.broker.status()["holder"]["who"] == "agent-2"


def test_rest_client_is_httpx():
    # the tools speak plain HTTP to the REST API, in process or across the network
    from wanpire import mcp_server
    assert isinstance(mcp_server.rest_client("http://box:8080", USER, PASSWORD),
                      httpx.AsyncClient)


def test_rest_client_needs_credentials():
    from wanpire import mcp_server
    with pytest.raises(ValueError, match="user name and password"):
        mcp_server.rest_client("http://box:8080")
