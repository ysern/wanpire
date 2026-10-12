# Build journal

How wanpire was built, in the order it happened. Written as the work went, not
reconstructed afterwards. Every address, host name, user name and network name is a
placeholder: `<pi-address>`, `<pi-user>`, `<wifi-ssid>`.

## 2026-10-09 — The Pi, from a blank card to a box you can reach

The hardware: a Raspberry Pi 4 Model B with 1 GB of RAM in a two-tone case, a
microSD card, the official USB-C power supply. Later, a USB 3 gigabit Ethernet adapter
on one of the blue USB 3 ports.

### Flashing the card

Raspberry Pi Imager, with these choices:

- **Device:** Raspberry Pi 4.
- **OS:** Other general-purpose OS → Ubuntu → **Ubuntu Server 24.04 LTS (64-bit)**.
  An LTS server image because the box should run unattended for years and get
  security updates without a release upgrade every six months. 64-bit because the
  Python wheels and the kernel's networking are best tested on aarch64.
- **OS customisation** (the gear icon):
  - a host name;
  - a user `<pi-user>` (the password is set but never used; see below);
  - the Wi-Fi: `<wifi-ssid>`, its passphrase and the country;
  - **SSH enabled, public-key authentication only**, with the public half of a key
    made for this box alone.

The dedicated key, on the workstation:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/wanpire_ed25519 -C "wanpire control"
```

and an entry in `~/.ssh/config`, so that everything afterwards is just `ssh wanpire`:

```
Host wanpire
    HostName <pi-address>
    User <pi-user>
    IdentityFile ~/.ssh/wanpire_ed25519
    IdentitiesOnly yes
```

A dedicated key means the box can be cut off by deleting one line from its
`authorized_keys`, without touching any other machine's access.

### First boot: making SSH key-only for good

The Imager's "public-key only" setting writes it through cloud-init, which also drops
its own file into `/etc/ssh/sshd_config.d/`. To make the decision independent of
cloud-init, a drop-in of our own, sorted first so it wins (sshd takes the first value
it reads for each keyword):

```sh
sudo tee /etc/ssh/sshd_config.d/01-key-only.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
sudo systemctl reload ssh
sudo sshd -T | grep -E 'passwordauthentication|kbdinteractive|pubkeyauthentication'
```

`sshd -T` prints the configuration sshd will actually use, which is the only honest
check: `passwordauthentication no`, `kbdinteractiveauthentication no`,
`pubkeyauthentication yes`.

### Passwordless sudo

The user's password is never typed, so sudo must not ask for it. A file of its own in
`/etc/sudoers.d/`, checked with `visudo` before it can lock anybody out:

```sh
echo '<pi-user> ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/90-<pi-user>
sudo chmod 0440 /etc/sudoers.d/90-<pi-user>
sudo visudo -c
```

With key-only SSH this is no weaker than before: whoever has the key is already the
user, and a password nobody types protects nothing.

### A fixed address for the Wi-Fi

On the home router, a **DHCP reservation** binds the Pi's Wi-Fi MAC address to one
address, `<pi-address>`. The Pi itself keeps plain DHCP (cloud-init's netplan file is
left alone), so it still works on any other network, and the workstation's
`~/.ssh/config` names an address that never moves at home.

### Why the Wi-Fi is the control channel, and the Ethernet ports carry no address

wanpire's job is to stand on a cable and slow it down. If you also had to talk to it
over that cable, every command you sent would suffer the delay and loss you had just
asked for, and a bad setting (100% loss, say) would lock you out of the box that can
undo it. So:

- **Wi-Fi is control.** The web UI, the REST API and the MCP server listen there
  only. It is never impaired.
- **The two Ethernet ports are the line.** In bridge mode they are joined into a
  bridge with no IP address at all, so the devices on either side see one
  network and wanpire is invisible to them, except for what it does to their packets.

Today the on-board port is still plugged into the home network with a DHCP address,
which is handy for updates and harmless; nothing is applied to it. It becomes the
"inbound" port when the bridge is built (B4).

What the box looks like when it starts:

```
$ uname -r; lsb_release -ds; free -m | head -2
6.8.0-1065-raspi
Ubuntu 24.04.5 LTS
               total        used        free
Mem:             899         272         438
```

899 MB visible to Linux out of the 1 GB board, 272 MB used by a bare server. Four
Cortex-A72 cores. That is the whole budget.

## 2026-10-09 — Updating the box and installing the tools

```sh
sudo apt-get update
sudo apt-get full-upgrade -y
```

Only two packages were behind (an XML and an archive library); no new kernel, so no reboot.
The box stays on 24.04 LTS: no `do-release-upgrade`.

The spike's tools:

```sh
echo "iperf3 iperf3/start_daemon boolean false" | sudo debconf-set-selections
sudo apt-get install -y iproute2 iperf3 python3-venv python3-pip ethtool bridge-utils \
     tcpdump jq hping3 fping sysstat
```

The `debconf` line answers iperf3's install-time question ("start a server at boot?") with no,
so an unattended install does not hang on it. netem itself needs nothing: Ubuntu's Pi kernel
ships `sch_netem` as a module (`modinfo sch_netem`). One package I expected,
`linux-modules-extra-raspi`, does not exist for this kernel, and is not needed.

## 2026-10-09 — Is the name free?

- GitHub repositories named or describing "wanpire": only ours.
- GitHub *users*: an account called `wanpire` exists, created in 2023, with one repository and
  no description. Not a project, but it means `github.com/wanpire` is not ours to have.
- PyPI: `wanpire` is free (`https://pypi.org/pypi/wanpire/json` answers 404). npm: free too.

No clash worth renaming over.

## 2026-10-09 — Planning with OpenSpec

The project is planned with OpenSpec, so the design, the requirements and the work are files
in the repository next to the code:

```sh
openspec init --tools claude .
```

`openspec/config.yaml` describes the project for the agents that write the plans;
`openspec/changes/<change>/` holds a change while it is worked on (proposal, specs, design,
tasks); `openspec/specs/` holds what is true once a change is archived. The first change is
the design itself: `design-the-link-emulator`.

## 2026-10-10 — The spike: is netem on a Pi good enough?

Before writing a line of the tool: does Linux's network emulator do what it says on this
board, and how much can the Pi push through it?

### A test bed that cannot hurt anything

The box's real ports are its lifeline, so the first experiments use none of them. Three
network namespaces on the Pi, joined by virtual Ethernet cables:

```
  wp-a (10.99.0.1) -- veth -- [ wp-br: bridge br0, no address ] -- veth -- wp-b (10.99.0.2)
                          a1: netem for b->a          netem for a->b: b1
```

```sh
ip netns add wp-a; ip netns add wp-br; ip netns add wp-b
ip link add a0 netns wp-a type veth peer name a1 netns wp-br
ip link add b0 netns wp-b type veth peer name b1 netns wp-br
ip -n wp-br link add br0 type bridge
ip -n wp-br link set a1 master br0; ip -n wp-br link set b1 master br0
# ... addresses on a0 and b0 only, everything up
ip netns exec wp-br tc qdisc add dev b1 root netem delay 50ms   # a -> b
```

Each direction is impaired on the egress of the port it leaves by, which is how it will be on
the real box. The scripts are in the design change's `spikes/scripts/`.

### Delay: exact

`ping` 500 times at 10 ms intervals, half the round trip asked in each direction:

```
label                  asked   min      avg      max      mdev (ms)
none                       0   0.063    0.089    0.132    0.004
delay 20                  20  20.071   20.125   20.234    0.011
delay 100                100 100.109  100.126  100.185    0.005
delay 200                200 200.107  200.124  200.184    0.005
delay 300                300 300.110  300.127  300.177    0.005
jitter ±10 uniform       100  81.948  100.316  119.699    8.345
jitter ±10 normal        100  61.976  100.018  144.649   14.295
jitter ±10 paretonormal  100  80.957   99.755  147.046   12.043
jitter ±10 normal + rate 100  66.356  103.835  136.465   11.227
```

Asked 300, got 300.127, and 0.089 of that is the test bed itself. The jitter's spread matches
the theory for each distribution (uniform ±10 ms each way: 8.2 ms round trip; normal σ=10 ms
each way: 14.1 ms). **Surprise one: netem's default jitter distribution is uniform**, which is
not what anyone pictures when they say "10 ms of jitter".

### Loss, bursts, duplicates, reordering

A tiny sequenced UDP prober (`seq.py`): 10,000 numbered packets at 1,000 per second; the
receiver counts what is lost, in what bursts, what arrives twice and what arrives late.

```
asked                         lost    bursts  mean burst  out of order  duplicates
none                            0        0       -              0           0
loss 1%                        88       87     1.01             0           0
loss 5%                       495      473     1.05             0           0
Gilbert-Elliott (3.2%, ~3.3)  282       89     3.17             0           0
loss 2% with 25% correlation    1        1     1.0              0           0
jitter ±10 ms uniform           0        -       -           7173           0
jitter ±10 ms normal + rate     0        -       -              0           0
duplicate 1%                    0        -       -              0         102
reorder 5% 50%                  0        -       -              0           0
reorder 25% gap 5               0        -       -           8730           0
```

Random loss, Gilbert-Elliott burst loss and duplication are all where they should be.
Three surprises:

- **Correlated loss is broken.** Asking for 2% loss with 25% correlation lost *one* packet in
  ten thousand (and none on a second run), while plain 2% lost 1.8%. Burst loss must use the
  Gilbert-Elliott model.
- **Jitter reorders packets wholesale.** 72% arrived out of order: each packet draws its own
  delay, so one sent later can overtake. Real paths mostly keep order. netem's `rate` option
  keeps them in line, since each packet then waits for the one before it.
- **`reorder` without a `gap` does nothing** on this kernel.

And a fourth, found by accident: `tc qdisc replace` on a netem *merges* the new options into
the old ones. Replacing "delay 20ms reorder 5%" with "loss 2%" left the reorder in place.

The first attempt at this table used iperf3's out-of-order count, which came back zero for
everything, heavy jitter included. Wrong field: iperf3's client summary does not carry the
receiver's count. That is why the sequenced prober exists.

### Netem-Q: a long delay needs a long queue

netem holds every delayed packet in a queue of, by default, 1,000 packets. 100 Mbit/s of
1,400-byte packets is about 8,700 packets a second; held for 150 ms, that is 1,300 packets in
flight. So the default should drop roughly a quarter:

```
100 Mbit/s, 150 ms one way, limit 1000 (default)   loss 25.28%   netem dropped 33,925
100 Mbit/s, 150 ms one way, limit 2000             loss 0%
```

The engine must size the queue from the delay, the jitter and the rate.

### How much can the Pi push?

iperf3, one way through the bridge, with `mpstat` watching all four cores. In namespaces the
traffic generators run on the same Pi, so these are floors, not ceilings:

```
                                               delivered    loss    idle (4 cores)  busiest core
UDP 600 Mbit/s 1400 B, no netem                600 Mbit/s   0%      27%             100%
UDP 1000 Mbit/s 1400 B, no netem               611 Mbit/s   0%      26%             100%
UDP 300 Mbit/s, 150 ms one way, limit 6000     300 Mbit/s   0%      45%              95%
UDP 500 Mbit/s, 150 ms one way, limit 10000    419 Mbit/s   0.02%   34%              95%
UDP 500 Mbit/s, 150 ms, 5% loss                428 Mbit/s   5.06%   36%              95%
UDP 64 B packets, no netem                     60,000 packets/s     25%             100%
UDP 64 B packets, 50 ms one way                39,000 packets/s     31%              94%
```

The limit is one core: on veth the sender's own system call carries the packet through the
bridge and into netem, so the sender's core does everything. About 37,000–39,000 packets a
second through a long netem queue, whatever their size. A 50 Mbit/s video stream is about
4,500 packets a second. The 1 GB of RAM was never close to the limit: with a 10,000-packet
queue the box still had 610 MB available.

**Surprise:** with jitter *and* ordering kept, 300 Mbit/s lost 4.4%, yet netem dropped
nothing. The packets died in the receiver's socket buffer (`UdpRcvbufErrors`), because packets
held behind a slow one are released together, as a burst. That is what jitter does to a real
receiver too. Lesson for the tool: every loss figure must say who dropped the packet.

### Can the home network stand in for the second port?

The owner asked: the Pi is on the home network twice, by Wi-Fi and by cable, and so is the
workstation. Can one carry control and the way in, and the other the way out?

**For the transparent bridge, no.** A Wi-Fi client cannot be a port of a bridge. Wi-Fi frames
carry three addresses, and an access point accepts frames only from the MAC address that
associated with it; a bridge would be forwarding frames *from other devices' addresses*, and
the access point drops them. (A four-address "WDS" mode exists, but the access point has to
support and allow it.) And even with two cables, bridging two ports that sit on the *same* LAN
joins the LAN to itself: a loop. The bridge needs two wired ports on separate segments, which
means the USB adapter.

**For router-with-NAT, yes, with care.** The rig (`rig.sh`): the workstation connects to the
Pi's Ethernet address on two test ports; nftables forwards those two ports, and nothing else,
to a target in a namespace on the Pi behind a veth pair; netem sits on the veth ends, never on
a real port; a timer armed first removes everything after 20 minutes whatever happens:

```sh
systemd-run --unit wp-deadman --on-active=20m /path/to/rig.sh down
```

The workstation needed no route and no firewall rule: it only makes outgoing connections
(`iperf3` and a small UDP echo prober, since ping's ICMP cannot be port-forwarded).

**Surprise: the home network is not a wire.** Workstation to Pi, through the house:

```
                                   min       median    p99       loss
the house's own path               3.9 ms    6.4 ms    22 ms     0%
+ 50 ms each way                 103.9 ms  108.2 ms   151 ms     0%      (+100.03)
+ 150 ms each way                304.0 ms  307.3 ms   486 ms     0.15%   (+300.07)
+ 50 ms and 2% loss each way     104.0 ms  106.8 ms   149 ms     4.1%    (expected 3.96)
```

The minimum moved by exactly what was asked, and the loss compounded as it should; but the
house added its own 4 to 20 ms and carried only 55 Mbit/s one way and 21 the other. Somewhere
between the desk and the Pi there is a wireless mesh hop. Fine for checking that delay is
added on top of a real path; useless for finding the Pi's ceiling. That waits for two wired
ports.

**Another trap found here:** with both Wi-Fi and Ethernet on the same LAN, the Pi answered the
SSH session that came in over Wi-Fi *out of the Ethernet port*, because its route there has
the lower metric. An impairment on that port without a filter would have slowed my own
control session. In the finished box the bridge ports carry no address, so it cannot happen;
in the design, every impairment lives on the outbound port, which never carries anything else.

### Cleaning up

Every run ends with the namespaces deleted, the nftables table removed, forwarding switched
back off and the dead-man timer stopped. One more trap: **deleting a namespace does not stop
its processes.** An `iperf3` started inside a namespace kept running after the namespace was
gone. The scripts now kill a namespace's processes (`ip netns pids`) before deleting it. And
`pkill -f iperf3` over SSH is a bad idea: the remote shell's own command line contains the
word, so it kills the session that sent it.

## 2026-10-10 — What data may we ship?

wanpire describes the path between two cities with measured figures where it can, and a
formula where it cannot. Only data whose licence allows redistribution goes into the shipped
table; the rest may only calibrate the formula. What I found:

| Source | Licence | Ship it? |
|---|---|---|
| A cloud provider's published region-to-region round trips | CC BY 4.0 | Yes, with attribution |
| M-Lab NDT (access-link speed, RTT, loss) | CC0 | Yes |
| RIPE Atlas | Terms: commercial use needs prior permission | No, read only |
| WonderNetwork ping tables | No licence; "please reach out" | No, read only |
| Ookla Open Data | CC BY-NC-SA 4.0 | No (not compatible with MIT) |
| Cloudflare Radar | CC BY-NC 4.0 | No |
| TeleGeography cable map | Maps CC BY-SA; data by subscription | No |

First sanity check of the formula: London to the US West coast is about 8,630 km on the great
circle; light in fibre would take 86 ms there and back; the published figure is 140 ms. A route
factor of about 1.6, which is in line with what is usually quoted for intercontinental paths.

## 2026-10-10 — The engine, test-first

The second change, `build-the-link-engine`, starts with its requirements written as
scenarios (`openspec/changes/build-the-link-engine/specs/`), then tests, then code.

**A library gap decided one thing.** The plan was pyroute2 for everything netlink. Its netem
support (0.9.6) leaves out the delay distribution table and the loss models, so it cannot
express normal jitter or Gilbert-Elliott loss, the two things the spike said we must use. The
engine therefore builds `tc` argument lists (a pure function, testable on any laptop) and runs
them; pyroute2 stays for adapters and bridges.

What the engine does, in the order it was tested:

1. **The model** (`model.py`): two directions, each with delay, jitter and its distribution,
   random or burst loss, bandwidth, duplication and reordering; refusals that name the setting
   and its range.
2. **netem's options** (`netem.py`): normal jitter by default; `rate` set under jitter so
   packets keep their order; burst loss as Gilbert-Elliott from two human figures (mean loss,
   mean burst length: `r = 1/B`, `p = L·r/(1−L)`); a reorder gap always; the queue sized as
   1.5 × (delay + 3 jitters) × rate, at least 1,000 packets, at most 64 MB.
3. **The engine** (`engine.py`): *down* on the outbound adapter's egress; *up* on its ingress,
   redirected (`matchall` + `mirred`) to an `ifb` device with its own netem. Every apply clears
   first, so nothing lingers. Counters come from `tc -s -j` (JSON).

51 unit tests run in a third of a second without root. Then the same scenarios with real
packets, in namespaces on the Pi (`sudo .venv/bin/python -m pytest tests/netns`): 10 passed in
under two minutes, first time. Figures from that bed:

```
50 ms each way                         round trip +100.048 ms
10 ms jitter one way, order kept       spread 10.07 ms, 0 of 10,000 out of order
3% loss in bursts of 3                 2.94% lost, mean burst 2.7, longest 12
150 ms down (egress netem)             418 Mbit/s through, engine dropped 0
150 ms up (ingress via ifb)            373 Mbit/s through, engine dropped 0
```

The `ifb` detour for the up direction costs about 11% of throughput on the Pi, at a rate far
above anything wanpire is for.

### The dead-man

A forgotten impairment is the worst failure a link emulator has: somebody's video call is
slow for a day and nobody knows why. Every `apply` therefore arms a **transient systemd
timer** that runs `wanpire clear` when the link's lifetime (two minutes by default) runs out;
`wanpire renew` pushes it back. Being a systemd unit, it fires even if the program that applied
the link has crashed. One detail that mattered: the timer must run on the host, not inside the
network namespace, so the engine keeps two runners, one for the adapter's namespace and one for
the host. The namespace tests check both ways: not renewed, gone after its lifetime; renewed
every two seconds, still there after ten. 77 tests pass on the Pi.

## 2026-10-10 — Two ends instead of numbers

The engine takes figures: 150 ms, 1% loss. Nobody thinks of a link that way. You think "my
laptop in London on fibre, talking to someone in Los Angeles on 4G". The third change,
`add-endpoint-presets`, makes that the way to ask:

```
$ wanpire preview london:consumer-fibre los-angeles:mobile-4g
near  london:consumer-fibre (the device under test)
far   los-angeles:mobile-4g
path  142.1 ms round trip, from the table: uk-south (London) to us-west (San Francisco
      Bay Area): 140 ms; 0 km and 560 km from the ends, corrected by +2.1 ms
down  100 ms, +/- 8.1 ms, 0.55% loss in bursts of 3, 8 Mbit/s
up    100 ms, +/- 8.1 ms, 0.55% loss in bursts of 3, 30 Mbit/s
```

An **endpoint** is a JSON file (with a published schema): a city, its coordinates, and its
**channels**, the kinds of access you can have there: generic, fibre, cable, DSL, 4G, 5G,
two kinds of satellite, a studio-grade private network. No provider is ever named. The link
is the path between the two cities plus each end's channel: delays add, jitters add in
quadrature, losses compound, and the bandwidth is the narrower end's.

### Where the path comes from

The rule from the start: only figures whose licence allows us to ship them. One cloud
provider publishes the median round trip between its ~54 data-centre regions, measured every
minute, in a documentation repository licensed CC BY 4.0. That is 2,862 directional figures,
shipped with their attribution, and rebuilt by a script from the page's own CSV.

A city is anchored at its nearest data-centre site, if one is within 1,000 km, and the
table's figure is nudged by the difference the distance makes. Everywhere else, a formula:

    rtt = 2 × great-circle km × route factor / 200 km per ms + router term

### Fitting the formula, and publishing how wrong it is

The design's first guess (one factor of 1.6, no router term) was off by a median of 14.5%
against the table. Fitting a factor per pair of world regions and a router term (7.5 ms)
brought it to 6.7%. The honest figure is the one with each site *held out* of the fit and then
predicted, because that is how the formula is used, for places the table lacks: **8.9%**
median, 23% at the 90th percentile. All 1,419 pairs and their errors are in the repository.

The data taught two things. First, Europe to "east Asia" was a mess (19.5% median error) until
south-east Asia became a region of its own: Europe reaches Singapore by the straight route
through the Red Sea, and Tokyo or Seoul by long ones. Second, a formula cannot know a route:
São Paulo to Cape Town is 6,300 km, but this backbone does not use the South Atlantic cable,
so the measured round trip is 304 ms against the formula's 106. That is what the table is for.

### Access figures

For each city's *generic* channel, M-Lab's NDT statistics (CC0): the median download, upload
and minimum round trip people in that city measured to their nearest test server, January to
March 2024. London: 51 Mbit/s down, 9 up, 5.6 ms. Mumbai: 29 down, 12 up. The other kinds are
our own typical figures, written down with the reasoning behind each, such as the
geostationary satellite's 290 ms each way: 35,786 km up and down again is 239 ms at the speed
of light before anything else happens.

110 unit tests, all without root, pass on the laptop and on the Pi.

## 2026-10-10 — Putting the box on the line: bridge or router

Two ways to sit on a cable. As a **bridge**, the box is invisible: the two ports are joined,
neither has an address, and the device behind it stays on the same network as before. As a
**router with NAT**, the device gets a network of its own, an address from the box's DHCP
server, and leaves through the box's address, like behind a home router; that is the mode for
testing anything that cares about NAT.

Which port does what lives in one small JSON file: *control* (where wanpire is driven from),
*inbound* (towards the wider network), *outbound* (towards the device). One rule matters more
than the rest: **outbound shares its port with nothing**, because every impairment lives on
it. A file that breaks it is refused with that sentence.

Both modes are built with pyroute2 (bridges, addresses), one nftables table of wanpire's own
(the NAT), and dnsmasq (DHCP), and tested with real packets in network namespaces on the Pi:
the device pings across the bridge; in router mode it gets an address by DHCP, and the far
side sees the box's address as the sender. Tearing down puts IP forwarding back to what it was.
All seven passed on the first run.

### netem's rate is not a bottleneck

The design left one question open: shape bandwidth with netem's own `rate`, or with a separate
token bucket (`tbf`)? Measured on the Pi: 40 ms of delay, 20 Mbit/s, one TCP download, and a
ping running alongside.

| Shaper | Download | Ping under load (avg / max) |
|---|---|---|
| netem `rate` | 18.9 Mbit/s | 372 / 718 ms |
| `tbf`, 20 ms queue | 19.0 Mbit/s | 62 / 72 ms |
| `tbf`, 100 ms queue | 18.9 Mbit/s | 126 / 151 ms |

Same speed, very different line. netem holds as many packets as its queue allows, and the
queue has to be long enough for the delay at full line rate, so at 20 Mbit/s one TCP flow piles
up most of a second of data in it. A real access link has a buffer of tens of milliseconds and
drops beyond it. So bandwidth is now a `tbf` under the netem delay, with its queue as a setting
(`queue_ms`, 50 ms by default), and the counters tell the bottleneck's drops from wanpire's own.
(One trap on the way: the kernel counts a child queue's drops in its parent's too, so netem's
"dropped" included the bottleneck's until the engine subtracted them.)

## 2026-10-10 — One driver at a time: the broker

wanpire will be driven by people at a web page and by AI agents, often several at once. If two
change the link together, neither measures what it asked for. So there is a **broker**, and it
sits in the core rather than in any one interface, so the web page, the REST API and the MCP all
see the same holder and the same queue.

The rules fit in a paragraph. Ask for the link with who you are and why; you get a ticket. If
the link is free, the ticket holds a **lease**; otherwise it waits in a queue, first come first
served. Both are kept alive by use: a queued ticket that is not polled for a minute leaves the
queue, and a lease without a call for two minutes ends. When a lease ends, for any reason, the
link is cleared before the next in line gets it, so nobody inherits another's impairments. A
person can end a lease by hand, and the agent holding it is told why on its next call.

The point of the time limits is the crashed client. An agent that dies while waiting, or while
holding the link, frees it within two minutes without anyone noticing, and the engine's own
dead-man timer clears the line even if the server itself has died.

The broker has no thread and never sleeps: the clock is passed in, and every call first works
out what the passing time has done. Its 16 tests run in milliseconds by moving a fake clock.

## 2026-10-10 — The REST API

Everything so far is reachable through one HTTP interface, and nothing else will reach the
engine: the web page and the MCP for agents will both be clients of it, so there is exactly one
place where the token is checked and one broker deciding who drives.

```sh
curl -H "Authorization: Bearer $TOKEN" -d '{"who":"me","purpose":"testing a call"}' \
     -H 'content-type: application/json' http://<pi-address>:8080/api/v1/lease
curl -X PUT -H "Authorization: Bearer $TOKEN" -H "X-Wanpire-Ticket: $TICKET" \
     -H 'content-type: application/json' -d '{"near":"london","far":"new-york"}' \
     http://<pi-address>:8080/api/v1/link
```

A design detail I like: the lease drives the dead-man. A link is applied with the lease's
lifetime, and every poll from the holder renews both. An agent that keeps polling keeps its
link; one that crashes loses the lease and the link on the same two-minute clock, and the link
is cleared by a systemd timer even if the server itself has died.

Tried for real on the Pi, against a namespace test bed: no token, 401; ask for the lease, get
it; put London to New York; a ping across the box goes from 0.1 ms to 84 ms; release, and the
link is gone. 179 unit tests run on the laptop in under four seconds.

## 2026-10-10 — A web page, like a router's

A person should not need `curl` to slow a line down. The box now serves a page at its own
address: give it the token once, pick two places and a channel for each (London on its generic
line, Los Angeles on 4G), and it shows what the link will be both ways before anything changes:
98.8 ms each way, 8 ms of jitter, 0.6% loss in bursts of three, 8 Mbit/s down and 8.9 up, and
where the 142 ms path came from. Ask for the link, apply, and the counters start moving.

The look is deliberately boring: the admin page of a home router, the kind everybody has used.
One column, system fonts, white or near-black depending on the phone's setting, one blue for
actions, red only for the one button that ends somebody else's lease, green and amber only for
state. Three files, no framework, no build step: about 350 lines of plain JavaScript that call
the same REST API an agent would. The page gets no shortcut into the box.

It is a polite client, too. It holds a lease like everybody else, polls it at a third of its
lifetime only while it is open, and gives the link back when the tab is closed. Ending an agent's
lease by hand takes a confirmation and a reason, and the agent is told that reason on its next
call.

The tests drive the page in a headless Chromium (Playwright) against the real server with a
fake engine: 16 of them, written before the page, including one that fails if anything scrolls
sideways on a 360-pixel phone. Then the real thing, through an SSH tunnel to the Pi and a
namespace test bed: a ping across the bed went from 0.12 ms to 196 ms when the page applied
London to Los Angeles on 4G (twice 98.8 ms, as previewed), and back to 0.12 ms when it released.

## 2026-10-10 — Agents get their own door: the MCP

The point of wanpire, for me, is that an AI agent testing a piece of software can say "make
this a bad 4G line to Sydney" and get it. Agents speak MCP, the Model Context Protocol, so the
box now has an MCP server: nine tools (status, endpoints, lease, poll, describe, apply, clear,
counters, release), each a few lines that call the REST API. Nothing in it reaches the engine
directly. On the box the tools even call the API over HTTP, through a transport bound to the
application itself, so the token is checked and the broker decides exactly as for anyone else.

Two small design choices made it simple. The agent carries its own ticket: `wanpire_lease`
returns it and every change takes it, so the MCP server keeps no state and a reconnecting agent
loses nothing. And every answer says what to do next: "Queued at position 1. Say once that you
are waiting for the link, then call wanpire_poll every 20 s until you hold it."

There is deliberately no tool to end somebody else's lease. An agent that wants the box must
wait; a person at the web page can decide otherwise.

The same package runs on a laptop too: `wanpire mcp --url http://<pi-address>:8080` serves the
tools over stdio and calls the box across the network. The owner asked whether that would save
the Pi's CPU. It would not, measurably: the MCP sleeps between calls, and the Pi's work is the
kernel's, delaying and forwarding packets.

Tried for real against the namespace bed on the Pi, from the laptop through a tunnel: an MCP
client leased the link, described London to Sydney (139 ms each way), applied it, and a ping
across the bed went from 0.12 ms to 279 ms; it cleared and released, and the ping was back at
0.12 ms. The same through `wanpire mcp` over stdio. The SDK had just moved to a 2.x line that
renamed its server class, which cost ten minutes of reading the installed package rather than
the internet's examples.

## 2026-10-10 — Teaching agents manners: the skill

Tools are not enough. An agent that applies a link and then stops to ask its user a question
holds the only link for as long as the answer takes; one that forgets to poll loses its lease
and runs the rest of its test on a clean line without noticing. So wanpire ships a skill,
`skills/wanpire/SKILL.md`, in the open Agent Skills format: a folder any agent host can copy into
its skills, with a short front matter and plain instructions.

What it teaches fits on one screen: register the MCP; ask for the link with who you are and why;
if queued, say *once* that you are waiting and poll at the interval the answer gives; describe
the link by two places and check it before applying; prove with the counters that your traffic
crosses the box; and give the link back the moment you are done, or before you stop to wait for
a person. Never end another agent's lease.

A test keeps it honest: it fails if the skill names a tool the MCP no longer has, or stops
teaching any step of a lease's life.

Followed by hand on the Pi's namespace bed, with a person holding the link: the agent was told
"Queued at position 1. Say once that you are waiting...", got the link on its next poll after
the person released it, described Tokyo to London over a geostationary satellite (410 ms each
way), applied it, and a ping across the bed averaged 817 ms with the counters showing the
packets in both directions. Cleared and released, the ping was back to 0.13 ms.

## 2026-10-10 — One script to make a box

Everything so far ran from a checkout, with a token made by hand. Now `install/install.sh` turns
Ubuntu Server (or any Debian-like Linux with two Ethernet ports) into a wanpire box: the packages,
a virtual environment in `/opt/wanpire`, the configuration with the adapters' roles, a token, a
netplan drop-in that leaves the line's two ports without an address, and a systemd service that
clears every impairment, sets up the bridge and serves on the Wi-Fi address.

The script is careful about the one thing that can lock you out of a headless box: the network.
It never names the control adapter in netplan, and it writes and validates the drop-in but does
not apply it unless asked, because applying netplan restarts networking, Wi-Fi included. It runs
every check before its first change, so a missing USB adapter stops it with the box untouched.
And it is idempotent: run it twice and the second run says "unchanged" for every step, keeping
the token.

The USB adapter has not arrived, so the script was tested two ways. Seventeen tests run it
against a staging directory with a fake `/sys/class/net`, as an ordinary user: the files and
their modes, the roles detected, the refusals, the second run byte for byte, the uninstall. Then
a real install on the Pi, with the roles pointed at a namespace test bed: the service came up,
the web page answered over Wi-Fi, a link applied through the API put 84 ms across the bed, and a
`systemctl restart` brought the line back to 0.13 ms on its own. `uninstall --purge` left nothing
behind.

## 2026-10-10 — The page gets a proper look

The first page was deliberately bare, one column of plain tables. The owner wanted it to look
like the admin interface of a home router: the kind with a coloured band across the top, round
icons for the sections, a menu down the side and white panels on a light grey page. Simple and
neat, and familiar to anyone who has ever changed a Wi-Fi password.

So the page was rebuilt to a set of style rules, written out in the project's own words in the
web UI's design: the band 160 px tall, 44 px circled line icons, labels on the left of the forms,
one primary button per panel, tables as white "pills" on a tinted card. The colours are
wanpire's own: a wine red for a vampire on the wire, deepened until white text on it passes the
accessibility guidelines (WCAG 2.2 AA) with room to spare, and a warm amber for "you are here".
A dark theme keeps the same roles.

Accessibility is not taken on trust. A test opens every page at 720 and 1,280 px, light and
dark, and measures the contrast of every visible piece of text against what is really behind
it, both ends of a gradient included. It caught one rule that could not be kept as written: the
light grey for the sentence under each title is 2.4:1 on white, so it became a darker grey of
the same family. Another test lists every request the page makes: nothing leaves the box, no
web fonts, no icon sets, no scripts from elsewhere. 26 page tests in all, in 30 seconds.

## 2026-10-10 — A face for the vampire

The name came first, a pun: a vampire sitting on the WAN, sucking the traffic. So the logo is
the box itself: a small computer in its case, two-tone, a grey rounded lid over a black base,
with a cartoon face on the front. Big eyes on the lid, two fangs sunk into an Ethernet cable,
and little packets draining from the cable into the mouth. One version adds a vampire's cape
collar; a third is just a head biting a network plug, which survives being shrunk to a browser
tab.

The rules for it: a generic case, no product's name or logo; only the project's own drawing in
the repository; legible at 16 pixels and in one colour. Each proposal is three hand-drawn SVGs,
in the web page's wine red and amber: full colour, one colour, and a favicon redrawn on a
32-pixel grid, since a scaled-down drawing turns to mush at that size. A contact sheet shows them
all at 128, 32 and 16 px on light and dark. They wait for the owner to pick one.

## 2026-10-10 — On the wire at last

The USB adapter arrived and went in: an ASIX AX88179B, gigabit, in one of the Pi's blue USB 3
ports. The Pi went between a machine and the switch it used to plug into, its on-board port on
the machine's side and the adapter on the switch's. One more cable came out of the drawer too:
the on-board port, which had linked at 100 Mbit/s all along, now linked at a gigabit.

The install ran, and the service refused to start. The bridge's ports must carry no address,
and the adapter had one: an IPv6 address the kernel gave it by itself, because it had been
brought up by hand a few minutes earlier to read its link. The refusal was the design working.
The install's network settings take effect at boot, so the Pi rebooted, came back over its
Wi-Fi, and the bridge was up and forwarding.

Then the bridge was found with addresses of its own: a link-local one, and two global ones
from the router's advertisements on the line. A box that is meant to be a wire was answering on
it. The namespace tests had never seen it, because nothing in them advertises a router. A new
test now says the bridge has no IPv6 address at all, not even link-local; it failed, IPv6 was
switched off on the bridge, it passed, and a ping over IPv6 still crossed.

The measurements, with a machine behind each port so the Pi only forwards:

- **With no link applied, the box is a wire:** 933 and 940 Mbit/s of TCP, one way and the other.
- **Delay is exact:** 150 ms each way added 300.0 ms to the round trip, give or take a fraction.
  London to Sydney, from the presets, measured 280.6 ms: the 278 promised plus the line's own 2.
- **Loss is accurate and directional:** 2% asked, 2.02% and 1.93% measured, none the other way.
- **A bandwidth holds:** 50 Mbit/s carried 47.5 of TCP.
- **The ceiling, through 150 ms each way:** 760 Mbit/s towards the device without one packet
  lost on the box; about 600 the other way, above which the outgoing port's own queue starts to
  drop.

One false lead on the way: the first fast runs lost 7 to 14% and looked like the Pi. The
ports' counters said every packet entered the Pi and left it. The receiving machine's own
socket buffer was overflowing, and it did the same with no link applied at all. Count at the
box, not at the receiver.

The owner did not pick any of the three. They sent a sketch of their own instead: a green board
with an angry face, a red cape, a blue ring, cables draining from its fangs into packets. It
became proposal D, drawn by hand like the others, with one change: the sketch carried the board
maker's fruit, a trademark, and the logo shows a generic board. D's favicon, just the face, the
fangs and three cables, still reads at 16 pixels, and it is now the page's icon.

## 2026-10-11 — A router's first visit

The token had to go. A 64-digit secret generated at install, copied off the box and pasted into
every browser and every agent's configuration, is a developer's idea of convenience. The owner
asked for a home router's instead: the box ships with no credentials, and the first visit to its
page asks for a user name and a password, twice. After that, people and agents sign in with the
same account.

People get a session cookie the page cannot read, so the browser no longer keeps a secret any
script could find. Agents send HTTP Basic on every call, which every HTTP client already does, so
the API stays as stateless for them as it was. The password is stored as a salted scrypt hash. A
verified pair is remembered in memory, so a Pi does not spend fifty milliseconds hashing on every
poll. The MCP on the box calls the API in process with a credential made at start and never
written down, and `/mcp` takes Basic only, never the cookie. A page from another site could make
a signed-in browser send the cookie, but never the password.

The router's reset button became `sudo wanpire account set` and `reset`, run over SSH. The
server reads the account file again when it changes, so a new password counts from the next call,
without a restart.

That SSH path caught a bug on its first real run. A password piped into `ssh` from PowerShell
arrived with three invisible bytes in front of it: a UTF-8 byte-order mark. The account was set,
and nothing could sign in to it. The code stripped the line ending but not the mark. It strips
both now, with a test that feeds it exactly what PowerShell sends.

## 2026-10-11 — Saying what the box is doing

The page said what it had applied in a message line, "Applied: london:generic to
los-angeles:generic.", which the next action replaced and no other tab ever saw. Now the header
band says it, under the logo: `london:generic <> los-angeles:generic`, or `no link`. The band
itself is a calm pastel while the line is a plain wire, and turns the wine red only while a link
is applied, so you can tell from across the room. To make that true for every viewer, the API now
remembers which ends it applied and forgets them the moment the engine reports nothing applied,
whoever cleared it.

A lease used to last only while its holder kept calling: right for an agent, wrong for a person
who wants the link for the afternoon. A lease can now be asked for a length, from 10 minutes to
a week, or until released. It needs no calls and survives closing the page, and the box's own
dead-man timer is set to its end. A lease until released has no dead-man at all: only a release,
ending it by hand, or a reboot clears it. The Broker page shows what is left.

Smaller things the owner asked for: Endpoints moved next to Settings, each place now opens to
its channels and their figures, and Counters is called Traffic.

## 2026-10-11 — A hotspot of its own

A headset joins Wi-Fi, not a cable. So far that meant an access point behind wanpire, one more
box on the bench and one more hop wanpire did not control. The owner plugged a USB Wi-Fi adapter
into the Pi and asked for wanpire to be the access point itself.

The adapter was the first surprise. It was sold as a Wi-Fi 6 stick and assumed to be the chip
most of those use, with a well-known out-of-tree driver. That driver's list of USB ids did not
have it. Upstream Linux's did, in another file: the chip is an RTL8832AU, which the kernel drives
only from versions well after the Pi's 6.8. A backport of that upstream driver builds for older
kernels through DKMS, and lists it. wanpire references it and ships none of it: it is GPL code,
and it is someone else's to keep up to date.

The second surprise was the build. The driver's Makefile runs one compiler per core but one, and
three compilers on a 1 GB Pi with no swap left nothing for anything else. The box kept answering
ping and opened TCP connections, but SSH never said hello. Nothing was killed; the kernel just
kept evicting pages and reading them back. The install's driver step now builds with one
compiler on a small box.

The page got what the owner sketched: the Adapters page has two drop-downs, inbound and outbound,
and picking a Wi-Fi adapter in either shows the network name and password below it. Save checks
them by the usual Wi-Fi rules (a name of 1 to 32 bytes, a password of 8 to 63 printable
characters) and refuses one adapter in both roles. The box then takes the line down and sets it
up again with the new roles, without a restart, so nobody is signed out; it refuses while
someone holds the link, and puts the old roles back if the new ones do not come up. The access
point is `hostapd`, on 5 GHz channel 36, WPA2 and WPA3 both accepted. The network name goes to
`hostapd` in hexadecimal, so a quote or a line break in it cannot become a setting of its own.

## 2026-10-12 — The stick works, and learns which way it faces

The owner switched the Pi off and on again, and the driver was built a second time, now with one
compiler and, as a guard, a temporary swap file on the SD card. Ten minutes, never short of
memory, SSH answering all along; the swap was barely touched and is gone again. The first build
had not failed for want of anything but restraint.

The adapter then did what was asked of it. wanpire's own access-point code put it on channel 36
at 80 MHz with WPA2 and WPA3, the Pi's built-in radio saw the beacon, and it stayed up for an
hour, checked every minute, without a word from the driver. The only kernel messages were the
Pi's: twice, a brief undervoltage. Two USB adapters draw on one small supply, and that is worth
a better supply before anyone measures throughput.

Meanwhile the owner changed what a Wi-Fi adapter is for. Picked as outbound, it is the access
point the device joins, in either mode. Picked as inbound, it is an ordinary Wi-Fi client of the
network named under the drop-down, so the box itself can reach the world without a cable, in
router mode only. A Wi-Fi client cannot be a bridge port: the access point it joins drops frames
from any address but the client's own. The ways around that (a four-address link that only some
access points accept, or proxy ARP with a DHCP relay that loses broadcast, multicast and IPv6)
were set aside; the owner confirmed it.

The client's hard part was not joining but keeping out of the way. On the bench it joins the same
network the box is controlled over, so its default route must lose to the control adapter's, it
must not answer ARP for the control adapter's address (or the network would learn that address
at the wrong card, and the session would break the moment the client left), it must not pick up
IPv6 from a router advertisement, and no DHCP hook may rewrite the name servers. wanpire runs
`wpa_supplicant` and `dhcpcd` itself, for that one adapter, and routes the line's traffic out
through it by a table of its own. On the Pi it joined in eighteen seconds at Wi-Fi 6 rates,
pinged its gateway, and left again, while the SSH session over the built-in radio carried on as
if nothing had happened. A timer had been set to switch the adapter off had it not.
