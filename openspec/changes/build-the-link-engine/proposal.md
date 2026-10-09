## Why

The design (`design-the-link-emulator`) settled how wanpire impairs a line. Nothing applies an
impairment yet. Everything else, the presets, the broker, the REST API, the web UI and the
MCP, sits on an engine that turns a description of a link into kernel state, reads it back and
clears it. That engine comes first, and it has to close the netem traps the spike found.

## What Changes

- **A link description**: per direction, delay, jitter and its distribution, random or burst
  loss, bandwidth, duplication and reordering, with validation and clear errors.
- **Its translation to netem**, closing the spike's traps: queue sized from delay and rate,
  jitter that keeps packet order unless reordering is asked, burst loss through the
  Gilbert-Elliott model and never netem's loss correlation, a reorder gap always set.
- **The engine** that applies a link to the outbound adapter (down on its egress, up on its
  ingress through an `ifb` device), replaces it whole, clears it, and reads its counters back
  with netem's own drops kept apart.
- **A dead-man**: an applied link carries a lifetime and is cleared when it runs out.
- **A first CLI**: `wanpire apply`, `wanpire show`, `wanpire clear`, on raw figures.
- Tests first: unit tests that need no root; namespace tests on Linux that never touch a real
  interface.

Not in this change, each a change of its own: endpoint presets and the city-pair table; the
bridge and router modes' setup; the broker; the REST API, web UI and MCP; the install.

## Capabilities

### New Capabilities

- `link-model`: describing a link per direction, validating it, and what each setting means.
- `link-engine`: applying, replacing, clearing and reading back a link on an adapter, safely.

### Modified Capabilities

None.

## Impact

- New Python package `wanpire` (Python 3.12, `src/` layout), with `pyroute2` as its first
  runtime dependency and `pytest` for tests.
- Needs `iproute2` (`tc`) on the box, and root for the engine.
