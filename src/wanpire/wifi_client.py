"""A Wi-Fi inbound adapter joining a network of the wider world as a client, through
``wpa_supplicant`` and ``dhcpcd`` run for that adapter only.

wanpire writes wpa_supplicant's settings to ``<state_dir>/wpa-<adapter>.conf`` (readable by root
only: it holds the password) and runs it in the background with a pid file and a log beside it,
as it runs hostapd. Once joined, ``dhcpcd`` takes an IPv4 address for the adapter with no hook
script (so ``resolv.conf`` and the box's other settings are left alone) and a route metric well
above any the box's own adapters get, so the box's own traffic keeps to its control adapter.
The adapter answers ARP for its own addresses only, and has no IPv6, for the same reason: on the
same network as the control adapter it must never draw the control adapter's traffic.

Nothing here names any adapter but the one it is given, and ``stop`` touches an adapter only if
wanpire joined it: a wired inbound's own DHCP client is not wanpire's.
"""

from __future__ import annotations

import os
import re
import signal
import time

from .engine import CommandFailed, run

DEFAULT_STATE_DIR = "/run/wanpire"
METRIC = 4000  # above the box's own routes (networkd gives 100 wired, 600 Wi-Fi)
JOIN_S = 30
_HEX64 = re.compile(r"[0-9A-Fa-f]{64}")


class WifiClientFailed(RuntimeError):
    """The adapter did not join the network, or got no address from it; with the reason."""


def wpa_settings(adapter: str, net: dict, ctrl_dir: str, country: str | None) -> str:
    """wpa_supplicant's settings for joining ``net`` (``ssid``, ``passphrase``), already
    validated. The name is written in hexadecimal, so no character in it can end the line; a
    quoted password ends at its last quote, and holds no line break (printable ASCII only)."""
    pw = net["passphrase"]
    lines = ["# written by wanpire; do not edit, it is rewritten each time the mode is set up",
             f"ctrl_interface={ctrl_dir}"]
    if country:
        lines.append(f"country={country}")
    lines += ["network={",
              f"    ssid={net['ssid'].encode('utf-8').hex()}",
              "    scan_ssid=0"]  # hidden networks are not supported
    if pw == "":
        lines.append("    key_mgmt=NONE")
    elif _HEX64.fullmatch(pw):  # the key itself: WPA2 only, since WPA3 (SAE) needs the password
        lines += ["    key_mgmt=WPA-PSK WPA-PSK-SHA256", f"    psk={pw.lower()}",
                  "    ieee80211w=1"]
    else:
        lines += ["    key_mgmt=WPA-PSK WPA-PSK-SHA256 SAE", f'    psk="{pw}"',
                  f'    sae_password="{pw}"', "    ieee80211w=1"]
    lines.append("}")
    return "\n".join(lines) + "\n"


def _is_wpa(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
            return f.read().strip() == "wpa_supplicant"
    except OSError:
        return False


def _terminate(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(50):
        if not _is_wpa(pid):
            return
        time.sleep(0.05)


class WifiClient:
    def __init__(self, state_dir: str = DEFAULT_STATE_DIR, runner=None, is_wpa=_is_wpa,
                 kill=_terminate, sleep=time.sleep, join_s: float = JOIN_S):
        self.state_dir = state_dir
        self._run = runner or run
        self._is_wpa = is_wpa
        self._kill = kill
        self._sleep = sleep
        self._join_s = join_s

    def _path(self, adapter: str, ext: str) -> str:
        return os.path.join(self.state_dir, f"wpa-{adapter}.{ext}")

    def _ctrl(self, adapter: str) -> str:
        return os.path.join(self.state_dir, f"wpa-{adapter}")

    def joined(self, adapter: str) -> bool:
        """wanpire joined ``adapter`` to a network and has not left it."""
        return os.path.exists(self._path(adapter, "conf"))

    def start(self, adapter: str, net: dict, country: str | None) -> None:
        """Join ``net`` on ``adapter`` and take an address from it (again, if joined)."""
        self.stop(adapter)
        os.makedirs(self.state_dir, exist_ok=True)
        conf, log = self._path(adapter, "conf"), self._path(adapter, "log")
        fd = os.open(conf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(wpa_settings(adapter, net, self._ctrl(adapter), country))
        os.chmod(conf, 0o600)
        # the box's own traffic stays on control: ARP for this adapter's addresses only, no IPv6
        for setting in (f"net.ipv4.conf.{adapter}.arp_ignore=1",
                        f"net.ipv4.conf.{adapter}.arp_announce=2",
                        f"net.ipv6.conf.{adapter}.disable_ipv6=1"):
            self._run(["sysctl", "-qw", setting])
        try:
            self._run(["wpa_supplicant", "-B", "-D", "nl80211", "-i", adapter, "-c", conf,
                       "-P", self._path(adapter, "pid"), "-f", log])
        except CommandFailed as e:
            self._fail(adapter, f"{adapter} did not join {net['ssid']}: "
                                f"{self._tail(log) or e.stderr.strip() or e}")
        if not self._wait_joined(adapter):
            self._fail(adapter, f"{adapter} did not join {net['ssid']} within "
                                f"{self._join_s:g} s: {self._tail(log) or 'no reason given'}")
        try:
            self._run(["dhcpcd", "-4", "-f", "/dev/null", "-c", "/bin/true", "-m", str(METRIC),
                       "-t", str(JOIN_S), adapter])
        except CommandFailed as e:
            self._fail(adapter, f"{adapter} joined {net['ssid']} but got no address from "
                                f"{net['ssid']}: {e.stderr.strip() or e}")

    def _wait_joined(self, adapter: str) -> bool:
        waited = 0.0
        while True:
            out = self._run(["wpa_cli", "-p", self._ctrl(adapter), "-i", adapter, "status"],
                            check=False) or ""
            if "wpa_state=COMPLETED" in out:
                return True
            if waited >= self._join_s:
                return False
            self._sleep(1.0)
            waited += 1.0

    def gateway(self, adapter: str) -> str | None:
        """The gateway the network gave ``adapter``, from the route dhcpcd added."""
        out = self._run(["ip", "-4", "route", "show", "default", "dev", adapter],
                        check=False) or ""
        m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", out)
        return m.group(1) if m else None

    def stop(self, adapter: str) -> None:
        """Leave the network on ``adapter`` if wanpire joined it; safe to run twice."""
        if not self.joined(adapter):
            return
        self._run(["dhcpcd", "-x", "-4", adapter], check=False)
        pid = self._pid(adapter)
        if pid:
            self._kill(pid)
        self._remove(adapter)

    def _fail(self, adapter: str, reason: str):
        self.stop(adapter)
        raise WifiClientFailed(reason)

    def _pid(self, adapter: str) -> int | None:
        try:
            with open(self._path(adapter, "pid"), encoding="utf-8") as f:
                pid = int(f.read().strip())
        except (OSError, ValueError):
            return None
        return pid if self._is_wpa(pid) else None

    def _remove(self, adapter: str) -> None:
        for ext in ("pid", "conf", "log"):
            try:
                os.remove(self._path(adapter, ext))
            except OSError:
                pass

    @staticmethod
    def _tail(log: str, n: int = 3) -> str:
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                return " / ".join(line.strip() for line in f.read().splitlines()[-n:] if line)
        except OSError:
            return ""
