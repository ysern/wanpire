## Context

D7 of `design-the-link-emulator/design.md` describes the broker; this records what is decided
on top of it.

## Goals / Non-Goals

**Goals:** the broker as a plain object, testable without sleeping; leases, the queue, TTLs,
ending by hand, status.

**Non-Goals:** how a ticket travels over HTTP and MCP (the REST API change); persistence.

## Decisions

### K1. Tickets, not identities

`request(who, purpose)` returns an opaque random ticket (128 bits, hex). `who` and `purpose` are
shown in the status but prove nothing; the ticket is what a client presents. Behind one bearer
token for the whole box (D8), names are labels, and the ticket keeps two clients with the same
label apart.

Not taken: the client chooses its own id (two agents both called "agent" would share a lease).

### K2. Time is a function, and the broker settles it on every call

The clock (`time.monotonic` by default) is injected. Every public call first settles what time
has done: drops queued requests past their TTL, ends an expired lease (clearing the link) and
grants the next. No thread or timer runs inside the broker. The REST server calls `status()` on
a slow tick too (a later change), so an expired lease is cleared even when nobody calls; the
engine's own dead-man (120 s) is the backstop until then.

Not taken: a background thread (harder to test; the dead-man already guards the line).

### K3. Granted on release, not on the next poll

When the link frees, the head of the queue holds the lease at once and its lease TTL starts;
its next poll learns it. If it has died, its lease expires after the lease TTL like anyone's.
This keeps one rule ("a lease ends after its TTL without a call") rather than two.

### K4. Clearing is a callback, and a failure does not keep the link

The broker takes `on_clear`, which the server wires to `Engine.clear` on the outbound adapter.
If it raises, the broker still ends the lease and passes it on, and reports the error in the
status (`last_clear_error`): a stuck lease is worse than a reported failure, and the dead-man
still clears the line.

### K5. In memory

A restart ends every lease. The service clears every impairment at boot (D3), so nobody keeps
a link through a restart. A client whose ticket is unknown is told to ask again.

### K6. One lock

Every public method holds one `threading.Lock`: FastAPI runs plain functions in a thread pool.

## Risks / Trade-offs

- **A lease outlives a silent holder by up to its TTL** (120 s). → Configurable; the skill tells
  agents to release as soon as they are done.
