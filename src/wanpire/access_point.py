"""An access point on a Wi-Fi adapter, through ``hostapd``: 5 GHz, channel 36 at 80 MHz, WPA2
and WPA3-Personal, under a regulatory country.

wanpire writes hostapd's settings to ``<state_dir>/hostapd-<adapter>.conf`` (readable by root
only: it holds the password), and runs it in the background with a pid file and a log file
beside it, as it runs dnsmasq. In bridge mode hostapd puts the adapter in the bridge itself
(``bridge=``). Nothing here names any adapter but the one it is given.
"""

from __future__ import annotations

import os
import signal
import time

from .engine import CommandFailed, run

DEFAULT_STATE_DIR = "/run/wanpire"
CHANNEL = 36  # non-DFS, allowed nearly everywhere: starts with no radar wait
CENTRE_80MHZ = 42  # the centre of channels 36 to 48


class AccessPointFailed(RuntimeError):
    """hostapd did not bring the access point up; the message carries its last lines."""


def hostapd_settings(adapter: str, ap: dict, country: str, bridge: str | None = None) -> str:
    """hostapd's settings for ``ap`` (``ssid``, ``passphrase``), already validated. The name is
    written in hexadecimal (``ssid2``), so no character in it can end the line."""
    ssid_hex = ap["ssid"].encode("utf-8").hex()
    lines = [
        "# written by wanpire; do not edit, it is rewritten each time the mode is set up",
        f"interface={adapter}",
        *([f"bridge={bridge}"] if bridge else []),
        "driver=nl80211",
        "ctrl_interface=/run/hostapd",
        f"ssid2={ssid_hex}",
        "utf8_ssid=1",
        f"country_code={country}",
        "ieee80211d=1",
        "hw_mode=a",
        f"channel={CHANNEL}",
        "ieee80211n=1",
        "ht_capab=[HT40+][SHORT-GI-20][SHORT-GI-40]",
        "ieee80211ac=1",
        "vht_oper_chwidth=1",
        f"vht_oper_centr_freq_seg0_idx={CENTRE_80MHZ}",
        "wmm_enabled=1",
        "auth_algs=1",
        "wpa=2",
        "wpa_key_mgmt=WPA-PSK SAE",
        "rsn_pairwise=CCMP",
        f"wpa_passphrase={ap['passphrase']}",
        f"sae_password={ap['passphrase']}",
        "ieee80211w=1",
        "sae_require_mfp=1",
    ]
    return "\n".join(lines) + "\n"


def _is_hostapd(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
            return f.read().strip() == "hostapd"
    except OSError:
        return False


def _terminate(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(50):
        if not _is_hostapd(pid):
            return
        time.sleep(0.05)


class AccessPoint:
    def __init__(self, state_dir: str = DEFAULT_STATE_DIR, runner=None, is_hostapd=_is_hostapd,
                 kill=_terminate):
        self.state_dir = state_dir
        self._run = runner or run
        self._is_hostapd = is_hostapd
        self._kill = kill

    def _path(self, adapter: str, ext: str) -> str:
        return os.path.join(self.state_dir, f"hostapd-{adapter}.{ext}")

    def _pid(self, adapter: str) -> int | None:
        try:
            with open(self._path(adapter, "pid"), encoding="utf-8") as f:
                pid = int(f.read().strip())
        except (OSError, ValueError):
            return None
        return pid if self._is_hostapd(pid) else None

    def running(self, adapter: str) -> bool:
        return self._pid(adapter) is not None

    def start(self, adapter: str, ap: dict, country: str, bridge: str | None = None) -> None:
        """Start (or restart) the access point on ``adapter``."""
        self.stop(adapter)
        os.makedirs(self.state_dir, exist_ok=True)
        conf, log = self._path(adapter, "conf"), self._path(adapter, "log")
        fd = os.open(conf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(hostapd_settings(adapter, ap, country, bridge))
        os.chmod(conf, 0o600)
        try:
            self._run(["hostapd", "-B", "-P", self._path(adapter, "pid"), "-f", log, conf])
        except CommandFailed as e:
            reason = self._tail(log) or e.stderr.strip() or str(e)
            self._remove(adapter)
            raise AccessPointFailed(f"the access point on {adapter} did not come up: "
                                    f"{reason}") from None

    def stop(self, adapter: str) -> None:
        """Stop the access point on ``adapter`` if wanpire started one; safe to run twice."""
        pid = self._pid(adapter)
        if pid:
            self._kill(pid)
        self._remove(adapter)

    def _remove(self, adapter: str) -> None:
        for ext in ("pid", "conf", "log"):
            try:
                os.remove(self._path(adapter, ext))
            except OSError:
                pass

    @staticmethod
    def _tail(log: str, n: int = 4) -> str:
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                return " / ".join(line.strip() for line in f.read().splitlines()[-n:] if line)
        except OSError:
            return ""
