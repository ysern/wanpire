## Why

The design (D8) makes one REST API the engine's only interface: the web UI is its client, and
the MCP's tools call it over HTTP, so one token check and one broker apply to every way in.
The engine, the presets, the modes and the broker exist; nothing serves them yet.

## What Changes

- **A FastAPI application** under `/api/v1`, every route behind **one bearer token**:
  - `GET status`: the mode, the outbound adapter, the link's counters, the broker's holder and
    queue;
  - `POST lease` (ask), `POST lease/poll`, `DELETE lease` (release), `DELETE lease/holder`
    (end the current lease by hand, with a reason);
  - `GET link`, `PUT link` (raw figures, or two ends), `DELETE link`: changes need the lease's
    ticket (`X-Wanpire-Ticket`);
  - `GET endpoints`, `GET endpoints/{id}`, `POST preview`, `GET adapters`.
- **The lease drives the dead-man**: a link is applied with the lease's TTL as its lifetime,
  and each call of the holder renews both.
- **A slow tick** settles the broker every few seconds, so an expired lease is cleared even when
  nobody calls.
- `wanpire serve`: uvicorn on the control adapter's address only, the token read from
  `/etc/wanpire/token`.
- Tests with FastAPI's test client against a recording engine; no root.

## Decided and assumed

Decided by the design (D7, D8): the REST API is the only way in; one bearer token; the server
listens on the control address only; changes need the lease. Assumed here (also in
`docs/open-questions.md`): the ticket travels in a header; errors are JSON `{"error": ...}` with
401, 404 (unknown ticket), 409 (not the holder), 410 (lease ended, with why) and 422 (invalid
link or preset); the slow tick runs every 5 s.

## Capabilities

### New Capabilities

- `rest-api`: the routes, the token, the ticket, the errors, and the lease driving the dead-man.

### Modified Capabilities

None.

## Impact

- New `src/wanpire/api.py`; `cli.py` gains `serve`.
- Runtime dependencies: `fastapi`, `uvicorn`; `httpx` for tests.
