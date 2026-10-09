"""wanpire's command line: apply, show, renew and clear a link on an adapter.

    wanpire endpoints
    wanpire preview london:consumer-fibre los-angeles:mobile-4g
    wanpire apply --adapter eth1 london:consumer-fibre los-angeles:mobile-4g
    wanpire apply --adapter eth1 --down delay_ms=150,jitter_ms=5 --up delay_ms=150,loss_pct=1
    wanpire apply --adapter eth1 --file link.json --lifetime 600
    wanpire show  --adapter eth1
    wanpire renew --adapter eth1 --lifetime 120
    wanpire clear --adapter eth1
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields

from . import catalogue
from .engine import DEFAULT_LIFETIME_S, CommandFailed, Engine, RefusedAdapter
from .model import Direction, InvalidLink, Link
from .presets import InvalidPreset

_TEXT = {"distribution"}


def make_engine(netns: str | None = None, control=()) -> Engine:
    return Engine(netns=netns, control_adapters=control)


def _settings(text: str) -> dict:
    known = {f.name for f in fields(Direction)}
    out = {}
    for pair in filter(None, text.split(",")):
        key, _, value = pair.partition("=")
        key = key.strip()
        if key not in known:
            raise InvalidLink(f"unknown setting {key!r}; known: {', '.join(sorted(known))}")
        out[key] = value.strip() if key in _TEXT else float(value)
    return out


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wanpire", description="Make a line behave like a long link.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("endpoints", help="list the shipped endpoints and their channels")
    pv = sub.add_parser("preview", help="work out the link between two ends; changes nothing")
    pv.add_argument("near", help="the device under test's end: <endpoint>[:<channel>]")
    pv.add_argument("far", help="the other end: <endpoint>[:<channel>]")
    pv.add_argument("--json", action="store_true", help="print JSON")
    for name in ("apply", "show", "renew", "clear"):
        s = sub.add_parser(name)
        s.add_argument("--adapter", required=True, help="the outbound adapter")
        s.add_argument("--netns", help="the network namespace the adapter lives in")
        s.add_argument("--control", action="append", default=[],
                       help="an adapter that must never be impaired (repeatable)")
        if name in ("apply", "renew"):
            s.add_argument("--lifetime", type=float, default=DEFAULT_LIFETIME_S,
                           help="seconds until the link is cleared unless renewed (0: never)")
        if name == "apply":
            s.add_argument("--down", default="", help="settings towards the device, k=v,...")
            s.add_argument("--up", default="", help="settings away from the device, k=v,...")
            s.add_argument("--file", help="a JSON link: {\"down\": {...}, \"up\": {...}}")
            s.add_argument("ends", nargs="*", metavar="END",
                           help="two ends instead of figures: <near>[:<channel>] <far>[:<channel>]")
    return p


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        if a.command == "endpoints":
            _print_endpoints()
            return 0
        if a.command == "preview":
            link, account = catalogue.preview(a.near, a.far)
            if a.json:
                print(json.dumps({"link": link.to_dict(), "account": account}, indent=2))
            else:
                print(_explain(link, account))
            return 0
        if a.command == "apply":
            link = _link_to_apply(a)
        engine = make_engine(netns=a.netns, control=a.control)
        if a.command == "apply":
            engine.apply(a.adapter, link, lifetime_s=a.lifetime or None)
        elif a.command == "renew":
            engine.renew(a.adapter, lifetime_s=a.lifetime)
        elif a.command == "clear":
            engine.clear(a.adapter)
        elif a.command == "show":
            print(json.dumps(engine.read(a.adapter), indent=2))
    except (InvalidLink, InvalidPreset, RefusedAdapter, ValueError) as e:
        print(f"wanpire: {e}", file=sys.stderr)
        return 2
    except CommandFailed as e:
        print(f"wanpire: {e}", file=sys.stderr)
        return 1
    return 0


def _link_to_apply(a) -> Link:
    if a.ends:
        if a.file or a.down or a.up:
            raise ValueError("give either two ends or figures (--down/--up/--file), not both")
        if len(a.ends) != 2:
            raise ValueError(f"a link has two ends, near and far; got {len(a.ends)}")
        link, _ = catalogue.preview(*a.ends)
        return link
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            return Link.from_dict(json.load(f))
    return Link(down=Direction(**_settings(a.down)), up=Direction(**_settings(a.up)))


def _print_endpoints() -> None:
    for eid in catalogue.endpoint_ids():
        e = catalogue.endpoint(eid)
        print(f"{eid:<14} {e.name} ({e.country}, {e.region})")
        for cid, c in e.channels.items():
            mark = "*" if cid == e.default_channel else " "
            print(f"  {mark} {cid:<22} {c.description}")


def _figures(d: Direction) -> str:
    parts = [f"{d.delay_ms:g} ms"]
    if d.jitter_ms:
        parts.append(f"+/- {d.jitter_ms:g} ms")
    if d.loss_pct:
        parts.append(f"{d.loss_pct:g}% loss")
    if d.burst_loss_pct:
        parts.append(f"{d.burst_loss_pct:g}% loss in bursts of {d.burst_length:g}")
    parts.append(f"{d.rate_mbit:g} Mbit/s" if d.rate_mbit else "no rate limit")
    return ", ".join(parts)


def _explain(link: Link, account: dict) -> str:
    n, f, p = account["near"], account["far"], account["path"]
    lines = [
        f"near  {n['endpoint']}:{n['channel']} (the device under test)",
        f"far   {f['endpoint']}:{f['channel']}",
        f"path  {p['rtt_ms']:g} ms round trip, from the {p['origin']}: {p['detail']}",
        f"down  {_figures(link.down)}",
        f"up    {_figures(link.up)}",
    ]
    if p.get("attribution"):
        lines.append(f"      {p['attribution']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
