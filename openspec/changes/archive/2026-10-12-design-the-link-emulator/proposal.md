## Why

Software that talks over the internet is mostly tested over a LAN, where the round trip is a
millisecond and nothing is lost. It then meets a 300 ms satellite hop or a 4G cell losing 3%
of its packets, and behaves in ways nobody saw. Commercial link emulators exist but cost money
and are not scriptable by an AI agent. Linux has had the mechanism, `tc netem`, for twenty
years; what is missing is a small box that anyone can build, that describes a link in words a
developer uses ("London on fibre to Los Angeles on 4G"), and that a person or an agent can
drive safely.

Before any of it is built, two things had to be known: whether netem on a Raspberry Pi 4 is
accurate and fast enough, and which public measurements wanpire may ship.

## What Changes

This change is the design. It adds no code and no requirement yet:

- **A spike** on the Pi, [`spikes/netem-on-a-pi.md`](spikes/netem-on-a-pi.md): netem's accuracy and
  the Pi's throughput, in network namespaces and through the on-board port. Fixed delay is
  exact to 0.04 ms; loss is within sampling error; the Pi forwards at least ~37,000 packets/s
  through long netem queues while generating the traffic itself. It found five netem traps
  the engine must close.
- **A study** of public calibration data and its licences,
  [`spikes/calibration-sources.md`](spikes/calibration-sources.md): a CC BY 4.0 table of
  cloud-region round trips and M-Lab's CC0 data may be shipped; RIPE Atlas, WonderNetwork,
  Ookla and Cloudflare Radar may only be read.
- **The design,** [`design.md`](design.md): the engine, endpoint presets and how two combine,
  the two modes, adapters and their roles, the broker, the REST API with the web UI and the MCP
  on top, and the install.

What is decided and what is assumed: the owner decided the two-endpoint presets with channels,
the city-pair table first with the formula as fallback, Python with the MCP SDK, FastAPI and
pyroute2, the adapter roles, the broker with leases and a queue, the skill, and the web UI's
plain style. Everything else in `design.md` is the design's own choice, and the ones that are
assumptions are listed in [`docs/open-questions.md`](../../../docs/open-questions.md).

## Capabilities

### New Capabilities

None in this change. The next change, `build-the-link-engine`, adds the first ones
(`link-model`, `link-engine`) with their requirements, test-first.

### Modified Capabilities

None.

## Impact

- New: this change's documents and the spike's scripts.
- No code, no dependency, no API yet.
