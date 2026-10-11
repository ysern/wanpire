# wanpire

<img src="docs/logo-proposals/d-emblem-full.svg" width="160" alt="wanpire's logo: a small board as a caped vampire, biting the line">

**A small box on your Ethernet line that makes it behave like a long internet link.**

wanpire sits between your device and the rest of the network and adds what a long
link adds: delay, jitter, loss (also in bursts), a bandwidth cap, reordering and
duplication, set separately for each direction. Describe the link by its two ends,
for example *London on consumer fibre* to *Los Angeles on 4G*, and wanpire works out
the rest. Drive it from a web page, a REST API, or any MCP-capable AI agent.

To install it on the box (Ubuntu Server, or any Debian-like Linux with two Ethernet ports), from
a checkout:

```sh
sudo install/install.sh                 # roles detected: Wi-Fi control, on-board in, USB out
sudo install/install.sh --dry-run       # what it would do, changing nothing
sudo install/install.sh uninstall       # and back out (--purge also removes /etc/wanpire)
```

It installs a service that clears every impairment at boot and serves the web page, the REST
API and the MCP on the control address, port 8080.

**Then open `http://<pi-address>:8080/` at once,** as with a new home router: the first visit
makes the box's one account, a user name and a password, which people and agents both sign in
with. Until then anyone on the control network could make it; to set it during the install
instead, add `--user admin` and give the password on standard input.

A forgotten password is reset on the box itself, over SSH:

```sh
ssh <pi-address> sudo wanpire account set admin   # a new password, asked twice
ssh <pi-address> sudo wanpire account reset       # or none: the next visit makes it again
```

The running server takes the change at once; no restart.

The reference build is a Raspberry Pi 4 with Ubuntu Server 24.04 LTS, its on-board
Ethernet port as the link in and a USB 3 gigabit Ethernet adapter as the link out,
controlled over its Wi-Fi. Any Debian-like Linux box with two Ethernet ports should do.

### Measured on the reference build

A Pi 4 (1 GB) in bridge mode, its on-board port and an ASIX AX88179B USB 3 adapter on two
gigabit segments, a machine behind each, driven through the REST API:

| What | Asked | Measured |
|---|---|---|
| No link applied | — | TCP 933 / 940 Mbit/s each way; base round trip 1.8–2.5 ms |
| Delay | 50 ms each way; 150 ms each way | round trip +100.0 ms; +300.0 ms (spread under 1 ms) |
| A preset | London to Sydney, 139 ms each way | round trip 280.6 ms (278 + the line's 2) |
| Loss | 2% one way | 2.02% and 1.93% over 31,000 packets, none the other way |
| Bandwidth | 50 Mbit/s | 47.5 Mbit/s of TCP goodput |
| Throughput through 150 ms each way | — | towards the device: 760 Mbit/s, nothing lost; away from it: 600 Mbit/s, nothing lost, then 3% lost at 700 |

Forwarding runs on one of the four cores. How each figure was taken, and what is not yet
understood about the last one, is in the spike's [findings](openspec/changes/design-the-link-emulator/spikes/netem-on-a-pi.md).

## Status

Early. The engine, the endpoint presets, the two modes, the broker, the REST API, a web page, an MCP server for agents and a command line work. What there is:

- the design and the first measurements: [`openspec/changes/design-the-link-emulator/`](openspec/changes/design-the-link-emulator/)
- how the box was built, step by step: [`docs/build-journal.md`](docs/build-journal.md)
- what is assumed and what is still open: [`docs/open-questions.md`](docs/open-questions.md)

What works today: a link described by its two ends, or by raw figures, applied on Linux as root.

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/wanpire endpoints                                    # the shipped cities and their channels
.venv/bin/wanpire preview london:consumer-fibre los-angeles:mobile-4g   # no root needed
sudo .venv/bin/wanpire apply --adapter <outbound> london:consumer-fibre los-angeles:mobile-4g
sudo .venv/bin/wanpire apply --adapter <outbound> --down delay_ms=150,jitter_ms=5 --up delay_ms=150,loss_pct=1
sudo .venv/bin/wanpire show  --adapter <outbound>
sudo .venv/bin/wanpire clear --adapter <outbound>
```

The box sits on the line as a transparent bridge or as a router with NAT, set in
`/etc/wanpire/wanpire.json`:

```json
{"schema": "wanpire-config/1", "mode": "bridge",
 "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["eth1"]}}
```

```sh
.venv/bin/wanpire adapters          # every adapter, its kind and its role
sudo .venv/bin/wanpire up           # set up the configured mode
sudo .venv/bin/wanpire down         # and take it off again
```

### A Wi-Fi device under test

A Wi-Fi adapter picked as inbound or outbound becomes an access point that the device joins
(`hostapd`, 5 GHz channel 36, WPA2 and WPA3), in either mode. Pick it on the web page's
Adapters / Roles page, with the network's name and password, or in the configuration:

```json
{"schema": "wanpire-config/1", "mode": "bridge",
 "adapters": {"control": "wlan0", "inbound": "eth0", "outbound": ["wlan1"]},
 "access_points": {"wlan1": {"ssid": "<wifi-ssid>", "passphrase": "<wifi-password>"}},
 "wifi": {"country": "<two-letter country code>"}}
```

The box's own Wi-Fi stays its control channel and is never offered. A USB adapter whose kernel
has no driver for it is named by the install; `install.sh --wifi-driver` builds the out-of-tree
[rtw89 backport](https://github.com/morrownr/rtw89) for Realtek's Wi-Fi 6 USB chips through DKMS
(one compiler at a time on a small box: a 1 GB Pi building with three stops answering).
wanpire ships none of that driver.

Adapters tried as access points on the reference build:

| Adapter | Chip | Driver | Access point |
|---|---|---|---|
| TP-Link Archer TX20U Plus (USB `2357:013f`) | RTL8832AU | rtw89 backport, DKMS | being tried |

Adapters whose driver is in the kernel and known to do AP mode, if you are buying one: MediaTek
MT7612U and MT7921AU based ones (`mt76`).

The REST API (`wanpire serve`, on the control adapter's address, port 8080) needs the box's
account: HTTP Basic credentials on every call (`curl -u admin:<password> ...`), or a browser's
session after it signs in. One client drives the link at a time:
ask for a lease (`POST /api/v1/lease`), keep it by polling (`POST /api/v1/lease/poll`), change
the link with its ticket (`PUT /api/v1/link`), release it (`DELETE /api/v1/lease`). The routes
are listed in [`src/wanpire/api.py`](src/wanpire/api.py) and at `/docs` on the box.

The same server serves a web page at `http://<pi-address>:8080/`: sign in, pick
the two ends and a channel for each, see the link's figures, ask for the link, apply, clear,
read the counters and see who else is using the box.

AI agents use the MCP at `http://<pi-address>:8080/mcp` (streamable HTTP, the account in an
`Authorization: Basic` header), or run it on their own machine over stdio with
`wanpire mcp --url http://<pi-address>:8080` and the account in `WANPIRE_USER` and
`WANPIRE_PASSWORD`. Client configurations for both are in
[`examples/mcp/`](examples/mcp/). The skill [`skills/wanpire/SKILL.md`](skills/wanpire/SKILL.md),
in the open Agent Skills format, teaches an agent to share the box: lease, wait, apply, check,
clear and release; copy its folder into your agent host's skills.

A link is cleared by itself after two minutes unless renewed (`wanpire renew`), so a
forgotten one never lingers. Tests: `.venv/bin/pytest` (no root needed; the web page's tests run in a headless browser when
`pip install -e ".[ui-test]" && python -m playwright install chromium` has been done), and with real packets
in network namespaces, `sudo .venv/bin/python -m pytest tests/netns`.

The project is planned with [OpenSpec](https://github.com/Fission-AI/OpenSpec):
`openspec/specs/` says what must be true, `openspec/changes/` holds the work in progress.

An end is `<endpoint>[:<channel>]`, where `<endpoint>` is a shipped city or your own preset
file (schema: [`src/wanpire/data/schema/endpoint.schema.json`](src/wanpire/data/schema/endpoint.schema.json)).
The first is where your device under test is.

## Data and its sources

- **Paths between cities**: round-trip figures from "Azure network round-trip latency
  statistics", Microsoft, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
  wanpire maps the regions to approximate coordinates and re-shapes the matrix
  ([`tools/import_backbone_rtt.py`](tools/import_backbone_rtt.py)).
- **Elsewhere, a formula** fitted on those figures; its error, pair by pair, is in
  [`docs/route-factor-fit.md`](docs/route-factor-fit.md).
- **Each city's generic access**: the M-Lab NDT Data Set (CC0), via the M-Lab statistics service.
- **The other kinds of access** are wanpire's own estimates, with their reasoning in each file.

## Licence

MIT, see [LICENSE](LICENSE). The data above keeps its own licence.
