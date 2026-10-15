"""A test bed for the web UI: the real app on a free port, a recording engine, a real broker,
and a headless browser. Skipped where Playwright or its browser is missing."""

from __future__ import annotations

import base64
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

try:
    import uvicorn
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # no Playwright here (pip install -e ".[ui-test]"): skip the page tests
    collect_ignore_glob = ["test_*.py"]

from wanpire.account import Account  # noqa: E402
from wanpire.adapters import Adapter  # noqa: E402
from wanpire.api import create_app  # noqa: E402
from wanpire.broker import Broker  # noqa: E402
from wanpire.config import config_from_dict  # noqa: E402
from wanpire.roles import Roles  # noqa: E402

USER, PASSWORD = "admin", "correct horse"
AUTH = {"Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()}
LEASE_TTL_S = 3.0  # the page polls at a third of it: once a second

ADAPTERS = [Adapter("eth0", "ethernet", "aa:bb:cc:dd:ee:01", "up", 1000, False),
            Adapter("eth1", "usb-ethernet", "aa:bb:cc:dd:ee:02", "up", 1000, False),
            Adapter("wlan0", "wifi", "aa:bb:cc:dd:ee:03", "up", None, True),
            Adapter("wlan1", "wifi", "aa:bb:cc:dd:ee:04", "down", None, True),
            Adapter("wpbr0", "virtual", "aa:bb:cc:dd:ee:05", "up", None, False)]
CONFIG = config_from_dict({"schema": "wanpire-config/1", "mode": "bridge",
                           "adapters": {"control": "wlan0", "inbound": "eth0",
                                        "outbound": ["eth1"]},
                           "wifi": {"country": "GB"}})
# a box served with its USB stick `wlx1`, the outbound adapter, unplugged: loaded unchecked
DOWN_CONFIG = config_from_dict({"schema": "wanpire-config/1", "mode": "bridge",
                                "adapters": {"control": "wlan0", "inbound": "eth0",
                                             "outbound": ["wlx1"]},
                                "wifi": {"country": "GB"}})
STICK = Adapter("wlx1", "usb-ethernet", "aa:bb:cc:dd:ee:06", "up", 1000, False)


class RecordingModes:
    def __init__(self):
        self.calls = []

    def up(self, cfg):
        self.calls.append(("up", cfg.inbound, cfg.outbound[0]))

    def down(self, cfg):
        self.calls.append(("down", cfg.inbound, cfg.outbound[0]))


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
    def __init__(self, with_account=True, config=CONFIG, missing=()):
        """``missing``: the configured line adapters the box lacks (the line starts down).
        ``adapters`` is the box's list, which a test may plug the stick into."""
        self.engine = RecordingEngine()
        self.modes = RecordingModes()
        self.adapters = list(ADAPTERS)
        self.config_path = Path(tempfile.mkdtemp()) / "wanpire.json"
        self.roles = Roles(config, lambda: self.adapters, modes=self.modes,
                           path=str(self.config_path), missing=missing)
        self.broker = Broker(on_clear=lambda: self.engine.clear(self.roles.config.outbound[0]),
                             lease_ttl_s=LEASE_TTL_S, queue_ttl_s=LEASE_TTL_S)
        self.account = Account(Path(tempfile.mkdtemp()) / "account")
        if with_account:
            self.account.set(USER, PASSWORD)
        app = create_app(engine=self.engine, broker=self.broker, config=config,
                         account=self.account, list_adapters=lambda: self.adapters,
                         tick_s=None, fail_delay_s=0, roles=self.roles)
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
def new_box():
    """A box as installed: no account yet."""
    b = Box(with_account=False)
    b.start()
    yield b
    b.stop()


@pytest.fixture
def down_box():
    """A box started with the stick out: the line is down for outbound `wlx1`."""
    b = Box(config=DOWN_CONFIG, missing=("wlx1",))
    b.start()
    yield b
    b.stop()


def _page(browser, box):
    context = browser.new_context(viewport={"width": 1000, "height": 900})
    pg = context.new_page()
    pg.box = box
    pg.set_default_timeout(5000)
    return context, pg


@pytest.fixture
def page(browser, box):
    context, pg = _page(browser, box)
    yield pg
    context.close()


@pytest.fixture
def new_page(browser, new_box):
    context, pg = _page(browser, new_box)
    yield pg
    context.close()


@pytest.fixture
def down_page(browser, down_box):
    context, pg = _page(browser, down_box)
    yield pg
    context.close()


def sign_in(page, user=USER, password=PASSWORD):
    """Open the page and sign in with the box's account."""
    page.goto(page.box.url + "/")
    page.fill("#user", user)
    page.fill("#password", password)
    page.click("#signin-save")
