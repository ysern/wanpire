## Why

The engine impairs an adapter, but nothing yet puts the box on the line. The design (D5, D6)
settled two modes, a transparent bridge and a router with NAT, and three adapter roles kept in
a main configuration file, with outbound never shared. And the engine's bandwidth was netem's
own `rate`, which the design flagged as unlike a real bottleneck (D2, A5): this change
measures it against `tbf` and settles it.

## What Changes

- **The main configuration** (`/etc/wanpire/wanpire.json`, JSON, `wanpire-config/1`): the mode,
  and the adapters mapped to *control*, *inbound* and *outbound* (a list, one entry for now).
  Validated on load, with a message saying why: outbound shares its adapter with nothing; the
  named adapters exist; a bridge's ports are wired; in bridge mode control is not a bridge port.
- **The adapters list**: every adapter with its name, kind (on-board Ethernet, USB Ethernet,
  Wi-Fi, virtual), hardware address, link state, speed, whether it can be a Wi-Fi access point,
  and its role. Read from sysfs and `iw`.
- **Bridge mode** set up and torn down with pyroute2: inbound and outbound joined in a bridge
  with STP off and no address; a port that carries an address is refused, never stripped.
- **Router-with-NAT mode**: outbound gets an address on a private network of its own, a DHCP
  server (dnsmasq) on it, masquerading out of inbound (an nftables table of wanpire's own), and
  forwarding on; teardown puts forwarding back as it found it.
- `wanpire adapters`, `wanpire up`, `wanpire down` on the CLI.
- **Bandwidth through `tbf`** under netem, with a bounded bottleneck queue (`queue_ms`, default
  50 ms), instead of netem's `rate`: measured on the Pi, netem's rate with its delay-sized queue
  added up to 680 ms of queueing under one TCP flow; `tbf` bounds it to what is asked at the same
  throughput. netem keeps a `rate` at the line rate when jitter must keep order.
- Tested in network namespaces on the Pi, never on a real interface.

## Decided and assumed

Decided by the design: the roles and their rules, the two modes, pyroute2 for links and
bridges, nftables for NAT, dnsmasq for DHCP. Assumed here (also in `docs/open-questions.md`):
in bridge mode the control adapter may not be a bridge port (moving its address onto the bridge
is not built); the Pi's Wi-Fi as an outbound access point is refused as not built yet; the
router's default network is `10.77.0.0/24`; the bottleneck queue defaults to 50 ms; the
mode's state (what forwarding was, dnsmasq's pid) is kept in `/run/wanpire/`.

## Capabilities

### New Capabilities

- `adapter-roles`: the main configuration, the adapter list, and the rules on the mapping.
- `line-modes`: setting up and tearing down the bridge and the router with NAT.

### Modified Capabilities

- `link-model`: bandwidth becomes a bottleneck with a bounded queue (a new requirement; the
  netem queue is then sized at the line rate).

## Impact

- New: `src/wanpire/config.py`, `adapters.py`, `modes.py`; tests in `tests/unit` and
  `tests/netns`.
- `netem.py` and `engine.py`: the rate moves to a `tbf` child; counters report its drops.
- `pyroute2` becomes the first runtime dependency; the box needs `nftables`, `dnsmasq-base`
  and `iw` (the design's install list).
