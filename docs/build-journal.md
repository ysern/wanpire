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
