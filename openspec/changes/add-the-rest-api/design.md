## Context

D8 of `design-the-link-emulator/design.md` describes the server: one process, three faces, one
token, listening on the control address. This change builds the REST face; the web UI and the
MCP are changes of their own, both clients of it.

## Goals / Non-Goals

**Goals:** the routes, the token, the ticket, the errors, the lease driving the dead-man, a
slow tick, `wanpire serve`.

**Non-Goals:** the web UI's pages; the MCP; scenarios; changing the adapter mapping through the
API (it needs the lease and a careful teardown; later); the systemd unit and the token's
generation (the install, B4).

## Decisions

### R1. An application factory with its parts passed in

`create_app(engine, broker, config, token, list_adapters)` builds the app. The server wires the
real engine (outbound's control adapter refused, D1), a broker whose `on_clear` clears the
outbound adapter, the loaded configuration and the token file. The tests pass a recording
engine and a broker with a fake clock. Plain (non-async) route functions: FastAPI runs them in a
thread pool, and the broker holds its lock.

### R2. The ticket in a header, errors as JSON

`X-Wanpire-Ticket` carries the ticket on every call that needs one, so a route's body is only
about the link. Errors are `{"error": "<sentence>"}`:

| Status | When |
|---|---|
| 401 | no token, or a wrong one |
| 404 | an unknown ticket (expired from the queue, never issued) |
| 409 | a change by a ticket that does not hold the lease (names the holder) |
| 410 | the ticket's lease ended without it (expired, or ended by hand, with why), said once |
| 422 | an invalid link, preset or end |
| 500 | the engine failed (the `tc` error is in the sentence) |

Not taken: the ticket as a bearer token (it would replace the box's token, which every route
needs); a cookie (agents do not keep them).

### R3. The lease drives the dead-man

`PUT link` applies with `lifetime_s = lease TTL`; a poll by the holder renews the dead-man for
the same TTL when a link is applied. A holder that keeps polling keeps its link; one that stops
loses its lease and its link on the same schedule, the engine's dead-man firing even if the
server has died.

### R4. A slow tick

A background task calls `broker.status()` every 5 s, so an expired lease is cleared and passed
on without waiting for someone to call.

### R5. `wanpire serve`

uvicorn, one worker (the broker is in memory), on the control adapter's IPv4 address, read with
`ip -j -4 addr show dev <control>`; `--host` overrides it (for a test bed). It refuses to start
without `/etc/wanpire/token`, saying how to make one (`openssl rand -hex 32`, mode 0600) until
the install does it.

Not taken: listening on all addresses (D8: control only).

## Risks / Trade-offs

- **One worker** is one process for the web UI, the API and the MCP. → They are idle between
  calls; the work is the kernel's.
- **Plain HTTP on the control network.** → The token is the only protection; the README says
  the control network should be trusted, and a reverse proxy can add TLS.
