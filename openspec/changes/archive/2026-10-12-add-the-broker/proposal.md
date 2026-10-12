## Why

One link, many drivers: a person at the web page, an agent over MCP, a script over REST. If two
change the link at once, neither measures what it asked for. The design (D7) put a broker in
the core, under the REST API, so every way in sees one holder and one queue. The REST API, the
web UI and the MCP all build on it, so it comes first.

## What Changes

- **A broker** (`broker.py`, no I/O, its clock injected): a client asks for the link with who
  it is and its purpose and gets a ticket. A free link gives it a **lease**; otherwise it is
  **queued** in order of arrival.
- **TTLs**: a queued request lives 60 s without a poll; a lease 120 s without a call. Both are
  configuration. An expired request leaves the queue; an expired lease passes to the next.
- **The link is cleared between holders**: whenever a lease ends (released, expired, or ended
  by hand), the broker calls the engine's clear before the next holder gets it.
- **Only changes need the lease.** The broker checks a ticket before a change and renews the
  lease when it does; reading needs no ticket.
- **A lease can be ended by hand** (a person at the web UI, after a confirmation); the holder is
  told why on its next call.
- **Status**: the holder, its purpose, since when, when its lease runs out, and the queue.

## Decided and assumed

Decided by the design (D7): leases not locks, a queue in order of arrival, TTLs as
configuration, cleared between holders, the broker in the core. Assumed here (also in
`docs/open-questions.md`): the broker hands out an opaque random ticket and the client keeps
it; a queued client is granted the lease the moment the link frees, and its lease's TTL starts
then; the broker's state lives in memory, so a restart of the server ends every lease (and the
boot-time clear makes the line clean anyway).

## Capabilities

### New Capabilities

- `broker`: leases, the queue, their TTLs, ending a lease by hand, and the status.

### Modified Capabilities

None.

## Impact

- New `src/wanpire/broker.py` and `tests/unit/test_broker.py`. No dependency, no root.
