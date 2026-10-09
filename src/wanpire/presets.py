"""Endpoint presets, the path between two ends, and combining them into a Link. No I/O here.

A link is described by its two ends. Each end is an *endpoint preset* (a place and its access
*channels*); the *path* between the two places comes from, in order:

1. a measured path one end's preset gives for the other;
2. the shipped path table, when each end lies near a table site (the table's figure between
   those sites, corrected by the formula's difference between the ends and the sites);
3. the formula: ``2 × great-circle km × route factor / 200 km per ms + router term``.

Then each end's channel adds its access delay and jitter, losses compound, and the bandwidth
each way is the narrower end's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .model import Direction, InvalidLink, Link

SCHEMA = "wanpire-endpoint/1"
KINDS = (
    "generic", "media-private-network", "enterprise-fibre", "business-fibre",
    "consumer-fibre", "cable", "dsl", "fixed-wireless", "mobile-4g", "mobile-5g",
    "satellite-leo", "satellite-geo",
)
REGIONS = (
    "north-america", "south-america", "europe", "middle-east", "africa", "south-asia",
    "southeast-asia", "east-asia", "oceania",
)
CHANNEL_SETTINGS = ("delay_ms", "jitter_ms", "loss_pct", "burst_loss_pct", "burst_length",
                    "rate_mbit")
FIBRE_KM_PER_MS = 200
EARTH_RADIUS_KM = 6371.0088
ANCHOR_KM = 1000


class InvalidPreset(ValueError):
    """An endpoint preset that cannot be used, with the reason."""


# -- presets ------------------------------------------------------------------------------

@dataclass(frozen=True)
class Channel:
    id: str
    kind: str
    description: str
    down: Direction
    up: Direction
    sources: tuple = ()


@dataclass(frozen=True)
class Endpoint:
    id: str
    name: str
    lat: float
    lon: float
    country: str
    region: str
    default_channel: str
    channels: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)  # other end's id -> measured rtt_ms

    def channel(self, name: str | None) -> Channel:
        """The named channel, or the default one."""
        name = name or self.default_channel
        if name not in self.channels:
            raise InvalidPreset(
                f"{self.id} has no channel {name!r}; it has: {', '.join(self.channels)}"
            )
        return self.channels[name]


def endpoint_from_dict(data: dict) -> Endpoint:
    """Validate a preset document and build an Endpoint, or say what is wrong."""
    pid = data.get("id", "<no id>")
    if data.get("schema") != SCHEMA:
        raise InvalidPreset(f"{pid}: 'schema' must be {SCHEMA!r}, not {data.get('schema')!r}")
    for key in ("id", "name", "location", "default_channel", "channels"):
        if key not in data:
            raise InvalidPreset(f"{pid}: missing {key!r}")
    loc = data["location"]
    try:
        lat, lon = float(loc["lat"]), float(loc["lon"])
    except (KeyError, TypeError, ValueError):
        raise InvalidPreset(f"{pid}: location needs numeric 'lat' and 'lon'") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise InvalidPreset(f"{pid}: location ({lat}, {lon}) is not on Earth")
    region = loc.get("region")
    if region not in REGIONS:
        raise InvalidPreset(
            f"{pid}: location.region must be one of {', '.join(REGIONS)}, not {region!r}"
        )
    raw = data["channels"]
    if not raw:
        raise InvalidPreset(f"{pid}: a preset needs at least one channel")
    channels = {cid: _channel(pid, cid, c) for cid, c in raw.items()}
    if not any(c.kind == "generic" for c in channels.values()):
        raise InvalidPreset(f"{pid}: every preset has a 'generic' channel; this one has none")
    if data["default_channel"] not in channels:
        raise InvalidPreset(
            f"{pid}: default_channel {data['default_channel']!r} is not one of its channels "
            f"({', '.join(channels)})"
        )
    paths = {}
    for other, p in (data.get("paths") or {}).items():
        try:
            rtt = float(p["rtt_ms"])
        except (KeyError, TypeError, ValueError):
            raise InvalidPreset(f"{pid}: paths.{other} needs a numeric 'rtt_ms'") from None
        if not 0 < rtt <= 2000:
            raise InvalidPreset(f"{pid}: paths.{other}.rtt_ms must be in (0, 2000], not {rtt}")
        if not p.get("source"):
            raise InvalidPreset(f"{pid}: paths.{other} must name its source")
        paths[other] = rtt
    return Endpoint(id=data["id"], name=data["name"], lat=lat, lon=lon,
                    country=loc.get("country", ""), region=region,
                    default_channel=data["default_channel"], channels=channels, paths=paths)


def _channel(pid: str, cid: str, c: dict) -> Channel:
    where = f"{pid}, channel {cid}"
    if c.get("kind") not in KINDS:
        raise InvalidPreset(
            f"{where}: kind must be one of {', '.join(KINDS)}, not {c.get('kind')!r}"
        )
    if not c.get("sources"):
        raise InvalidPreset(f"{where}: every channel names at least one source")
    dirs = {}
    for d in ("down", "up"):
        figures = c.get(d) or {}
        extra = sorted(set(figures) - set(CHANNEL_SETTINGS))
        if extra:
            raise InvalidPreset(
                f"{where}, {d}: a channel carries only {', '.join(CHANNEL_SETTINGS)}; "
                f"not {', '.join(extra)}"
            )
        try:
            dirs[d] = Direction(**figures)
        except InvalidLink as e:
            raise InvalidPreset(f"{where}, {d}: {e}") from None
    return Channel(id=cid, kind=c["kind"], description=c.get("description", ""),
                   down=dirs["down"], up=dirs["up"], sources=tuple(c["sources"]))


# -- the formula --------------------------------------------------------------------------

def great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def region_pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


@dataclass(frozen=True)
class Formula:
    """``rtt = 2 × km × factor / 200 + router_ms``, the factor fitted per region pair."""

    router_ms: float
    global_factor: float
    factors: dict = field(default_factory=dict)  # sorted (region, region) -> factor

    def factor(self, region_a: str, region_b: str) -> tuple[float, str]:
        key = region_pair(region_a, region_b)
        if key in self.factors:
            return self.factors[key], f"route factor {self.factors[key]:.3g} ({key[0]}/{key[1]})"
        return self.global_factor, f"route factor {self.global_factor:.3g} (global; no fit for " \
                                   f"{key[0]}/{key[1]})"

    def rtt(self, lat1, lon1, region1, lat2, lon2, region2) -> tuple[float, str]:
        km = great_circle_km(lat1, lon1, lat2, lon2)
        f, how = self.factor(region1, region2)
        return 2 * km * f / FIBRE_KM_PER_MS + self.router_ms, \
            f"{km:.0f} km great circle, {how}, router term {self.router_ms:g} ms"

    @classmethod
    def from_dict(cls, data: dict) -> Formula:
        factors = {region_pair(*k.split("/")): float(v["factor"])
                   for k, v in data.get("factors", {}).items()}
        return cls(router_ms=float(data["router_ms"]),
                   global_factor=float(data["global_factor"]), factors=factors)


# -- the path -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PathTable:
    sites: dict  # id -> {lat, lon, region, metro}
    rtt: dict  # source id -> destination id -> ms (directional)
    source: dict = field(default_factory=dict)

    def mean_rtt(self, a: str, b: str) -> float | None:
        x = [v for v in (self.rtt.get(a, {}).get(b), self.rtt.get(b, {}).get(a)) if v]
        return sum(x) / len(x) if x else None

    def nearest(self, lat: float, lon: float) -> tuple[str, float]:
        return min(((sid, great_circle_km(lat, lon, s["lat"], s["lon"]))
                    for sid, s in self.sites.items()), key=lambda t: t[1])

    @classmethod
    def from_dict(cls, data: dict) -> PathTable:
        return cls(sites=data["sites"], rtt=data["rtt_ms"], source=data.get("source", {}))


@dataclass(frozen=True)
class Path:
    rtt_ms: float
    origin: str  # "preset", "table" or "formula"
    detail: str


def path_between(near: Endpoint, far: Endpoint, table: PathTable | None,
                 formula: Formula, anchor_km: float = ANCHOR_KM) -> Path:
    if far.id in near.paths:
        return Path(near.paths[far.id], "preset", f"measured, given by {near.id}'s preset")
    if near.id in far.paths:
        return Path(far.paths[near.id], "preset", f"measured, given by {far.id}'s preset")
    direct, how = formula.rtt(near.lat, near.lon, near.region, far.lat, far.lon, far.region)
    if table and table.sites:
        (sa, ka), (sb, kb) = table.nearest(near.lat, near.lon), table.nearest(far.lat, far.lon)
        measured = table.mean_rtt(sa, sb) if sa != sb else None
        if ka <= anchor_km and kb <= anchor_km and measured:
            a, b = table.sites[sa], table.sites[sb]
            between_sites, _ = formula.rtt(a["lat"], a["lon"], a["region"],
                                           b["lat"], b["lon"], b["region"])
            correction = direct - between_sites
            rtt = max(measured + correction, 1.0)
            return Path(rtt, "table",
                        f"table {sa} ({a.get('metro', '')}) to {sb} ({b.get('metro', '')}): "
                        f"{measured:g} ms, mean of both directions; {ka:.0f} km and {kb:.0f} km "
                        f"from the ends, corrected by {correction:+.1f} ms")
    return Path(direct, "formula", how)


# -- combining ----------------------------------------------------------------------------

def _loss(d: Direction) -> float:
    return (d.loss_pct or d.burst_loss_pct) / 100


def _one_way(sender_up: Direction, receiver_down: Direction, half_path_ms: float) -> Direction:
    sides = (sender_up, receiver_down)
    lost = 1 - math.prod(1 - _loss(d) for d in sides)
    bursts = [d.burst_length for d in sides if d.burst_loss_pct]
    rates = [d.rate_mbit for d in sides if d.rate_mbit is not None]
    loss_pct = round(lost * 100, 3)
    return Direction(
        delay_ms=round(half_path_ms + sum(d.delay_ms for d in sides), 1),
        jitter_ms=round(math.sqrt(sum(d.jitter_ms ** 2 for d in sides)), 1),
        loss_pct=0 if bursts else loss_pct,
        burst_loss_pct=loss_pct if bursts else 0,
        burst_length=max(bursts) if bursts else 0,
        rate_mbit=min(rates) if rates else None,
    )


def combine(near: Channel, far: Channel, path_rtt_ms: float) -> Link:
    """The link through the box: *down* is the far end sending to the near end."""
    half = path_rtt_ms / 2
    return Link(down=_one_way(far.up, near.down, half), up=_one_way(near.up, far.down, half))
