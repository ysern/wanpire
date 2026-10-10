# Spike: a transparent bridge with netem on a Raspberry Pi 4

**Status:** done, 2026-10-10. Namespaces, the on-board port, and the hardware run (bridge mode, the USB adapter, two wired segments) measured.

## Question

Is a Linux bridge with `tc netem` on each direction accurate enough, and fast enough, on a
Raspberry Pi 4 (1 GB) to emulate a long internet link at the rates a video stream needs?
Where does the Pi stop keeping up?

## Why it matters

Everything wanpire is rests on netem. If netem on this board is inaccurate, or tops out
below a few tens of Mbit/s with long queues, the design has to change (another board, XDP,
or a different shaper) before any code is written.

## Rests on

- Linux 6.8 (Ubuntu's `raspi` kernel), `sch_netem` as a module, iproute2 6.1.
- netem's behaviour as documented in `tc-netem(8)`.

## Method

All scripts are in [`scripts/`](scripts/), run on the Pi as root.

1. **Accuracy, in namespaces** ([`testbed.sh`](scripts/testbed.sh)): three namespaces, `wp-a` and
   `wp-b` as the two ends and `wp-br` holding a bridge over two veth pairs. No address on the
   bridge. Direction a→b is netem on `b1`'s egress, b→a on `a1`'s egress: the same shape as
   the real box, where each direction is the egress of the port it leaves by.
   - delay and jitter: `ping` 500 packets at 10 ms ([`delay.sh`](scripts/delay.sh));
   - loss, loss bursts, duplication, reordering: a sequenced UDP probe, 10,000 packets of
     200 bytes at 1,000 per second ([`seq.py`](scripts/seq.py), [`seq.sh`](scripts/seq.sh)), and
     `iperf3 -u` at 10 Mbit/s ([`udp.sh`](scripts/udp.sh));
   - throughput and CPU: `iperf3` TCP and UDP one way, `mpstat` over the run
     ([`tput.sh`](scripts/tput.sh)).
2. **Netem-Q:** the same UDP stream through a long delay, with netem's default queue and with a
   queue sized from delay × rate.
3. **The real port, router-with-NAT** ([`rig.sh`](scripts/rig.sh)): a workstation on the LAN
   sends to the Pi's Ethernet address; nftables forwards two test ports, and only those, to a
   target namespace behind a veth pair; netem sits on the veth ends. The workstation runs the
   clients (`iperf3`, and [`udpping.py`](scripts/udpping.py), a UDP echo prober, since ICMP
   cannot be port-forwarded). A dead-man timer (`systemd-run --on-active`) removes the rig
   whatever happens.

**What the namespaces measure and what they do not.** veth pairs cost CPU in the kernel's
forwarding path and netem costs what it costs, so the namespaces show netem's accuracy and its
per-packet price. They do not show a real NIC's interrupts, the USB stack's cost, or the
USB adapter's own buffering. The traffic generators also run on the same four cores, so every
throughput figure below is a *floor* for what the Pi can forward. The USB adapter is measured
in the hardware run, later.

## Kill or pivot signal

- Fixed delay more than 1 ms off what was asked, or loss more than 20% off it over 10,000
  packets: pivot away from netem.
- The Pi unable to forward 50 Mbit/s of 1,200-byte packets through 150 ms of delay each way:
  pivot to another board.

Neither fired.

## Findings

1. **Fixed delay is exact.** Asked 20, 100, 200 and 300 ms round trip; measured 20.125,
   100.126, 200.124, 300.127 ms average, with a spread (mdev) of 0.005 to 0.011 ms. The
   0.12 ms on top is the test bed's own round trip (0.089 ms without netem).
2. **Jitter follows the distribution asked for**, and the default is uniform. ±10 ms each way:
   uniform gives a round-trip stdev of 8.3 ms (theory 8.2), `distribution normal` 14.3 ms
   (theory 14.1).
3. **Jitter reorders packets, a lot.** ±10 ms of uniform jitter at 1,000 packets per second put
   7,173 of 10,000 packets out of order. Real paths rarely do that. Adding netem's `rate`
   keeps packets in order (0 of 10,000), at the price of a different delay distribution
   (average 103.8 ms for 100 asked, stdev 11.2 instead of 14.3), since a packet now waits for
   the one before it.
4. **Random loss is accurate:** 1% gave 0.88% and 1.12%, 5% gave 4.95% and 5.06%, 0.1% gave
   0.07%, all within two standard deviations of a binomial draw.
5. **Burst loss: use the Gilbert-Elliott model.** `loss gemodel 1% 30% 100% 0%` (expected 3.2%
   loss in bursts averaging 3.3 packets) gave 2.8% in bursts of 3.2.
6. **Correlated loss is broken.** `loss 2% 25%` (2% with 25% correlation) lost 1 packet in
   10,000, and 0 on a second run; plain `loss 2%` lost 1.79%. The engine must never emit
   netem's loss correlation.
7. **`reorder` needs a `gap`.** `delay 20ms reorder 5% 50%` reordered nothing; with `gap 5` it
   did. Duplication is accurate (1% gave 1.02%).
8. **`tc qdisc replace` merges with what was there.** Replacing a netem that had `reorder` with
   one that did not left the reorder in place. The engine deletes and re-adds, or always
   states every parameter.
9. **Netem-Q is real.** 100 Mbit/s through 150 ms one way with netem's default limit of 1,000
   packets lost 25.3% (netem's own drop counter: 33,925 packets); the arithmetic predicts
   about 24%, since the queue must hold 150 ms × ~8,700 packets/s ≈ 1,300 packets. With
   `limit 2000`: no loss. The engine sizes the limit from the delay, the jitter and the rate.
10. **Throughput, a floor:** with both traffic generators on the Pi, it moved 1,400-byte UDP at
    about 54,000 packets/s (610 Mbit/s) without netem and about 37,000 packets/s (420 Mbit/s)
    with 150 ms of netem delay and a 10,000-packet queue; 64-byte packets went 60,000/s and
    39,000/s. One core was at 95–100% (the sender's, which also runs the forwarding in its
    own context on veth); the four cores together were 35–50% idle. A 50 Mbit/s video stream
    is about 4,500 packets/s, an order of magnitude below.
11. **Memory is not the limit:** a 10,000-packet queue at 420 Mbit/s left 230 MB free and
    610 MB available on the 1 GB board.
12. **Jitter without reordering makes bursts.** With jitter and `rate`, packets that waited for a
    slow one leave together. At 300 Mbit/s the *receiver's* socket buffer overflowed (4.4% lost,
    all in `UdpRcvbufErrors`, none by netem). This is what jitter does to a real receiver too,
    but it means a loss figure must say who dropped the packet: wanpire reports netem's own
    drops separately from what the endpoints see.
13. **The real port, through NAT, adds exactly what is asked on top of the line's own delay.**
    The home LAN between the workstation and the Pi's port is not a wire (it crosses a
    wireless mesh backhaul): 3.9 ms minimum, 6.4 ms median, 22 ms at the 99th percentile.
    With 50 ms each way the minimum rose by 100.03 ms; with 150 ms each way by 300.07 ms; 2%
    loss each way gave 4.1% round-trip loss (expected 3.96%). That LAN carried only 55 and 21
    Mbit/s, so it cannot measure the Pi's ceiling; that waits for two wired ports.

**The hardware run** (2026-10-10): the installed box in bridge mode, the on-board port and an
ASIX AX88179B USB 3 adapter, each on its own gigabit segment. The two ends were two Linux
machines, one behind each port, so the Pi only forwarded. Everything went through the REST API
under a lease, as a client would.

14. **Clean, the box is a wire:** TCP at 933 and 940 Mbit/s, one way and the other; UDP at
    818 Mbit/s with nothing dropped on the box. The base round trip is 1.8 to 2.5 ms. The kernel
    drives the adapter with `cdc_ncm`, which reports "half duplex": cosmetic, since it carries
    the line rate both ways.
15. **Delay on the real ports is as exact as in namespaces.** 50 and 150 ms each way raised the
    minimum round trip by 100.15 and 300.15 ms and the mean by 100.00 and 299.97 ms, mdev under
    1 ms. The preset London to Sydney (139 ms each way, ±1.9 ms) measured 280.6 ms on average,
    278 plus the line's own 2.
16. **Loss is accurate, and goes the right way:** 2% *up* gave 2.02% from the device's side and
    none back; 2% *down* gave 1.93% towards it and none away; over 31,000 packets each. wanpire's
    `dropped` counter matched what the receiver missed.
17. **A bandwidth holds:** 50 Mbit/s each way carried 47.4 and 47.5 Mbit/s of TCP goodput.
18. **The ceiling under 150 ms each way is the *up* direction's, about 600 Mbit/s.** *Down*
    (netem as the outbound port's root qdisc) forwarded 760 Mbit/s with not one packet lost on
    the box. *Up* (netem on the `ifb` that outbound's ingress redirects to, then the bridge, then
    inbound's own egress) lost nothing at 600 Mbit/s, 3% at 700 and 13% at 800, every drop in
    inbound's default `fq_codel`; netem dropped none, softnet none, and with the link clear
    818 Mbit/s crossed the same queue without a drop. netem releasing the `ifb`'s packets in
    bursts that overrun a 5 ms CoDel target is the likely reading, not a proven one. A video
    stream of 50 Mbit/s is a twelfth of it. Recorded as an open question.
19. **Forwarding costs one core.** All of it ran in softirq on CPU 0 (70% averaged over a 12 s
    window at 540 Mbit/s, the other three cores idle): one receive queue per adapter, no RPS. 300
    MB of 900 used with 18,750-packet queues.

## Findings in full

- **Disproven along the way:** the first loss runs reported `out_of_order = 0` for everything,
  including heavy jitter. The field was being read from iperf3's client summary, which does not
  carry it. The sequenced probe was written because of that, and showed 72% reordering.
- **A process outlives its namespace.** Deleting a namespace left its `iperf3 -D` running in
  no namespace at all. The test bed now kills a namespace's processes before deleting it, and
  the engine will track what it starts.
- **`pkill -f <name>` over SSH can kill your own session**, because the remote shell's command
  line contains the name. Kill by PID.
- **A dual-homed Pi answers on its lowest-metric route.** With Wi-Fi and Ethernet on the same
  LAN, replies to an SSH session that arrived over Wi-Fi left by Ethernet (metric 100 against
  600). Any impairment on the Ethernet port without a classifier would have slowed the control
  session. In bridge mode the ports carry no address, so this goes away; in a test rig on a
  live LAN it does not.
- **Why the Wi-Fi cannot be one side of a bridge.** A Wi-Fi client sends frames with three
  addresses: the access point accepts only frames from the MAC address that associated, so a
  bridge forwarding other devices' frames over it is dropped. (Four-address WDS mode would
  work, but needs the access point's cooperation.) And bridging the Wi-Fi and the Ethernet when
  both sit on the same LAN would join the LAN to itself in a loop. The bridge needs two wired
  ports on separate segments.

- **The bridge took addresses of its own.** Installed, `wpbr0` came up with a link-local IPv6
  address and two global ones from the line's router advertisements: the box was reachable, and
  talking, on the line it should be invisible on. The namespace test checked global addresses
  only, and its bed sends no advertisements. Fixed by switching IPv6 off on the bridge itself
  (it still forwards IPv6 frames, checked by a ping across it), with a test that the bridge has
  no IPv6 address at all.
- **A port brought up by hand before the install gets an address.** Bringing the USB port up to
  read its link let the kernel give it an IPv6 address by autoconfiguration; `wanpire up` then
  refused it, as designed (A29). A reboot applied the install's netplan drop-in and the bridge
  came up. Read a link with `ethtool` on a port that is down, or reboot after the install.
- **Where a loss happened is read off counters, not the receiver.** The first 600 Mbit/s runs
  lost 7 to 14% *up*, which looked like the box. The ports' counters showed every packet in and
  out of the Pi; the receiving machine's `UdpRcvbufErrors` had them, and it lost as much with no
  wanpire link at all. Only the runs above 600 Mbit/s lost on the box (finding 18).

Raw output of every run is in the build journal's entries for 2026-10-09 and 2026-10-10.
