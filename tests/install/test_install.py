"""install/install.sh against a staging root, without root and without the hardware (spec: install).

Linux only: the script is POSIX sh for Debian-like systems.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("sh"),
                                reason="the install script is for Linux")

SCRIPT = Path(__file__).resolve().parents[2] / "install" / "install.sh"
ROLES = ["--control", "wlan0", "--inbound", "eth0", "--outbound", "eth1"]


def fake_sysfs(base: Path, ifaces: dict[str, str]) -> Path:
    """A /sys/class/net with each interface of a kind: wifi, onboard, usb or virtual."""
    net = base / "sys" / "class" / "net"
    net.mkdir(parents=True)
    for name, kind in ifaces.items():
        d = net / name
        d.mkdir()
        if kind == "virtual":
            continue
        usb = kind in ("usb", "usb-wifi")
        dev = base / "devices" / (f"usb2/2-1/2-1:1.0/{name}" if usb else f"platform/{name}")
        dev.mkdir(parents=True)
        (d / "device").symlink_to(dev)
        if kind in ("wifi", "usb-wifi"):
            (d / "wireless").mkdir()
    return net


PI = {"lo": "virtual", "wlan0": "wifi", "eth0": "onboard", "eth1": "usb"}


def fake_usb(base: Path, devices: dict[str, tuple[str, str, str, bool]]) -> Path:
    """A /sys/bus/usb/devices: name -> (vendor id, product id, product, driven)."""
    usb = base / "usb-devices"
    usb.mkdir(parents=True)
    for name, (vendor, product_id, product, driven) in devices.items():
        d = usb / name
        (d / f"{name}:1.0").mkdir(parents=True)
        (d / "idVendor").write_text(f"{vendor}\n")
        (d / "idProduct").write_text(f"{product_id}\n")
        (d / "product").write_text(f"{product}\n")
        if driven:
            (d / f"{name}:1.0" / "driver").symlink_to(base)
    return usb


NO_DRIVER = {"1-1.4": ("2357", "013f", "802.11ac WLAN Adapter", False),
             "2-1": ("0b95", "1790", "AX88179B", True)}


@pytest.fixture
def box(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sysfs = fake_sysfs(tmp_path, PI)

    usb = fake_usb(tmp_path, {})

    def run(*args, sysfs_dir=sysfs, usb_dir=usb, check=True, stdin=""):
        r = subprocess.run(["sh", str(SCRIPT), *args, "--root", str(root), "--no-venv",
                            "--sysfs", str(sysfs_dir), "--usb-sysfs", str(usb_dir)],
                           capture_output=True, text=True, timeout=60, input=stdin,
                           env={**os.environ, "PYTHON": sys.executable})
        if check:
            assert r.returncode == 0, r.stdout + r.stderr
        return r

    run.root = root
    run.tmp = tmp_path
    return run


def files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}


def mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


# -- a first install ------------------------------------------------------------------------

def test_a_first_install_with_roles(box):
    box(*ROLES)
    cfg = json.loads((box.root / "etc/wanpire/wanpire.json").read_text())
    assert cfg == {"schema": "wanpire-config/1", "mode": "bridge",
                   "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]}}
    unit = (box.root / "etc/systemd/system/wanpire.service").read_text()
    assert "ExecStart=/opt/wanpire/venv/bin/wanpire serve" in unit
    assert (box.root / "etc/systemd/system/multi-user.target.wants/wanpire.service").is_symlink()


def test_a_first_install_writes_no_credential(box):
    r = box(*ROLES)
    assert not (box.root / "etc/wanpire/token").exists()
    assert not (box.root / "etc/wanpire/account").exists()
    last = r.stdout.strip().splitlines()[-1]
    assert "account" in last and ":8080/" in last and "wanpire account set" in last


def test_the_account_given_to_the_install(box):
    from wanpire.account import Account
    r = box(*ROLES, "--user", "admin", stdin="correct horse\n")
    account = box.root / "etc/wanpire/account"
    assert Account(account).verify("admin", "correct horse")
    assert "correct horse" not in account.read_text()
    assert mode(account) == 0o600
    assert "none yet" not in r.stdout


def test_a_second_install_keeps_the_account(box):
    from wanpire.account import Account
    box(*ROLES, "--user", "admin", stdin="correct horse\n")
    before = (box.root / "etc/wanpire/account").read_bytes()
    r = box(*ROLES, "--user", "eve", stdin="battery staple\n")
    assert (box.root / "etc/wanpire/account").read_bytes() == before
    assert "wanpire account set" in r.stdout
    assert Account(box.root / "etc/wanpire/account").user == "admin"


def test_a_short_password_given_to_the_install_stops_it(box):
    r = box(*ROLES, "--user", "admin", stdin="short\n", check=False)
    assert r.returncode != 0
    assert "8 characters" in r.stderr
    assert not (box.root / "etc/wanpire/account").exists()


def test_an_old_token_is_removed(box):
    (box.root / "etc/wanpire").mkdir(parents=True)
    (box.root / "etc/wanpire/token").write_text("ab" * 32 + "\n")
    box(*ROLES)
    assert not (box.root / "etc/wanpire/token").exists()


def test_the_unit_clears_before_it_sets_up_and_serves(box):
    # The unit is unchanged by serve-with-the-line-down: a line adapter that is not plugged in
    # fails neither `reset` nor `up` (both exit 0, `up` saying the line waits for it), so the
    # server starts with the line down. The script stages no `wanpire` to run, so that
    # scenario is pinned by the CLI's unit tests (tests/unit/test_cli.py, `up` and `serve`).
    box(*ROLES)
    lines = (box.root / "etc/systemd/system/wanpire.service").read_text().splitlines()
    order = [i for i, line in enumerate(lines)
             if line.startswith(("ExecStartPre=", "ExecStart="))]
    cmds = [lines[i].split("wanpire ", 1)[-1] for i in order]
    assert cmds == ["reset", "up", "serve"]
    assert "Restart=on-failure" in lines


# -- detection ------------------------------------------------------------------------------

def test_roles_detected(box):
    out = box().stdout
    cfg = json.loads((box.root / "etc/wanpire/wanpire.json").read_text())
    assert cfg["adapters"] == {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]}
    assert "wlan0" in out and "eth1" in out


def test_no_outbound_port_stops_before_any_change(box):
    sysfs = fake_sysfs(box.tmp / "two", {"lo": "virtual", "wlan0": "wifi", "eth0": "onboard"})
    r = box(sysfs_dir=sysfs, check=False)
    assert r.returncode != 0
    assert "outbound" in r.stderr and "--outbound" in r.stderr
    assert files(box.root) == {}


def test_a_named_adapter_that_does_not_exist(box):
    r = box("--control", "wlan0", "--inbound", "eth0", "--outbound", "eth9", check=False)
    assert r.returncode != 0
    assert "eth9" in r.stderr
    assert files(box.root) == {}


def test_outbound_shared_with_control_refused(box):
    r = box("--control", "eth1", "--inbound", "eth0", "--outbound", "eth1", check=False)
    assert r.returncode != 0
    assert "outbound" in r.stderr
    assert files(box.root) == {}


# -- netplan --------------------------------------------------------------------------------

def test_netplan_in_bridge_mode(box):
    box(*ROLES)
    p = box.root / "etc/netplan/60-wanpire.yaml"
    text = p.read_text()
    assert "eth0:" in text and "eth1:" in text and "wlan0" not in text
    assert text.count("dhcp4: false") == 2 and text.count("dhcp6: false") == 2
    assert "accept-ra: false" in text and "link-local: []" in text
    assert mode(p) == 0o600


def test_netplan_in_router_mode(box):
    box(*ROLES, "--mode", "router")
    text = (box.root / "etc/netplan/60-wanpire.yaml").read_text()
    assert "eth1:" in text and "eth0" not in text and "wlan0" not in text
    cfg = json.loads((box.root / "etc/wanpire/wanpire.json").read_text())
    assert cfg["mode"] == "router"


# -- idempotence and refusals ---------------------------------------------------------------

def test_idempotent(box):
    box(*ROLES)
    first = files(box.root)
    out = box(*ROLES).stdout
    assert files(box.root) == first
    assert "unchanged" in out


def test_other_roles_on_an_installed_box_refused(box):
    box(*ROLES)
    first = files(box.root)
    r = box("--control", "wlan0", "--inbound", "eth0", "--outbound", "eth2", check=False)
    assert r.returncode != 0
    assert "wanpire.json" in r.stderr and "--purge" in r.stderr
    assert files(box.root) == first


def test_dry_run_writes_nothing(box):
    r = box(*ROLES, "--dry-run")
    assert "would" in r.stdout
    assert files(box.root) == {}


@pytest.mark.skipif(sys.platform.startswith("linux") and os.geteuid() == 0,
                    reason="run as root")
def test_without_root_or_a_staging_root_refused():
    r = subprocess.run(["sh", str(SCRIPT), *ROLES, "--no-venv"], capture_output=True,
                       text=True, timeout=60)
    assert r.returncode != 0
    assert "root" in r.stderr


# -- uninstall ------------------------------------------------------------------------------

def test_uninstall_keeps_the_configuration(box):
    box(*ROLES, "--user", "admin", stdin="correct horse\n")
    box("uninstall")
    left = files(box.root)
    assert set(left) == {"etc/wanpire/wanpire.json", "etc/wanpire/factory.json",
                         "etc/wanpire/account"}
    assert not (box.root / "etc/systemd/system/multi-user.target.wants/wanpire.service").exists()
    assert not (box.root / "opt/wanpire").exists()


def test_uninstall_purge(box):
    box(*ROLES)
    box("uninstall", "--purge")
    assert files(box.root) == {}
    assert not (box.root / "etc/wanpire").exists()


def test_install_after_uninstall_keeps_the_account(box):
    box(*ROLES, "--user", "admin", stdin="correct horse\n")
    account = (box.root / "etc/wanpire/account").read_text()
    box("uninstall")
    box(*ROLES)
    assert (box.root / "etc/wanpire/account").read_text() == account


def test_no_check_installs_roles_not_plugged_in(box):
    box("--control", "wlan0", "--inbound", "eth0", "--outbound", "eth7", "--no-check")
    cfg = json.loads((box.root / "etc/wanpire/wanpire.json").read_text())
    assert cfg["adapters"]["outbound"] == ["eth7"]


def test_no_check_needs_every_role(box):
    r = box("--outbound", "eth7", "--no-check", check=False)
    assert r.returncode != 0
    assert "--control" in r.stderr
    assert files(box.root) == {}


# -- Wi-Fi: the access point's driver and country (host-a-wifi-access-point) -----------------

def test_a_new_configuration_is_readable_by_root_only(box):
    box(*ROLES)
    assert mode(box.root / "etc/wanpire/wanpire.json") == 0o600


def test_a_second_install_keeps_what_the_page_saved(box):
    box(*ROLES)
    cfg = box.root / "etc/wanpire/wanpire.json"
    saved = json.loads(cfg.read_text())
    saved["adapters"]["outbound"] = ["eth1"]
    saved["access_points"] = {"wlan1": {"ssid": "lab-ap", "passphrase": "correct horse"}}
    saved["wifi"] = {"country": "GB"}
    cfg.write_text(json.dumps(saved))
    box(*ROLES)
    assert json.loads(cfg.read_text()) == saved


def test_the_country_from_the_option(box):
    box(*ROLES, "--wifi-country", "GB")
    cfg = json.loads((box.root / "etc/wanpire/wanpire.json").read_text())
    assert cfg["wifi"] == {"country": "GB"}


def test_the_country_added_to_an_installed_box(box):
    box(*ROLES)
    box(*ROLES, "--wifi-country", "US")
    cfg = json.loads((box.root / "etc/wanpire/wanpire.json").read_text())
    assert cfg["wifi"] == {"country": "US"} and cfg["adapters"]["outbound"] == ["eth1"]


# -- the factory copy: the install's state, for a reset (reset-the-box-to-its-install-state) -

def test_a_first_install_keeps_a_factory_copy(box):
    box(*ROLES)
    config = box.root / "etc/wanpire/wanpire.json"
    factory = box.root / "etc/wanpire/factory.json"
    assert json.loads(factory.read_text()) == json.loads(config.read_text())
    assert mode(factory) == 0o600


def test_a_box_installed_before_the_copy_existed_gets_one_from_its_configuration(box):
    box(*ROLES)
    factory = box.root / "etc/wanpire/factory.json"
    factory.unlink()
    before = files(box.root)
    r = box(*ROLES)
    assert "factory" in r.stdout and "copied" in r.stdout
    assert json.loads(factory.read_text()) == json.loads(
        (box.root / "etc/wanpire/wanpire.json").read_text())
    assert mode(factory) == 0o600
    now = files(box.root)
    del now["etc/wanpire/factory.json"]
    assert now == before


def test_the_factory_copy_is_left_alone_when_the_roles_changed_since(box):
    box(*ROLES)
    cfg = box.root / "etc/wanpire/wanpire.json"
    factory = box.root / "etc/wanpire/factory.json"
    first = factory.read_bytes()
    saved = json.loads(cfg.read_text())
    saved["adapters"]["outbound"] = ["wlan1"]
    saved["access_points"] = {"wlan1": {"ssid": "lab-ap", "passphrase": "correct horse"}}
    saved["wifi"] = {"country": "GB"}
    cfg.write_text(json.dumps(saved))
    box()  # run again, no roles given: it keeps what it finds
    assert factory.read_bytes() == first
    assert json.loads(cfg.read_text()) == saved


def test_uninstall_purge_removes_the_factory_copy(box):
    box(*ROLES)
    assert (box.root / "etc/wanpire/factory.json").exists()
    box("uninstall", "--purge")
    assert files(box.root) == {}


def test_a_country_that_is_not_one_is_refused(box):
    r = box(*ROLES, "--wifi-country", "gb", check=False)
    assert r.returncode != 0 and "--wifi-country" in r.stderr
    assert files(box.root) == {}


def test_a_usb_wifi_adapter_is_not_taken_for_control(box):
    sysfs = fake_sysfs(box.tmp / "two-radios", {"lo": "virtual", "wlan0": "usb-wifi",
                                                "wlan1": "wifi", "eth0": "onboard",
                                                "eth1": "usb"})
    box(sysfs_dir=sysfs)
    cfg = json.loads((box.root / "etc/wanpire/wanpire.json").read_text())
    assert cfg["adapters"]["control"] == "wlan1"


def test_an_adapter_with_no_driver_is_named_and_none_installed(box):
    usb = fake_usb(box.tmp / "b", NO_DRIVER)
    r = box(*ROLES, usb_dir=usb)
    line = [x for x in r.stdout.splitlines() if "2357:013f" in x]
    assert line and "no driver" in line[0] and "--wifi-driver" in line[0]
    assert "0b95:1790" not in r.stdout
    assert "dkms" not in r.stdout


def test_the_driver_step_in_a_dry_run(box):
    usb = fake_usb(box.tmp / "b", NO_DRIVER)
    r = box(*ROLES, "--wifi-driver", "--dry-run", usb_dir=usb)
    out = r.stdout
    for want in ("linux-headers-", "dkms", "git", "github.com/morrownr/rtw89", "dkms install",
                 "/etc/dkms/rtw89.conf",
                 "install_fw", "/etc/modprobe.d/"):
        assert want in out, want
    assert files(box.root) == {}
