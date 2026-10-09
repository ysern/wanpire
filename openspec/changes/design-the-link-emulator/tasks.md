## 1. The box

- [x] 1.1 Update Ubuntu Server 24.04 on the Pi (no release upgrade); install iproute2, iperf3, python3-venv, ethtool, nftables tools, sysstat
- [x] 1.2 Search GitHub and PyPI for the name "wanpire" and record any clash

## 2. The spike

- [x] 2.1 Namespace test bed: two ends and a bridge, netem per direction, scripts in `spikes/scripts/`
- [x] 2.2 Delay and jitter accuracy at 20 to 300 ms round trip
- [x] 2.3 Loss, burst loss, duplication and reordering accuracy
- [x] 2.4 Netem-Q: default queue against a queue sized from delay and rate
- [x] 2.5 Throughput and CPU, with and without long netem queues
- [x] 2.6 The on-board port, router-with-NAT, from a workstation on the LAN, with a dead-man timer
- [ ] 2.7 The USB adapter, bridge mode, two wired segments (needs the adapter plugged in; the hardware run)

## 3. Calibration sources

- [x] 3.1 Find public city-to-city and access-link measurements
- [x] 3.2 Read each one's licence; classify as redistributable or read-only

## 4. The design

- [x] 4.1 `design.md`: engine, presets, modes, adapters and roles, broker, REST/UI/MCP, install
- [x] 4.2 Record assumptions and the owner's open items in `docs/open-questions.md`
