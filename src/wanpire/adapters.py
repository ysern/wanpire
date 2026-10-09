"""The box's network adapters: what each one is, read from sysfs, and whether its radio can
be a Wi-Fi access point, read from ``iw``. Nothing here changes anything.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass

SYSFS_NET = "/sys/class/net"
KINDS = ("ethernet", "usb-ethernet", "wifi", "virtual")


@dataclass(frozen=True)
class Adapter:
    name: str
    kind: str  # one of KINDS
    mac: str
    state: str  # the kernel's operstate: up, down, unknown, ...
    speed_mbit: int | None
    can_be_ap: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _run(argv: list[str], check: bool = True) -> str:
    return subprocess.run(argv, capture_output=True, text=True, check=check).stdout


def _kind(path: str) -> str:
    if os.path.isdir(os.path.join(path, "wireless")) or os.path.exists(
            os.path.join(path, "phy80211")):
        return "wifi"
    device = os.path.join(path, "device")
    if not os.path.exists(device):
        return "virtual"
    if "/usb" in os.path.realpath(device).replace("\\", "/"):
        return "usb-ethernet"
    return "ethernet"


def _can_be_ap(path: str, runner) -> bool:
    phy = _read(os.path.join(path, "phy80211", "name"))
    if not phy:
        return False
    try:
        out = runner(["iw", "phy", phy, "info"], check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    modes, inside = set(), False
    for line in out.splitlines():
        text = line.strip()
        if text.startswith("Supported interface modes"):
            inside = True
            continue
        if inside:
            if text.startswith("* "):
                modes.add(text[2:].strip())
            else:
                break
    return "AP" in modes


def list_adapters(sysfs_net: str = SYSFS_NET, runner=_run) -> list[Adapter]:
    """Every adapter but loopback, in name order."""
    out = []
    for name in sorted(os.listdir(sysfs_net)):
        path = os.path.join(sysfs_net, name)
        if name == "lo":
            continue
        speed = _read(os.path.join(path, "speed"))
        try:
            mbit = int(speed) if speed else None
        except ValueError:
            mbit = None
        kind = _kind(path)
        out.append(Adapter(
            name=name, kind=kind, mac=_read(os.path.join(path, "address")) or "",
            state=_read(os.path.join(path, "operstate")) or "unknown",
            speed_mbit=mbit if mbit and mbit > 0 else None,
            can_be_ap=kind == "wifi" and _can_be_ap(path, runner),
        ))
    return out
