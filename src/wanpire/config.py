"""wanpire's main configuration: the mode, and which adapter has which role. No I/O here
except ``load_config``.

    {
      "schema": "wanpire-config/1",
      "mode": "bridge",
      "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]},
      "router": {"address": "10.77.0.1/24"}
    }

Roles: *control* is where the web UI, the REST API and the MCP listen, and is never impaired;
*inbound* faces the wider network; *outbound* faces the device under test and carries every
impairment, so it shares its adapter with nothing.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass

SCHEMA = "wanpire-config/1"
DEFAULT_PATH = "/etc/wanpire/wanpire.json"
MODES = ("bridge", "router")
DEFAULT_ROUTER_ADDRESS = "10.77.0.1/24"
WIRED = ("ethernet", "usb-ethernet")


class InvalidConfig(ValueError):
    """A configuration that cannot be used, with the reason."""


@dataclass(frozen=True)
class Config:
    mode: str
    control: str
    inbound: str
    outbound: tuple[str, ...]
    router_address: str = DEFAULT_ROUTER_ADDRESS
    bridge_name: str = "wpbr0"

    def role(self, adapter: str) -> str | None:
        roles = [r for r, names in (("control", (self.control,)), ("inbound", (self.inbound,)),
                                    ("outbound", self.outbound)) if adapter in names]
        return "+".join(roles) or None

    @property
    def router_network(self) -> ipaddress.IPv4Network:
        return ipaddress.ip_interface(self.router_address).network


def config_from_dict(data: dict, adapters: dict | None = None) -> Config:
    """Validate a configuration document. With ``adapters`` (name -> Adapter), also check it
    against the adapters the box has."""
    if data.get("schema") != SCHEMA:
        raise InvalidConfig(f"'schema' must be {SCHEMA!r}, not {data.get('schema')!r}")
    mode = data.get("mode")
    if mode not in MODES:
        raise InvalidConfig(f"mode must be one of {', '.join(MODES)}, not {mode!r}")
    a = data.get("adapters") or {}
    control, inbound, outbound = a.get("control"), a.get("inbound"), a.get("outbound")
    if not control or not inbound:
        raise InvalidConfig("adapters needs a 'control' and an 'inbound' adapter")
    if not isinstance(outbound, list) or not outbound:
        raise InvalidConfig("adapters.outbound must be a list of one adapter")
    if len(outbound) != 1:
        raise InvalidConfig(
            f"one outbound adapter is supported for now, not {len(outbound)} ({', '.join(outbound)})"
        )
    out = outbound[0]
    if out in (control, inbound):
        shared = "control" if out == control else "inbound"
        raise InvalidConfig(
            f"{out} is both outbound and {shared}: outbound shares its adapter with nothing, "
            "because every impairment lives on it"
        )
    router = data.get("router") or {}
    address = router.get("address", DEFAULT_ROUTER_ADDRESS)
    _check_router_address(address)

    if adapters is not None:
        for role, name in (("control", control), ("inbound", inbound), ("outbound", out)):
            if name not in adapters:
                raise InvalidConfig(
                    f"{role} adapter {name} does not exist; this box has: "
                    f"{', '.join(sorted(adapters))}"
                )
        if adapters[out].kind == "wifi":
            raise InvalidConfig(
                f"{out} is Wi-Fi: outbound as an access point is not built yet"
            )
        if mode == "bridge":
            for name in (inbound, out):
                if adapters[name].kind == "wifi":
                    raise InvalidConfig(
                        f"{name} is Wi-Fi: a Wi-Fi client cannot be a bridge port (the access "
                        "point accepts only frames from the address that joined it); use "
                        "router mode"
                    )
                if adapters[name].kind not in WIRED:
                    raise InvalidConfig(f"{name} is {adapters[name].kind}, not a wired port")
    if mode == "bridge" and control in (inbound, out):
        raise InvalidConfig(
            f"control cannot be a bridge port in bridge mode ({control} is inbound): its address "
            "would stop working once the port joins the bridge; use another adapter for control, "
            "or router mode"
        )
    return Config(mode=mode, control=control, inbound=inbound, outbound=(out,),
                  router_address=address)


def _check_router_address(address: str) -> None:
    try:
        iface = ipaddress.ip_interface(address)
    except ValueError:
        raise InvalidConfig(f"router.address {address!r} is not an address with a prefix, "
                            "e.g. 10.77.0.1/24") from None
    if iface.version != 4 or not iface.network.is_private:
        raise InvalidConfig(f"router.address {address} must be a private IPv4 network")
    if iface.ip in (iface.network.network_address, iface.network.broadcast_address):
        raise InvalidConfig(f"router.address {address} must be a host address, not the "
                            "network's or its broadcast")
    if iface.network.prefixlen > 29:
        raise InvalidConfig(f"router.address {address}: the network is too small for DHCP")


def load_config(path: str = DEFAULT_PATH, adapters: dict | None = None) -> Config:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise InvalidConfig(f"cannot read {path}: {e.strerror}") from None
    except json.JSONDecodeError as e:
        raise InvalidConfig(f"{path} is not valid JSON: {e}") from None
    return config_from_dict(data, adapters)
