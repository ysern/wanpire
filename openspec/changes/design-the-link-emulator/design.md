## Context

wanpire is a box on an Ethernet line that makes the line behave like a long internet link.
The reference build is a Raspberry Pi 4 (1 GB) with Ubuntu Server 24.04 LTS: its on-board
Ethernet port, a USB 3 gigabit Ethernet adapter, and its Wi-Fi. It must be usable by a person
at a web page and by AI agents over MCP, and it is open source, so it must be easy to read and
extend.

The spike [`spikes/netem-on-a-pi.md`](spikes/netem-on-a-pi.md) showed that Linux `tc netem`
is accurate on this board (fixed delay within 0.04 ms, loss within sampling error) and that
the Pi forwards at least ~37,000 packets/s through long netem queues while also generating the
traffic itself. It also found five traps that this design closes (D2). The study
[`spikes/calibration-sources.md`](spikes/calibration-sources.md) found which public
measurements may be shipped.

Terms used below:

- **Link:** what wanpire emulates, between the two sides of the box. It has two
  **directions**: *down* (towards the device under test) and *up* (away from it).
- **Device under test:** whatever sits behind the outbound adapter.
- **Endpoint preset:** a place and its access channels (D4). A link is made from two.
- **Holder:** the client that holds the broker's lease (D7).

## Goals / Non-Goals

**Goals:**

- Delay, jitter, loss (random and in bursts), bandwidth, reordering and duplication, per
  direction, accurate to what the spike measured.
- A link described by two endpoint presets and a channel at each end, or by raw figures.
- Two modes: transparent bridge, and router with NAT.
- One REST API as the only way into the engine; a web UI and an MCP server on top of it.
- One driver at a time, decided by a broker with leases and a queue.
- Safe by construction: impairments cleared at boot and by a dead-man timer; the control
  channel never impaired.
- Installs with one script on a Pi with Ubuntu Server, and on any Debian-like Linux with two
  Ethernet ports.

**Non-Goals:**

- Several links at once (one per outbound adapter). The configuration leaves room for it.
- Emulating a specific carrier's NAT quirks. wanpire's NAT is one well-behaved NAT.
- Replaying recorded traces packet by packet. Timed scenarios change the link in steps.
- Line-rate gigabit with long queues on a Pi 4. The README states where the limit is.

## Decisions

### D1. Impair both directions on the outbound adapter only

The *down* direction is netem on the outbound adapter's egress. The *up* direction is the
outbound adapter's ingress, redirected to an `ifb` device that carries its own netem.
Nothing is ever applied to the inbound or control adapter.

Why: the inbound adapter may be shared with the control channel (D5), and the spike found
that on a dual-homed box the control session's replies can leave by any port with the lower
route metric. Putting all impairment on the one adapter that is never shared means a
mistake cannot slow the control session, and no classifier is needed.

Not taken: netem on each port's egress (the spike's layout). Simple and measured, but it
puts an impairment on a port that may carry control traffic. Kept as a fallback if `ifb`
proves too costly on the Pi; B2 measures `ifb` against it in namespaces first.

### D2. The engine builds netem from a link description, and owns its traps

The engine turns a `DirectionSpec` (delay, jitter and its distribution, loss model, rate,
reorder, duplicate) into one netem command, through pyroute2. It closes what the spike found:

| Trap found | What the engine does |
|---|---|
| `tc qdisc replace` merges with the old options | Always deletes and re-adds the qdisc |
| netem's loss *correlation* produces almost no loss | Never emits it. Bursts use the Gilbert-Elliott model (`loss gemodel p r 1-h 1-k`), parameterised from a mean loss and a mean burst length |
| Jitter reorders most packets | Jitter keeps order by default, by setting netem's `rate` (to the link's bandwidth, or the port's line rate when none is asked). Reordering is a separate, explicit setting |
| `reorder` without `gap` does nothing | Reordering always sets a gap |
| The default queue (1,000 packets) drops packets on long delays | The queue is sized: `limit = ceil(1.5 × (delay + 3 × jitter) × rate / (8 × 1,500 bytes))`, at least 1,000, and capped by a memory budget per direction (default 64 MB at an assumed 2 KB per queued packet) |

Jitter's distribution defaults to `normal`: the uniform default of netem is rarely what
anyone means by jitter. Loss figures are always reported with *who* dropped: netem's own
counters are read back separately from what the endpoints report (the spike saw a receiver
drop 4.4% that netem did not).

Bandwidth uses netem's own `rate` in the first version, one qdisc per direction. Not taken
yet: a `tbf` or `htb` child for the rate, which shapes more like a real bottleneck queue (a
buffer that fills, then drops at the tail). B2 compares the two; the API does not change.

### D3. Safe by construction

- **Cleared at boot.** The systemd unit clears every qdisc wanpire may have created before
  the server starts.
- **Dead-man timer.** Every applied link has a lifetime (default: the lease's, D7). If it is
  not renewed, the link is cleared. A crashed agent leaves a clean line.
- **Cleared between holders.** Nobody inherits another's link.
- **Never on the control adapter** (D1, D5).

### D4. A link is two endpoints, each with a channel

An **endpoint preset** is a JSON file with a published JSON Schema:

```json
{
  "schema": "wanpire-endpoint/1",
  "id": "london",
  "name": "London",
  "location": {"lat": 51.507, "lon": -0.128, "country": "GB"},
  "default_channel": "generic",
  "channels": {
    "generic": {
      "kind": "generic",
      "description": "A typical home or office connection",
      "down": {"delay_ms": 8, "jitter_ms": 2, "loss_pct": 0.1, "rate_mbit": 100},
      "up":   {"delay_ms": 8, "jitter_ms": 2, "loss_pct": 0.1, "rate_mbit": 20},
      "sources": [{"name": "...", "url": "...", "date": "2026-07-30", "licence": "CC0-1.0"}]
    },
    "consumer-fibre": {"kind": "consumer-fibre", "...": "..."},
    "mobile-4g":      {"kind": "mobile-4g", "...": "..."}
  },
  "paths": {"los-angeles": {"rtt_ms": 140, "source": "..."}}
}
```

- **Channel kinds** are generic and never name a provider: `generic`, `media-private-network`
  ("managed studio-to-studio links, low loss, guaranteed bandwidth"), `enterprise-fibre`
  (dedicated line), `business-fibre`, `consumer-fibre`, `cable`, `dsl`, `fixed-wireless`,
  `mobile-4g`, `mobile-5g`, `satellite-leo`, `satellite-geo`.
- A channel's figures are its *access* contribution: from the user to the first major
  network. `down` and `up` are seen from the endpoint.
- Every figure names its source. A preset may override the path to a named other end with a
  measured figure whose licence allows it (`paths`).

**How two ends combine** into the link through the box:

- **Path delay:** a measured city-pair figure if the shipped table has the pair (D4a),
  otherwise the formula (D4b). Split evenly between the two directions.
- **Delay each way:** path / 2 + the near end's channel delay + the far end's.
- **Jitter:** the two channels' jitters add in quadrature (independent sources), plus a path
  term from the table where it has one.
- **Loss:** compounds: `1 − (1 − a)(1 − b)(1 − path)`. Burstiness is kept from the channel
  that has it (satellite, mobile).
- **Bandwidth each way:** the narrower of the two ends, the sender's *up* against the
  receiver's *down*.
- The result is a plain `LinkSpec` (two `DirectionSpec`s) that the user can read, adjust and
  apply. Raw figures are always accepted too.

Which end is which: the **near** end is where the device under test is (the outbound side);
the **far** end is the rest of the network.

**D4a. The city-pair table** ships only redistributable figures (see the study): the first
source is a CC BY 4.0 table of cloud-region round trips, mapped to cities, with the dataset's
date and the attribution. Each row: two city ids, `rtt_ms`, optional `jitter_ms`, `loss_pct`,
the source, its licence and its date.

**D4b. The formula** for pairs the table lacks:

    rtt_path = 2 × (great_circle_km × route_factor(region_a, region_b) / 200 km per ms) + router_ms

Light in fibre covers about 200 km per ms. `route_factor` starts at 1.6 (the first sanity
check, London to the US West coast) and is fitted per region pair (same continent, ocean
crossing, via a hub) against the table *and* the read-only sources, which are not copied. The
fit, and the error left over pair by pair, go in the repository.

Not taken: a measured table only (it covers only measured pairs, and most measurements may
not be shipped); the formula only (too wrong on routes that detour).

### D5. Adapters have roles

The main configuration file (`/etc/wanpire/wanpire.json`) maps adapters to three roles:

- **control:** where the web UI, the REST API and the MCP listen. Never impaired.
- **inbound:** the side of the line towards the wider network.
- **outbound:** the side towards the device under test. All impairment lives here (D1).

Rules, checked when the file is loaded and on every change through the API:

- control and inbound may share an adapter;
- **outbound shares its adapter with nothing.** A mapping that breaks this is refused with a
  message that says why;
- one outbound adapter per link (the configuration's shape is a list, for later).

The API lists every adapter: name, kind (on-board Ethernet, USB Ethernet, Wi-Fi), hardware
address, link state, speed, whether it can be a Wi-Fi access point, and its role.

The default on a Pi: Wi-Fi as control, the on-board port as inbound, a USB adapter as
outbound. The Pi's own Wi-Fi *can* be outbound, as an access point the device joins, with
control moved to an Ethernet port; the README says when a separate access point gives cleaner
figures, since a Pi's radio adds delay and loss of its own.

A change of mapping on a running box needs the lease, clears the link first, and refuses to
take the control adapter away from the session that is asking.

### D6. Two modes: bridge, and router with NAT

- **Bridge:** inbound and outbound joined in a Linux bridge with no address, STP off. The
  device under test stays on the same network as everything else and sees nothing of
  wanpire but what it does to packets. Requires inbound and outbound to be two wired ports on
  separate segments: a Wi-Fi client cannot be a bridge port, since the access point accepts
  only frames from the address that associated.
- **Router with NAT:** outbound gets an address on a private network of its own and serves
  DHCP on it (dnsmasq); traffic is masqueraded out of inbound (nftables), as behind a home
  router. Inbound may then be the Wi-Fi client. The devices under test get a network of their
  own, which is what tests behind-NAT behaviour (ICE, STUN, TURN).

The mode is configuration; switching needs the lease and clears the link.

### D7. A broker in the core: leases and a queue

One link, many clients. The broker lives in the core, under the REST API, so the REST API, the
web UI and the MCP see one holder and one queue.

- A client **asks** for the link with who it is and its purpose. If the link is free, it gets
  a **lease**; otherwise its request is **queued** in order of arrival.
- A queued client **polls**; each poll renews its request's TTL (default 60 s). A request
  not polled expires and leaves the queue, so a crashed client never blocks the others.
- A lease has its own TTL (default 120 s), renewed by any call from the holder or a
  heartbeat. An expired lease passes to the next in the queue, **and the link is cleared
  between holders**.
- **Only changes need the lease.** Reading the link, the counters, the adapters and the queue
  is open to every authenticated client.
- A person at the web UI can end a lease by hand, after a confirmation; the holder is told why
  on its next call.
- The TTLs are configuration. The skill tells agents to poll at a third of the TTL.

Not taken: a lock held until released (a crashed holder would hold it forever); priorities
(nobody asked for them).

### D8. One server, three faces, one token

```
            ┌───────────────────────────── wanpire server (FastAPI, one process) ─┐
 browser ──►│ web UI (static HTML + JS) ─┐                                         │
 any HTTP ─►│ REST API  /api/v1 ◄────────┴── MCP (streamable HTTP, /mcp) ◄── agent │
            │     │                                                               │
            │   core: broker · link model (presets, table, formula) · engine     │
            │     │                                                   (pyroute2) │
            └─────┼───────────────────────────────────────────────────────────────┘
                  ▼  netem / ifb / bridge / nftables on the outbound adapter
```

- **The REST API is the engine's only interface.** The web UI is a client of it. The MCP
  server's tools call the same REST API over HTTP, so the same token check and the same
  broker apply; the same package can therefore run the MCP on another machine over stdio,
  pointed at the box's URL.
- The server listens on the **control adapter's address only**, behind **one bearer token**
  generated at install.
- The MCP uses the official MCP Python SDK. Its tools: `wanpire_status`, `wanpire_request`
  (ask, or poll while queued), `wanpire_release`, `wanpire_presets`, `wanpire_preview` (two
  endpoints and channels to a `LinkSpec`), `wanpire_apply`, `wanpire_clear`, `wanpire_counters`,
  `wanpire_scenario`.
- Running the MCP on the box itself is the default: any client registers one URL and installs
  nothing. It costs the Pi nothing measurable, since it is idle between calls and the load is
  the kernel's forwarding.

**The web UI's style, in wanpire's own words:** it should look like the admin page of a
home router, the kind anyone has used. One column, at most about 800 px wide. System fonts.
White background, black text, one accent colour for actions, red only for a destructive one,
green and amber only for status. Plain tables for figures and plain forms with the label on
the left. A status line at the top: mode, the link's state, who holds it and since when, the
queue. No framework theme, no icons where a word will do, no animation. It works without
JavaScript frameworks; a few hundred lines of plain JS calling the REST API.

**A skill for agents**, `skills/wanpire/SKILL.md`, in the open Agent Skills format, teaches an
agent to register the MCP, ask for the link and wait while queued (polling inside the TTL,
saying once that it waits), describe a link by two endpoints and channels, check the counters,
and clear the link and release the lease as soon as it is done, or before it stops to wait for
a person. It never ends another client's lease.

### D9. Python, and how it is laid out

Python 3.12 (Ubuntu 24.04's), pyroute2 for links, bridges and qdiscs, FastAPI and uvicorn, the
official MCP SDK. Chosen for how easily people read and extend it. Not taken: Go (one binary,
fewer casual contributors), TypeScript (heavier on a Pi).

```
src/wanpire/
  model.py       DirectionSpec, LinkSpec, validation (no I/O)
  netem.py       DirectionSpec -> netem options; queue sizing; Gilbert-Elliott parameters (no I/O)
  presets.py     endpoint presets, the city-pair table, the formula, combining two ends (no I/O)
  engine.py      applies and clears through pyroute2; reads counters
  adapters.py    lists adapters, checks role mappings
  broker.py      leases, queue, TTLs (a clock is injected, so it is testable without sleeping)
  api.py         FastAPI app: REST, web UI's static files, MCP mount
  mcp_server.py  MCP tools over the REST API
  cli.py         `wanpire apply london:consumer-fibre los-angeles:mobile-4g`, `wanpire clear`, ...
presets/         endpoints/*.json, city-pairs.json, schema/*.json
skills/wanpire/SKILL.md
install/         install.sh, wanpire.service, netplan and nftables templates
tests/unit/      no root, no network
tests/netns/     root, in network namespaces with veth pairs, never real interfaces
```

Everything with "no I/O" is tested without root on any machine. The engine is tested in
namespaces on Linux, in a test bed like the spike's.

### D10. The install

`install/install.sh`, idempotent, for Ubuntu Server and other Debian-like systems:

1. apt: `python3-venv iproute2 nftables dnsmasq-base ethtool iw`.
2. A virtual environment in `/opt/wanpire`, wanpire installed into it with pip.
3. `/etc/wanpire/wanpire.json`, with the adapters detected and the default roles proposed,
   and a generated token in `/etc/wanpire/token` (mode 0600).
4. For bridge mode, a netplan drop-in that brings inbound and outbound up with **no address**
   and leaves the control adapter's configuration exactly as it was.
5. `wanpire.service` (systemd): clears every impairment, then starts the server on the control
   address. Runs as root, since it changes qdiscs and bridges; Not taken: an unprivileged user
   with `CAP_NET_ADMIN`, possible later, but pyroute2's bridge and nftables work needs care.

The first-boot steps before the install (flashing, key-only SSH, passwordless sudo, a DHCP
reservation for the control address) are in `docs/build-journal.md` and will be condensed
into the README.

## Risks / Trade-offs

- **The USB adapter's cost is unmeasured.** USB 3 on a Pi 4 shares a PCIe lane with the
  other USB ports; the adapter's own buffers add delay. → Measured in the hardware run, and the
  README states the limit found.
- **`ifb` on the Pi is unmeasured** (D1). → Measured in namespaces in B2; fallback documented.
- **netem `rate` is not a real bottleneck queue** (D2). → Compared with `tbf` in B2.
- **The Pi's Wi-Fi as an access point adds its own delay and loss.** → Documented; a separate
  access point is recommended for clean figures.
- **One well-behaved NAT** is not every carrier's NAT. → Documented as a limit; a symmetric
  NAT can be added later.
- **The formula's error** on unmeasured pairs may be large. → The table is used wherever it has
  the pair; the formula's remaining error is published.
- **Root.** The server runs as root on the box. → It listens on the control address only,
  behind a token; the box is meant to be dedicated.
