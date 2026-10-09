"""What ships with wanpire: the endpoint presets, the path table and the fitted formula.

They live inside the package (``wanpire/data``) so an installed wanpire finds them. An end is
named ``<endpoint>`` or ``<endpoint>:<channel>``; ``<endpoint>`` is a shipped preset's id or
the path to a preset file of one's own.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path

from .model import Link
from .presets import (
    Channel,
    Endpoint,
    Formula,
    InvalidPreset,
    PathTable,
    combine,
    endpoint_from_dict,
    path_between,
)


def _data(*parts: str):
    return resources.files("wanpire").joinpath("data", *parts)


def _json(*parts: str) -> dict:
    return json.loads(_data(*parts).read_text(encoding="utf-8"))


def endpoint_ids() -> list[str]:
    return sorted(p.name[:-5] for p in _data("endpoints").iterdir() if p.name.endswith(".json"))


def endpoint_schema() -> dict:
    return _json("schema", "endpoint.schema.json")


def endpoint_document(eid: str) -> dict:
    if eid not in endpoint_ids():
        raise InvalidPreset(
            f"no endpoint {eid!r}; shipped: {', '.join(endpoint_ids())} (or give a file's path)"
        )
    return _json("endpoints", f"{eid}.json")


@cache
def endpoint(eid: str) -> Endpoint:
    return endpoint_from_dict(endpoint_document(eid))


@cache
def path_table() -> PathTable:
    return PathTable.from_dict(_json("paths", "backbone-rtt.json"))


@cache
def formula() -> Formula:
    return Formula.from_dict(_json("paths", "route-factors.json"))


def load_endpoint(ref: str) -> Endpoint:
    """A shipped id, or a path to a preset file."""
    if ref in endpoint_ids():
        return endpoint(ref)
    p = Path(ref)
    if p.suffix == ".json" or p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except OSError as e:
            raise InvalidPreset(f"cannot read {ref}: {e.strerror}") from None
        except json.JSONDecodeError as e:
            raise InvalidPreset(f"{ref} is not valid JSON: {e}") from None
        return endpoint_from_dict(data)
    return endpoint(ref)  # raises, listing the shipped ones


def resolve(end: str) -> tuple[Endpoint, Channel]:
    """``london``, ``london:mobile-4g`` or ``./my-office.json:cable``."""
    ref, channel = end, None
    head, sep, tail = end.rpartition(":")
    # A channel id never contains a path separator or a dot; a Windows drive letter is no channel.
    if sep and head and not any(c in tail for c in "/\\.") and len(head) > 1:
        ref, channel = head, tail
    e = load_endpoint(ref)
    return e, e.channel(channel)


def path(near: str, far: str):
    (a, _), (b, _) = resolve(near), resolve(far)
    return path_between(a, b, path_table(), formula())


def preview(near: str, far: str) -> tuple[Link, dict]:
    """The link from ``near`` (the device under test's end) to ``far``, and how it was found."""
    (a, ca), (b, cb) = resolve(near), resolve(far)
    p = path_between(a, b, path_table(), formula())
    link = combine(ca, cb, p.rtt_ms)
    account = {
        "near": {"endpoint": a.id, "channel": ca.id},
        "far": {"endpoint": b.id, "channel": cb.id},
        "path": {"rtt_ms": round(p.rtt_ms, 1), "origin": p.origin, "detail": p.detail},
        "channels": {
            "near": {"kind": ca.kind, "down": ca.down.to_dict(), "up": ca.up.to_dict()},
            "far": {"kind": cb.kind, "down": cb.down.to_dict(), "up": cb.up.to_dict()},
        },
        "rule": "down = path/2 + far up + near down; up = path/2 + near up + far down; "
                "jitters in quadrature; losses compound; rate is the narrower end",
    }
    if p.origin == "table":
        account["path"]["attribution"] = path_table().source.get("attribution")
    return link, account
