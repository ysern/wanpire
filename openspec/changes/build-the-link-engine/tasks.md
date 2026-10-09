## 1. Package

- [ ] 1.1 `pyproject.toml` (Python 3.12+, `src/` layout, pytest), `src/wanpire/__init__.py`, an empty test run passing

## 2. Link model (no root)

- [ ] 2.1 Failing tests: a direction with no settings is no impairment; two directions independent
- [ ] 2.2 Failing tests: each refusal in "Invalid figures are refused with a reason"
- [ ] 2.3 Implement `model.py` until green

## 3. netem options (no root)

- [ ] 3.1 Failing tests: delay, jitter with `distribution normal` by default, `rate` set when jitter is set and no reordering asked
- [ ] 3.2 Failing tests: Gilbert-Elliott parameters from mean loss and burst length; never `loss p corr`
- [ ] 3.3 Failing tests: reorder always has a gap; duplicate
- [ ] 3.4 Failing tests: queue sizing, the floor of 1,000 and the 64 MB cap (32,768 packets)
- [ ] 3.5 Implement `netem.py` until green

## 4. Engine (no root, recording runner)

- [ ] 4.1 Failing tests: apply deletes then adds root netem, ingress, matchall redirect, ifb and its netem
- [ ] 4.2 Failing tests: clear removes all of it and tolerates nothing to clear
- [ ] 4.3 Failing tests: the control adapter is refused
- [ ] 4.4 Failing tests: counters parsed from `tc -s -j qdisc show` output
- [ ] 4.5 Implement `engine.py` until green

## 5. Engine in namespaces (root, Linux)

- [ ] 5.1 A pytest fixture building the spike's three-namespace bed, torn down whatever happens
- [ ] 5.2 Scenarios of `link-engine`: delay each way, replace, clear, counters
- [ ] 5.3 Scenarios of `link-model` that need packets: jitter keeps order, burst loss, queue long enough
- [ ] 5.4 Run on the Pi; record figures in the build journal

## 6. Dead-man and CLI

- [ ] 6.1 Failing tests: apply with a lifetime arms the timer; renew re-arms; clear stops it
- [ ] 6.2 Implement; namespace test for "Not renewed" and "Renewed"
- [ ] 6.3 `wanpire apply|show|clear` on raw figures, with tests
