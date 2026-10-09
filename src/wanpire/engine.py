"""Applies a Link to the outbound adapter, reads it back, clears it.

Down is netem on the adapter's egress. Up is the adapter's ingress, redirected to an ifb
device that carries its own netem. Nothing is ever applied to another adapter, so the
control channel cannot be slowed by mistake.

Every command is an argument list handed to a runner (see ``run``), so the logic is tested
without root, and the namespace tests run the same code for real.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Iterable

from .model import Direction, Link
from .netem import netem_args

DEFAULT_LINE_RATE_MBIT = 1000
DEFAULT_LIFETIME_S = 120
IFNAMSIZ = 15


class CommandFailed(RuntimeError):
    def __init__(self, argv: list[str], code: int, stderr: str):
        super().__init__(f"{' '.join(argv)} failed ({code}): {stderr.strip()}")
        self.argv, self.code, self.stderr = argv, code, stderr


class RefusedAdapter(ValueError):
    pass


Runner = Callable[..., str]


def run(argv: list[str], check: bool = True, netns: str | None = None) -> str:
    """The real runner: runs a command, optionally inside a named network namespace."""
    full = (["ip", "netns", "exec", netns] if netns else []) + list(argv)
    p = subprocess.run(full, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise CommandFailed(full, p.returncode, p.stderr)
    return p.stdout


def ifb_name(adapter: str) -> str:
    name = f"ifb-{adapter}"
    if len(name) <= IFNAMSIZ:
        return name
    return "wp" + hashlib.sha1(adapter.encode()).hexdigest()[:10]


class Engine:
    def __init__(
        self,
        runner: Runner | None = None,
        control_adapters: Iterable[str] = (),
        netns: str | None = None,
        host_runner: Runner | None = None,
    ):
        """``runner`` runs commands where the adapter lives (inside ``netns`` if one is
        named); ``host_runner`` runs the dead-man's systemd commands, always on the host."""
        if runner is None:
            runner = lambda argv, check=True: run(argv, check=check, netns=netns)  # noqa: E731
            host_runner = host_runner or run
        self._run = runner
        self._host = host_runner or runner
        self._netns = netns
        self._control = set(control_adapters)

    # -- public ---------------------------------------------------------------

    def apply(
        self, adapter: str, link: Link, lifetime_s: float | None = DEFAULT_LIFETIME_S
    ) -> None:
        """Replace whatever the adapter carries with ``link``.

        With a lifetime, a dead-man clears the link when it runs out unless ``renew`` is
        called; it is a systemd timer, so it outlives this process.
        """
        self._refuse_control(adapter)
        self.clear(adapter)
        try:
            rate = self._line_rate(adapter)
            if not link.down.is_clear():
                self._netem(adapter, link.down, rate)
            if not link.up.is_clear():
                ifb = ifb_name(adapter)
                self._run(["ip", "link", "add", ifb, "type", "ifb"])
                self._run(["ip", "link", "set", ifb, "up"])
                self._netem(ifb, link.up, rate)
                self._run(["tc", "qdisc", "add", "dev", adapter, "handle", "ffff:", "ingress"])
                self._run(["tc", "filter", "add", "dev", adapter, "parent", "ffff:",
                           "protocol", "all", "prio", "1", "matchall",
                           "action", "mirred", "egress", "redirect", "dev", ifb])
        except Exception:
            self.clear(adapter)
            raise
        if lifetime_s:
            self._arm(adapter, lifetime_s)

    def renew(self, adapter: str, lifetime_s: float = DEFAULT_LIFETIME_S) -> None:
        """Push the dead-man's deadline to ``lifetime_s`` from now."""
        self._refuse_control(adapter)
        self._arm(adapter, lifetime_s)

    def clear(self, adapter: str) -> None:
        """Remove everything the engine adds. Succeeds when there is nothing to remove."""
        self._refuse_control(adapter)
        self._disarm(adapter)
        self._run(["tc", "qdisc", "del", "dev", adapter, "root"], check=False)
        self._run(["tc", "qdisc", "del", "dev", adapter, "ingress"], check=False)
        self._run(["ip", "link", "del", ifb_name(adapter)], check=False)

    def read(self, adapter: str) -> dict:
        """Per direction: whether a link is applied and netem's own counters."""
        return {
            "down": self._read_root(adapter),
            "up": self._read_root(ifb_name(adapter)),
        }

    # -- inside ---------------------------------------------------------------

    @staticmethod
    def _unit(adapter: str) -> str:
        return f"wanpire-deadman-{adapter}"

    def _disarm(self, adapter: str) -> None:
        self._host(["systemctl", "stop", f"{self._unit(adapter)}.timer"], check=False)

    def _arm(self, adapter: str, lifetime_s: float) -> None:
        self._disarm(adapter)
        # A finished or failed run of the previous dead-man would block the unit name.
        self._host(["systemctl", "reset-failed", f"{self._unit(adapter)}.service"], check=False)
        argv = ["systemd-run", f"--unit={self._unit(adapter)}", f"--on-active={lifetime_s:g}s",
                "--timer-property=AccuracySec=100ms", "--",
                sys.executable, "-m", "wanpire.cli", "clear", "--adapter", adapter]
        if self._netns:
            argv += ["--netns", self._netns]
        self._host(argv)

    def _refuse_control(self, adapter: str) -> None:
        if adapter in self._control:
            raise RefusedAdapter(
                f"{adapter} is the control adapter; wanpire never impairs it"
            )

    def _netem(self, dev: str, d: Direction, line_rate: float) -> None:
        self._run(["tc", "qdisc", "add", "dev", dev, "root", "netem",
                   *netem_args(d, line_rate_mbit=line_rate)])

    def _line_rate(self, adapter: str) -> float:
        try:
            mbit = int(self._run(["cat", f"/sys/class/net/{adapter}/speed"]).strip())
        except (CommandFailed, ValueError):
            return DEFAULT_LINE_RATE_MBIT
        return mbit if mbit > 0 else DEFAULT_LINE_RATE_MBIT

    def _read_root(self, dev: str) -> dict:
        try:
            out = self._run(["tc", "-s", "-j", "qdisc", "show", "dev", dev])
        except CommandFailed:
            return {"applied": False}
        for q in json.loads(out or "[]"):
            if q.get("root") and q.get("kind") == "netem":
                return {
                    "applied": True,
                    "packets": q.get("packets", 0),
                    "bytes": q.get("bytes", 0),
                    "dropped": q.get("drops", 0),
                    "queued": q.get("qlen", 0),
                    "limit": q.get("options", {}).get("limit"),
                }
        return {"applied": False}
