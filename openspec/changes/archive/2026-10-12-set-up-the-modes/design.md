## Context

The design (`design-the-link-emulator/design.md`, D1, D2, D5, D6, D10) settled the roles, the
two modes and the tools. This document records what this change decides on top of it, and the
measurement that settles the bandwidth question D2 left open.

## Goals / Non-Goals

**Goals:** the main configuration and its rules; the adapter list; bridge and router-with-NAT
set up and torn down, tested in namespaces; the rate shaper chosen and built.

**Non-Goals:** the Wi-Fi access point (hostapd); several outbound adapters; the install script
and the netplan drop-in that leaves the bridge ports address-less at boot (B4); a mapping
change through the API (B3: it needs the broker's lease).

## Decisions

### M1. The configuration is JSON, validated against the adapters the box has

`config.py` turns the document into a `Config` (no I/O), refusing with a reason. The rules
that need the box's adapters (existence, kinds) run when an adapter list is given, which the
CLI always does; the unit tests give a fixed one.

```json
{
  "schema": "wanpire-config/1",
  "mode": "bridge",
  "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]},
  "router": {"address": "10.77.0.1/24"}
}
```

- **In bridge mode, control may not be a bridge port.** An address on a port stops working
  once the port is enslaved; it would have to move to the bridge, and a mistake there loses
  the box. Not built; refused with the reason. Router mode lets control and inbound share.
- **A Wi-Fi outbound adapter is refused as "not built yet"** (it needs an access point).
- **Outbound is a list of exactly one**, so the file's shape does not change when several links
  come.

Not taken: YAML or TOML (the presets are JSON; one format); a schema library at run time.

### M2. Adapters are read from sysfs, the access point from `iw`

`adapters.py` reads `/sys/class/net/<name>/`: `address`, `operstate`, `speed`; `wireless/` or
`phy80211` makes it `wifi`; a `device` link whose resolved path contains `/usb` makes it
`usb-ethernet`; no `device` link makes it `virtual`; otherwise `ethernet`. A Wi-Fi adapter can
be an access point when `iw phy <phy> info` lists `* AP` among its interface modes. The sysfs
root and the runner are injected, so it is tested on a fake tree without root.

Not taken: pyroute2 for the list (it has no kind or bus; sysfs has both); `ethtool -i` (one
process per adapter for what sysfs already says).

### M3. Links, addresses and bridges through pyroute2; NAT through `nft`; DHCP through dnsmasq

`modes.py` uses pyroute2's `IPRoute` (or `NetNS` for a named namespace) for the bridge, its
ports, addresses and link states. The NAT is an nftables table of wanpire's own, `inet
wanpire`, loaded with `nft -f -` and deleted whole: a forward chain accepting traffic from
outbound and the replies to it, and a postrouting chain masquerading the router's network out
of inbound. DHCP is `dnsmasq` bound to outbound only, daemonised with a pid file and its lease
file under the state directory, its configuration on the command line (`--conf-file=/dev/null`)
so nothing on the box changes it.

The state directory (`/run/wanpire`, a tmpfs, so a reboot forgets it) keeps what teardown
needs: IPv4 forwarding's value before setup, and dnsmasq's pid. Setup records forwarding only
if no record exists, so a second setup cannot record its own "on" as the original.

Not taken: pyroute2's nftables module (experimental in 0.9.6; `nft` takes a readable ruleset);
`iptables` (legacy on Ubuntu 24.04); systemd-networkd's DHCP server (it would mean writing its
configuration files and reloading it, which also manages the control adapter).

### M4. A bridge port with an address is refused, never stripped

Removing an address could cut the session that asked. The install's netplan drop-in (B4)
brings the ports up address-less; until then, the refusal names the port and its address.

### M5. Bandwidth through `tbf` under netem, with a bounded queue

Measured on the Pi, in the spike's three-namespace bed (`spikes/rate-shaper.sh`): 40 ms delay,
20 Mbit/s, one TCP flow for 15 s towards the device, a ping alongside.

| Shaper | TCP | Ping idle | Ping under load (avg / max) | Drops |
|---|---|---|---|---|
| netem `rate 20mbit`, queue 1,000 packets (wanpire's floor) | 18.9 Mbit/s | 40.1 ms | 372 / 718 ms | 0 |
| netem `delay 40ms` + `tbf rate 20mbit latency 20ms` | 19.0 Mbit/s | 40.1 ms | 62 / 72 ms | 9 |
| netem `delay 40ms` + `tbf rate 20mbit latency 100ms` | 18.9 Mbit/s | 40.1 ms | 126 / 151 ms | 13 |

netem's rate queues whatever its limit allows: a queue sized for the delay at the line rate is
seconds long at a low bandwidth, and one TCP flow fills it (bufferbloat far beyond any real
access link). `tbf` holds what its `latency` says, then drops, which is what a real bottleneck
does, and the throughput is the same. So:

- A bandwidth becomes `tc qdisc add dev X root handle 1: netem …` and
  `tc qdisc add dev X parent 1:1 handle 10: tbf rate R burst B latency Q`, with `Q` the new
  `queue_ms` (default 50 ms) and `B` the larger of 32 KB and one timer tick of data at the rate
  (rate / 250 Hz), below which tbf cannot reach its rate.
- netem keeps `rate` at the **line rate** when jitter must keep order (as before when no
  bandwidth was asked): ordering is netem's job, shaping tbf's.
- netem's queue is sized at the line rate, so drops above the bandwidth are tbf's; the counters
  report them apart (`shaper_dropped`).

Not taken: netem's `rate` (the bufferbloat above); `htb` (classes wanpire does not need);
`cake` or `fq_codel` as the bottleneck (an AQM is a fine thing to *offer*, but a plain tail-drop
queue is what most access links are; a later setting).

## Risks / Trade-offs

- **tbf's burst at gigabit rates** is half a megabyte, so short bursts pass at line rate. →
  It is the kernel's limit at 250 Hz; stated here.
- **Router mode changes a global setting** (forwarding). → Recorded before and restored on
  teardown; the state lives in `/run`, so a reboot (which resets forwarding too) forgets it.
- **dnsmasq answers DNS on outbound** with the box's resolver. → Bound to outbound only.
- **Namespaces are not the hardware.** → The hardware run (O1) repeats both modes with the
  USB adapter.
