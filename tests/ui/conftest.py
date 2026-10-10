"""A test bed for the web UI: the real app on a free port, a recording engine, a real broker,
and a headless browser. Skipped where Playwright or its browser is missing."""

from __future__ import annotations

import socket
import threading
import time

import pytest

try:
    import uvicorn
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # no Playwright here (pip install -e ".[ui-test]"): skip the page tests
    collect_ignore_glob = ["test_*.py"]

from wanpire.adapters import Adapter  # noqa: E402
from wanpire.api import create_app  # noqa: E402
from wanpire.broker import Broker  # noqa: E402
from wanpire.config import config_from_dict  # noqa: E402

TOKEN = "t0ken"
LEASE_TTL_S = 3.0  # the page polls at a third of it: once a second

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
        self.packets = 0

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
        return {"down": {"applied": True, "packets": self.packets, "bytes": self.packets * 1500,
                         "dropped": 3, "shaper_dropped": 2, "queued": 1, "limit": 1000},
                "up": {"applied": True, "packets": 0, "bytes": 0, "dropped": 0, "queued": 0,
                       "limit": 1000}}


class Box:
    def __init__(self):
        self.engine = RecordingEngine()
        self.broker = Broker(on_clear=lambda: self.engine.clear("eth1"),
                             lease_ttl_s=LEASE_TTL_S, queue_ttl_s=LEASE_TTL_S)
        app = create_app(engine=self.engine, broker=self.broker, config=CONFIG, token=TOKEN,
                         list_adapters=lambda: ADAPTERS, tick_s=None)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port,
                                                    log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self):
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("the test server did not start")
            time.sleep(0.05)

    def stop(self):
        self.server.should_exit = True
        self.thread.join(5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except PlaywrightError as e:  # no browser installed: `python -m playwright install`
            pytest.skip(f"no headless Chromium: {e}")
        yield b
        b.close()


@pytest.fixture
def box():
    b = Box()
    b.start()
    yield b
    b.stop()


@pytest.fixture
def page(browser, box):
    context = browser.new_context(viewport={"width": 1000, "height": 900})
    pg = context.new_page()
    pg.box = box
    pg.set_default_timeout(5000)
    yield pg
    context.close()


def sign_in(page, token=TOKEN, name="ana"):
    """Open the page and give it the token and a name."""
    page.goto(page.box.url + "/")
    page.fill("#token", token)
    page.fill("#name", name)
    page.click("#token-save")
