"""wanpire's command line: apply, show, renew and clear a link on an adapter.

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

from .engine import DEFAULT_LIFETIME_S, CommandFailed, Engine, RefusedAdapter
from .model import Direction, InvalidLink, Link

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
    return p


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        engine = make_engine(netns=a.netns, control=a.control)
        if a.command == "apply":
            if a.file:
                with open(a.file, encoding="utf-8") as f:
                    link = Link.from_dict(json.load(f))
            else:
                link = Link(down=Direction(**_settings(a.down)), up=Direction(**_settings(a.up)))
            engine.apply(a.adapter, link, lifetime_s=a.lifetime or None)
        elif a.command == "renew":
            engine.renew(a.adapter, lifetime_s=a.lifetime)
        elif a.command == "clear":
            engine.clear(a.adapter)
        elif a.command == "show":
            print(json.dumps(engine.read(a.adapter), indent=2))
    except (InvalidLink, RefusedAdapter, ValueError) as e:
        print(f"wanpire: {e}", file=sys.stderr)
        return 2
    except CommandFailed as e:
        print(f"wanpire: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
