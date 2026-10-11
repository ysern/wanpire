"""The line's roles while the server runs: which adapter is inbound and which outbound, and the
access point of each Wi-Fi one. Changing them takes the mode down, writes the configuration
and sets the mode up again; if that fails, the old roles are put back.

The control adapter and the mode are not changed here: the control adapter carries the very
session that would change it.
"""

from __future__ import annotations

import threading

from .config import Config, InvalidConfig, config_from_dict, save_config


class Roles:
    def __init__(self, config: Config, list_adapters, modes=None, path: str | None = None,
                 save=save_config):
        self.config = config
        self.list_adapters = list_adapters
        self.modes = modes
        self.path = path
        self._save = save
        self._lock = threading.Lock()

    def offered(self, adapters=None) -> list[str]:
        """The adapters that may be picked for inbound and outbound: every one but virtual
        ones and the control adapter when it is Wi-Fi."""
        adapters = adapters if adapters is not None else self.list_adapters()
        return [a.name for a in adapters
                if a.kind != "virtual"
                and not (a.name == self.config.control and a.kind == "wifi")]

    def view(self) -> dict:
        adapters = self.list_adapters()
        offered = set(self.offered(adapters))
        c = self.config
        return {
            "mode": c.mode, "control": c.control, "inbound": c.inbound,
            "outbound": c.outbound[0],
            "access_points": {n: c.access_point(n) for n in (c.inbound, c.outbound[0])
                              if c.access_point(n)},
            "country": c.country,
            "offered": [{"name": a.name, "kind": a.kind, "can_be_ap": a.can_be_ap}
                        for a in adapters if a.name in offered],
        }

    def change(self, inbound: str, outbound: str, access_points: dict | None) -> Config:
        """Validate the new roles, then set the mode up again with them."""
        if not inbound or not outbound:
            raise InvalidConfig("the roles need an inbound and an outbound adapter")
        if inbound == outbound:
            raise InvalidConfig(f"inbound and outbound must be different adapters, not both "
                                f"{inbound}")
        adapters = {a.name: a for a in self.list_adapters()}
        offered = self.offered(list(adapters.values()))
        for role, name in (("inbound", inbound), ("outbound", outbound)):
            if name not in offered:
                raise InvalidConfig(f"{name} cannot be the {role} adapter; the adapters that "
                                    f"can: {', '.join(offered)}")
        with self._lock:
            old = self.config
            doc = old.to_dict()
            doc["adapters"] = {"control": old.control, "inbound": inbound,
                               "outbound": [outbound]}
            aps = dict(doc.get("access_points") or {})
            for name, ap in (access_points or {}).items():
                if name in (inbound, outbound):
                    aps[name] = {"ssid": (ap or {}).get("ssid"),
                                 "passphrase": (ap or {}).get("passphrase")}
            doc["access_points"] = aps
            new = config_from_dict(doc, adapters)
            if self.modes is None or self.path is None:
                raise RuntimeError("the roles cannot be changed here: no mode or file to set")
            self.modes.down(old)
            self._save(new, self.path)
            try:
                self.modes.up(new)
            except Exception:
                self.modes.down(new)
                self._save(old, self.path)
                self.modes.up(old)
                raise
            self.config = new
            return new
