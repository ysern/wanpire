## 1. The rate shaper

- [x] 1.1 Measure netem's rate against tbf in namespaces on the Pi (`spikes/rate-shaper.sh`); record in design M5
- [x] 1.2 Failing tests: `queue_ms` validation; netem rate only at the line rate under jitter; netem queue sized at the line rate; the tbf child and its burst; counters with `shaper_dropped`
- [x] 1.3 Implement in `model.py`, `netem.py`, `engine.py` until green
- [x] 1.4 Namespace scenario: one TCP flow does not fill a delay-sized queue

## 2. Configuration and adapters (no root)

- [ ] 2.1 Failing tests: each scenario of `adapter-roles` on a fixed adapter list
- [ ] 2.2 Failing tests: the adapter list from a fake sysfs tree and a recorded `iw`
- [ ] 2.3 Implement `config.py` and `adapters.py` until green

## 3. Modes (root, namespaces)

- [ ] 3.1 Namespace scenarios of `line-modes`: bridge reach, port with an address, teardown; router DHCP, NAT source, forwarding restored, twice
- [ ] 3.2 Implement `modes.py` until green on the Pi

## 4. CLI and close

- [ ] 4.1 `wanpire adapters`, `wanpire up`, `wanpire down`, with tests
- [ ] 4.2 Journal, open questions, README
