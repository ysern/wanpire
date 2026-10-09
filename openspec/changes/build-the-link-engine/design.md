## Context

The whole design is in `design-the-link-emulator/design.md` (D1 to D3, D9). This document
records only what this change decides on top of it.

## Goals / Non-Goals

**Goals:** a link model with validation; its translation to netem; an engine that applies,
replaces, clears and reads back a link on one adapter; a dead-man; a minimal CLI.

**Non-Goals:** presets, modes, the broker, the server. The engine is driven by figures only.

## Decisions

### E1. netem through `tc`, not pyroute2

pyroute2 0.9.6's netem support has no delay distribution table and no loss model (its
`TCA_NETEM_DELAY_DIST` and `TCA_NETEM_LOSS` are left empty), so it cannot express normal jitter
or Gilbert-Elliott loss, both of which the design depends on. The engine therefore renders each
direction as a `tc` argument list, a pure function that is tested without root, and runs it.
Counters come from `tc -s -j qdisc show` (JSON). pyroute2 remains the choice for adapters and
bridges in the next changes.

Not taken: writing the missing netlink attributes into pyroute2 (a contribution worth making
later, but not on the critical path); `tc -batch` (no gain for two qdiscs).

### E2. Commands go through a runner

Every command is an argument list handed to a runner. The real runner calls `subprocess.run`,
optionally prefixed with `ip netns exec <ns>`; the unit tests use a recording runner. This keeps
the engine's logic testable on any machine and the namespace tests honest.

### E3. Ingress through `ifb`

For the *up* direction, the engine creates `ifb-<adapter>` (truncated to the 15-character
interface name limit as `wp<hash>` when needed), adds an `ingress` qdisc on the adapter, a
`matchall` filter redirecting everything to the ifb (`mirred egress redirect`), and netem on the
ifb's root. Clearing removes the filter, the ingress qdisc and the ifb.

### E4. Replace is delete and add

Applying always deletes the root and ingress qdiscs first, then adds. A brief gap (micro-
seconds) in which the line is unimpaired is accepted; a merge with old options is not.

### E5. The dead-man is a systemd timer

`apply` with a lifetime arms a transient systemd timer (`systemd-run --on-active=<s>`) named
for the adapter that runs `wanpire clear` for it; renewing stops and re-arms it; clearing stops
it. It survives the process that applied the link. Where systemd is absent (a container, a CI
runner), the engine reports that the dead-man is unavailable, and the namespace tests run on a
host with systemd.

Not taken: an in-process timer (dies with the process, which is the case a dead-man is for).

### E6. Gilbert-Elliott from two figures

Burst loss `L` with mean burst `B` becomes netem's `loss gemodel p r 100% 0%` with `r = 1/B`
and `p = L·r / (1 − L)`, so that the bad state's share is `L` and its mean stay is `B`. The spike
measured `p = 1%, r = 30%` as 2.8% loss in bursts of 3.2, against 3.2% and 3.3 expected.

## Risks / Trade-offs

- `tc` output and options vary by iproute2 version. → JSON output; the minimum is the one in
  Ubuntu 24.04 (6.1); tests run there.
- The `ifb` redirect's CPU cost on a Pi is unmeasured. → Measured by the namespace tests'
  throughput case, against the spike's figures.
