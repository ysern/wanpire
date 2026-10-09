"""Puts the box on the line in bridge or router-with-NAT mode, and takes it off again.

- **Bridge:** inbound and outbound joined in a bridge, STP off, no address anywhere. A port
  that carries an address is refused, never stripped (stripping could cut the session).
- **Router with NAT:** outbound gets an address on a private network of its own and a DHCP
  server (dnsmasq, bound to outbound only); an nftables table of wanpire's own forwards
  outbound's traffic and masquerades it out of inbound; IPv4 forwarding is switched on.

Links, addresses and the bridge go through pyroute2; the ruleset through ``nft -f``, which
takes a readable file; DHCP through dnsmasq with its whole configuration on the command line.

What teardown needs to put back (forwarding's value before setup, dnsmasq's pid) is kept in a
state directory, ``/run/wanpire`` by default: a tmpfs, so a reboot forgets it, as it forgets
the setup itself. Both directions are safe to run twice.
"""

from __future__ import annotations

import ipaddress
import os
import signal
import time

from .config import Config
from .engine import CommandFailed, run

NFT_TABLE = "wanpire"
DEFAULT_STATE_DIR = "/run/wanpire"


class ModeRefused(RuntimeError):
    """Setting up a mode was refused, with the reason; nothing was changed."""


def _attr(msg, name):
    try:
        return msg.get(name)
    except (AttributeError, KeyError):
        return msg.get_attr(name)


class Modes:
    def __init__(self, netns: str | None = None, state_dir: str = DEFAULT_STATE_DIR,
                 runner=None):
        self.netns = netns
        self.state_dir = state_dir
        self._run = runner or (lambda argv, check=True: run(argv, check=check, netns=netns))

    # -- public ---------------------------------------------------------------------------

    def up(self, cfg: Config) -> None:
        if cfg.mode == "bridge":
            self._bridge_up(cfg)
        else:
            self._router_up(cfg)

    def down(self, cfg: Config) -> None:
        """Remove whatever either mode may have set up for these adapters."""
        self._bridge_down(cfg)
        self._router_down(cfg)

    # -- pyroute2 ---------------------------------------------------------------------------

    def _ipr(self):
        from pyroute2 import IPRoute, NetNS  # imported here: the unit tests need no pyroute2
        return NetNS(self.netns) if self.netns else IPRoute()

    @staticmethod
    def _index(ipr, name: str) -> int | None:
        found = list(ipr.link_lookup(ifname=name))
        return found[0] if found else None

    def _require(self, ipr, name: str, role: str) -> int:
        idx = self._index(ipr, name)
        if idx is None:
            raise ModeRefused(f"{role} adapter {name} does not exist")
        return idx

    @staticmethod
    def _addresses(ipr, idx: int) -> list[str]:
        """IPv4 addresses and global IPv6 ones (a link-local IPv6 address is harmless)."""
        out = []
        for m in ipr.get_addr(index=idx):
            fam, scope = m["family"], m["scope"]
            addr = _attr(m, "IFA_ADDRESS")
            if fam == 2 or (fam == 10 and scope == 0):
                out.append(f"{addr}/{m['prefixlen']}")
        return out

    # -- bridge -----------------------------------------------------------------------------

    def _bridge_up(self, cfg: Config) -> None:
        ports = [(cfg.inbound, "inbound"), (cfg.outbound[0], "outbound")]
        with self._ipr() as ipr:
            idx = {name: self._require(ipr, name, role) for name, role in ports}
            for name, _ in ports:
                held = self._addresses(ipr, idx[name])
                if held:
                    raise ModeRefused(
                        f"{name} carries {', '.join(held)}; a bridge port carries no address. "
                        "Remove it (the install does this at boot) or use router mode"
                    )
            br = self._index(ipr, cfg.bridge_name)
            if br is None:
                ipr.link("add", ifname=cfg.bridge_name, kind="bridge", br_stp_state=0)
                br = self._index(ipr, cfg.bridge_name)
            for name, _ in ports:
                ipr.link("set", index=idx[name], master=br)
                ipr.link("set", index=idx[name], state="up")
            ipr.link("set", index=br, state="up")

    def _bridge_down(self, cfg: Config) -> None:
        with self._ipr() as ipr:
            br = self._index(ipr, cfg.bridge_name)
            if br is not None:
                ipr.link("del", index=br)

    # -- router -----------------------------------------------------------------------------

    def _state(self, name: str) -> str:
        return os.path.join(self.state_dir, name)

    def _router_up(self, cfg: Config) -> None:
        out = cfg.outbound[0]
        iface = ipaddress.ip_interface(cfg.router_address)
        with self._ipr() as ipr:
            self._require(ipr, cfg.inbound, "inbound")
            idx = self._require(ipr, out, "outbound")
            have = self._addresses(ipr, idx)
            if str(iface) not in have:
                ipr.addr("add", index=idx, address=str(iface.ip),
                         prefixlen=iface.network.prefixlen)
            ipr.link("set", index=idx, state="up")
        os.makedirs(self.state_dir, exist_ok=True)
        self._forwarding_on()
        self._nft_up(cfg)
        self._dhcp_up(cfg)

    def _router_down(self, cfg: Config) -> None:
        out = cfg.outbound[0]
        self._dhcp_down(out)
        self._run(["nft", "delete", "table", "inet", NFT_TABLE], check=False)
        iface = ipaddress.ip_interface(cfg.router_address)
        with self._ipr() as ipr:
            idx = self._index(ipr, out)
            if idx is not None and str(iface) in self._addresses(ipr, idx):
                ipr.addr("del", index=idx, address=str(iface.ip),
                         prefixlen=iface.network.prefixlen)
        self._forwarding_restore()

    def _forwarding_on(self) -> None:
        saved = self._state("ip_forward")
        if not os.path.exists(saved):  # a second setup must not record its own "on"
            before = self._run(["sysctl", "-n", "net.ipv4.ip_forward"]).strip()
            with open(saved, "w", encoding="utf-8") as f:
                f.write(before + "\n")
        self._run(["sysctl", "-q", "-w", "net.ipv4.ip_forward=1"])

    def _forwarding_restore(self) -> None:
        saved = self._state("ip_forward")
        if not os.path.exists(saved):
            return
        with open(saved, encoding="utf-8") as f:
            before = f.read().strip()
        if before in ("0", "1"):
            self._run(["sysctl", "-q", "-w", f"net.ipv4.ip_forward={before}"])
        os.remove(saved)

    def _nft_up(self, cfg: Config) -> None:
        inb, out, net = cfg.inbound, cfg.outbound[0], cfg.router_network
        ruleset = f"""table inet {NFT_TABLE} {{
    chain forward {{
        type filter hook forward priority 0; policy accept;
        iifname "{out}" oifname "{inb}" accept
        iifname "{inb}" oifname "{out}" ct state established,related accept
        iifname "{inb}" oifname "{out}" drop
    }}
    chain postrouting {{
        type nat hook postrouting priority 100; policy accept;
        oifname "{inb}" ip saddr {net} masquerade
    }}
}}
"""
        path = self._state("nftables.conf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(ruleset)
        self._run(["nft", "delete", "table", "inet", NFT_TABLE], check=False)
        self._run(["nft", "-f", path])

    def _dhcp_up(self, cfg: Config) -> None:
        out = cfg.outbound[0]
        if self._dnsmasq_pid(out):
            return
        iface = ipaddress.ip_interface(cfg.router_address)
        hosts = [h for h in iface.network.hosts() if h != iface.ip]
        first, last = hosts[min(99, len(hosts) // 2)], hosts[min(198, len(hosts) - 1)]
        self._run([
            "dnsmasq", "--conf-file=/dev/null", f"--interface={out}", "--bind-interfaces",
            "--except-interface=lo", f"--listen-address={iface.ip}",
            f"--dhcp-range={first},{last},{iface.network.netmask},12h",
            f"--dhcp-option=option:router,{iface.ip}",
            f"--dhcp-option=option:dns-server,{iface.ip}",
            f"--dhcp-leasefile={self._state(f'dnsmasq-{out}.leases')}",
            f"--pid-file={self._state(f'dnsmasq-{out}.pid')}",
            "--user=root",
        ])

    def _dnsmasq_pid(self, out: str) -> int | None:
        try:
            with open(self._state(f"dnsmasq-{out}.pid"), encoding="utf-8") as f:
                pid = int(f.read().strip())
            with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
                return pid if f.read().strip() == "dnsmasq" else None
        except (OSError, ValueError):
            return None

    def _dhcp_down(self, out: str) -> None:
        pid = self._dnsmasq_pid(out)
        if pid:
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                if not os.path.exists(f"/proc/{pid}"):
                    break
                time.sleep(0.05)
        for name in (f"dnsmasq-{out}.pid", f"dnsmasq-{out}.leases"):
            try:
                os.remove(self._state(name))
            except OSError:
                pass


__all__ = ["Modes", "ModeRefused", "CommandFailed"]
