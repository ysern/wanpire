"""The line's roles while the server runs: which adapter is inbound and which outbound, the
network a Wi-Fi inbound one joins and the access point a Wi-Fi outbound one runs. Changing them takes the mode down, writes the configuration
and sets the mode up again; if that fails, the old roles are put back.

The line's state lives here too. A line adapter that is not plugged in (a USB stick) is a
state of the line, not a failure of the box: the server starts with the line **down**, says
which adapter is missing, and ``watch`` (called on the server's tick) sets the mode up as soon
as the adapter appears. Changing the roles while the line is down is the way out when the
adapter is gone for good.

The control adapter and the mode are not changed here: the control adapter carries the very
session that would change it.
"""

from __future__ import annotations

import logging
import threading

from .config import Config, InvalidConfig, config_from_dict, save_config

log = logging.getLogger(__name__)


class Roles:
    def __init__(self, config: Config, list_adapters, modes=None, path: str | None = None,
                 save=save_config, missing: tuple[str, ...] = ()):
        """``missing``: the line adapters the box lacked when the server started (the line is
        down until they appear); none, and the line is up, as ``wanpire up`` left it."""
        self.config = config
        self.list_adapters = list_adapters
        self.modes = modes
        self.path = path
        self._save = save
        self._lock = threading.Lock()
        self.missing = tuple(missing)
        self.line_up = not self.missing
        self._refusal: str | None = None  # why the last set-up was refused, while down

    # -- the line's state -------------------------------------------------------------------

    def line_view(self) -> dict:
        """``{"up": true}``, or ``{"up": false, "missing": [...], "reason": "..."}``."""
        if self.line_up:
            return {"up": True}
        reason = self._refusal or self.config.missing_reason(self.missing)
        return {"up": False, "missing": list(self.missing), "reason": reason}

    def watch(self) -> None:
        """While the line is down, set the mode up once its adapters exist (the server's
        tick). A refused set-up is logged once per reason, shown in the status, and tried
        again at the next tick. A no-op without modes (a test bed) or with the line up."""
        if self.line_up or self.modes is None:
            return
        with self._lock:
            if self.line_up:
                return
            adapters = {a.name: a for a in self.list_adapters()}
            missing = self.config.missing(adapters)
            if missing:
                self.missing, self._refusal = missing, None
                return
            try:
                # the adapters are here: now the configuration can be checked against them
                # (a Wi-Fi outbound adapter is an access point, which needs its settings)
                cfg = config_from_dict(self.config.to_dict(), adapters)
                self.modes.up(cfg)
            except Exception as e:  # ModeRefused, InvalidConfig, a failed command
                if str(e) != self._refusal:
                    log.warning("the line stays down: %s", e)
                self.missing, self._refusal = (), str(e)
                return
            self.config = cfg
            self._line_is_up()
            log.info("the line is up: inbound %s, outbound %s", cfg.inbound, cfg.outbound[0])

    def _line_is_up(self) -> None:
        self.line_up, self.missing, self._refusal = True, (), None

    # -- the roles ----------------------------------------------------------------------------

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
            "access_points": {n: c.access_point(n) for n in c.access_point_adapters},
            "wifi_clients": ({c.client_adapter: c.wifi_client(c.client_adapter)}
                             if c.client_adapter else {}),
            "country": c.country,
            "offered": [{"name": a.name, "kind": a.kind, "can_be_ap": a.can_be_ap}
                        for a in adapters if a.name in offered],
            "missing": list(c.missing(a.name for a in adapters)),
        }

    def change(self, inbound: str, outbound: str, access_points: dict | None,
               wifi_clients: dict | None = None) -> Config:
        """Validate the new roles, then set the mode up again with them. An access point is
        taken for the outbound adapter only, a network to join for the inbound one only.
        Allowed while the line is down: a change to present adapters brings it up."""
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
            for key, given, side in (("access_points", access_points, outbound),
                                     ("wifi_clients", wifi_clients, inbound)):
                kept = dict(doc.get(key) or {})
                net = (given or {}).get(side)
                if net is not None:
                    net = net if isinstance(net, dict) else {}
                    kept[side] = {"ssid": net.get("ssid"), "passphrase": net.get("passphrase")}
                doc[key] = kept
            new = config_from_dict(doc, adapters)
            if self.modes is None or self.path is None:
                raise RuntimeError("the roles cannot be changed here: no mode or file to set")
            self.modes.down(old)  # tolerant of a missing adapter: removes whatever is there
            self._save(new, self.path)
            try:
                self.modes.up(new)
            except Exception:
                self.modes.down(new)
                self._save(old, self.path)
                old_missing = old.missing(adapters)
                if old_missing:  # the old roles cannot come up either: the line stays down
                    self.line_up, self.missing, self._refusal = False, old_missing, None
                else:
                    self.modes.up(old)
                raise
            self.config = new
            self._line_is_up()
            return new
