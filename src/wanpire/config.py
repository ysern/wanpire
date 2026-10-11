"""wanpire's main configuration: the mode, and which adapter has which role. No I/O here
except ``load_config``.

    {
      "schema": "wanpire-config/1",
      "mode": "bridge",
      "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]},
      "router": {"address": "10.77.0.1/24"},
      "access_points": {"wlan1": {"ssid": "<wifi-ssid>", "passphrase": "<wifi-password>"}},
      "wifi": {"country": "GB"}
    }

Roles: *control* is where the web UI, the REST API and the MCP listen, and is never impaired;
*inbound* faces the wider network; *outbound* faces the device under test and carries every
impairment, so it shares its adapter with nothing.

A Wi-Fi adapter in the inbound or the outbound role is an access point: it needs its network
name and password in ``access_points`` and the regulatory country in ``wifi``. Both keys are
optional otherwise, so a wired configuration reads as it always did.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import tempfile
from dataclasses import dataclass, field

SCHEMA = "wanpire-config/1"
DEFAULT_PATH = "/etc/wanpire/wanpire.json"
MODES = ("bridge", "router")
DEFAULT_ROUTER_ADDRESS = "10.77.0.1/24"
WIRED = ("ethernet", "usb-ethernet")
SSID_RULE = "a network name has 1 to 32 bytes in UTF-8"
PASSPHRASE_RULE = "a password has 8 to 63 printable ASCII characters"
_COUNTRY = re.compile(r"[A-Z]{2}")


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
    access_points: dict = field(default_factory=dict)  # adapter -> {"ssid", "passphrase"}
    country: str | None = None
    wifi_roles: tuple[str, ...] = ()  # the adapters in a line role that are Wi-Fi, when known

    def role(self, adapter: str) -> str | None:
        roles = [r for r, names in (("control", (self.control,)), ("inbound", (self.inbound,)),
                                    ("outbound", self.outbound)) if adapter in names]
        return "+".join(roles) or None

    @property
    def router_network(self) -> ipaddress.IPv4Network:
        return ipaddress.ip_interface(self.router_address).network

    @property
    def access_point_adapters(self) -> tuple[str, ...]:
        """The adapters in a line role that run an access point."""
        return tuple(n for n in (self.inbound, *self.outbound) if n in self.wifi_roles)

    def access_point(self, adapter: str) -> dict | None:
        ap = self.access_points.get(adapter)
        return dict(ap) if ap else None

    def to_dict(self) -> dict:
        d = {"schema": SCHEMA, "mode": self.mode,
             "adapters": {"control": self.control, "inbound": self.inbound,
                          "outbound": list(self.outbound)},
             "router": {"address": self.router_address}}
        if self.access_points:
            d["access_points"] = {k: dict(v) for k, v in self.access_points.items()}
        if self.country:
            d["wifi"] = {"country": self.country}
        return d


def check_ssid(ssid) -> str:
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode("utf-8")) <= 32:
        raise InvalidConfig(f"{SSID_RULE}, not {ssid!r}")
    return ssid


def check_passphrase(passphrase) -> str:
    if (not isinstance(passphrase, str) or not 8 <= len(passphrase) <= 63
            or any(not 32 <= ord(ch) <= 126 for ch in passphrase)):
        raise InvalidConfig(f"{PASSPHRASE_RULE} (WPA2/WPA3-Personal)")
    return passphrase


def _access_points(data: dict) -> dict:
    raw = data.get("access_points") or {}
    if not isinstance(raw, dict):
        raise InvalidConfig("access_points must map an adapter to its ssid and passphrase")
    out = {}
    for name, ap in raw.items():
        if not isinstance(ap, dict):
            raise InvalidConfig(f"access_points.{name} must hold an ssid and a passphrase")
        try:
            out[name] = {"ssid": check_ssid(ap.get("ssid")),
                         "passphrase": check_passphrase(ap.get("passphrase"))}
        except InvalidConfig as e:
            raise InvalidConfig(f"access point {name}: {e}") from None
    return out


def _country(data: dict) -> str | None:
    wifi = data.get("wifi")
    country = wifi.get("country") if isinstance(wifi, dict) else None
    if country is None:
        return None
    if not isinstance(country, str) or not _COUNTRY.fullmatch(country) or country == "00":
        raise InvalidConfig(f"wifi.country {country!r} is not a regulatory country: two capital "
                            "letters, an ISO 3166-1 code such as GB or US")
    return country


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
    aps = _access_points(data)
    country = _country(data)
    if control in aps:
        raise InvalidConfig(f"{control} is the control adapter, which is never an access point: "
                            "its own configuration is left alone")
    wifi_roles: tuple[str, ...] = ()

    if adapters is not None:
        for role, name in (("control", control), ("inbound", inbound), ("outbound", out)):
            if name not in adapters:
                raise InvalidConfig(
                    f"{role} adapter {name} does not exist; this box has: "
                    f"{', '.join(sorted(adapters))}"
                )
        wifi_roles = tuple(n for n in (inbound, out) if adapters[n].kind == "wifi")
        for name in wifi_roles:
            if not adapters[name].can_be_ap:
                raise InvalidConfig(
                    f"{name} cannot be an access point: its radio does not support AP mode, and "
                    "a Wi-Fi adapter in a line role is always one"
                )
        if mode == "router" and inbound in wifi_roles:
            raise InvalidConfig(
                f"{inbound} is Wi-Fi: a Wi-Fi inbound adapter is an access point and works in "
                "bridge mode only (in router mode inbound is a client of the wider network)"
            )
        for name in wifi_roles:
            if name not in aps:
                raise InvalidConfig(
                    f"{name} needs a network name and a password: a Wi-Fi adapter in a line "
                    "role is an access point (access_points)"
                )
        if wifi_roles and not country:
            raise InvalidConfig(
                "an access point needs the regulatory country: wifi.country, e.g. GB or US"
            )
        if mode == "bridge":
            for name in (inbound, out):
                if adapters[name].kind not in WIRED and name not in wifi_roles:
                    raise InvalidConfig(f"{name} is {adapters[name].kind}, not a wired port")
    if mode == "bridge" and control in (inbound, out):
        raise InvalidConfig(
            f"control cannot be a bridge port in bridge mode ({control} is inbound): its address "
            "would stop working once the port joins the bridge; use another adapter for control, "
            "or router mode"
        )
    return Config(mode=mode, control=control, inbound=inbound, outbound=(out,),
                  router_address=address, access_points=aps, country=country,
                  wifi_roles=wifi_roles)


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


def save_config(cfg: Config, path: str = DEFAULT_PATH) -> None:
    """Write ``cfg`` to ``path`` in one step (a file beside it, renamed over it), readable and
    writable by its owner only: it holds the access points' passwords."""
    fd, tmp = tempfile.mkstemp(prefix=".wanpire-", suffix=".json",
                               dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, indent=1, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
