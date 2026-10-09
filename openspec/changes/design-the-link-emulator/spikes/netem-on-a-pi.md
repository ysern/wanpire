# Spike: a transparent bridge with netem on a Raspberry Pi 4

**Status:** done, 2026-10-10. Namespaces and the on-board port measured; the USB adapter is still to come.

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

Raw output of every run is in the build journal's entries for 2026-10-09 and 2026-10-10.
