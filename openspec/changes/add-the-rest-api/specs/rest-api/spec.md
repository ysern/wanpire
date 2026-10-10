## Purpose

The one way into wanpire's engine, for people (through the web UI), agents (through the MCP)
and scripts alike, so that one token check and one broker apply to all of them.

## ADDED Requirements

### Requirement: Every route needs the token

Every route under `/api/v1` SHALL require `Authorization: Bearer <token>` with the box's token,
compared in constant time, and SHALL answer 401 without it.

#### Scenario: No token
- **WHEN** `GET /api/v1/status` is called without a token
- **THEN** the answer is 401 and nothing else is said

#### Scenario: The right token
- **WHEN** `GET /api/v1/status` is called with the token
- **THEN** the answer is 200 with the mode, the outbound adapter, the link and the broker's holder and queue

### Requirement: Asking, polling and releasing the lease

`POST /api/v1/lease` with `who` and `purpose` SHALL return a ticket and whether it holds the
lease or its queue position. `POST /api/v1/lease/poll` and `DELETE /api/v1/lease`, with the
ticket in `X-Wanpire-Ticket`, SHALL poll and release. An unknown ticket SHALL be answered 404;
a lease that ended without its holder SHALL be answered 410 with why, once.

#### Scenario: Ask, queue, release, pass on
- **GIVEN** client A holds the lease and B is queued
- **WHEN** A releases it and B polls
- **THEN** B holds the lease and the link has been cleared

#### Scenario: Ended by hand
- **GIVEN** A holds the lease
- **WHEN** `DELETE /api/v1/lease/holder` is called with the reason "the lab needs the line", and then A polls
- **THEN** A's poll is answered 410 with "the lab needs the line"

### Requirement: Changing the link needs the lease

`PUT /api/v1/link` and `DELETE /api/v1/link` SHALL need the holder's ticket, and SHALL be
answered 409 naming the holder otherwise. `PUT` SHALL accept either raw figures
(`{"down": {...}, "up": {...}}`) or two ends (`{"near": "london:consumer-fibre", "far":
"tokyo"}`), and SHALL answer 422 with the reason for an invalid one. Reading the link SHALL need
no ticket.

#### Scenario: Apply from two ends
- **GIVEN** A holds the lease
- **WHEN** A puts `{"near": "london", "far": "new-york"}`
- **THEN** the engine applies the same link `wanpire preview london new-york` gives, on the outbound adapter
- **AND** the answer carries the link and how it was worked out

#### Scenario: Apply without the lease
- **GIVEN** A holds the lease for "soak"
- **WHEN** B puts a link
- **THEN** the answer is 409 naming A and "soak", and the engine is not called

#### Scenario: An invalid link
- **WHEN** the holder puts a link with 120% loss
- **THEN** the answer is 422 naming `loss_pct`

### Requirement: The lease drives the dead-man

A link SHALL be applied with the lease's TTL as its dead-man lifetime, and every poll by the
holder SHALL renew the dead-man while a link is applied.

#### Scenario: The holder polls
- **GIVEN** A holds the lease and has applied a link
- **WHEN** A polls
- **THEN** the engine's dead-man for the outbound adapter is renewed for the lease's TTL

### Requirement: Presets, previews and adapters can be read

`GET /api/v1/endpoints` SHALL list the shipped endpoints with their channels,
`GET /api/v1/endpoints/{id}` SHALL return one preset document, `POST /api/v1/preview` with
`near` and `far` SHALL return the link and its account without changing anything, and
`GET /api/v1/adapters` SHALL list the adapters with their roles.

#### Scenario: Preview changes nothing
- **WHEN** `POST /api/v1/preview` is called with `near` "london:consumer-fibre" and `far` "los-angeles:mobile-4g"
- **THEN** the answer carries the link and the path's origin, and the engine is not called

### Requirement: The server listens on the control address only

`wanpire serve` SHALL listen on the control adapter's IPv4 address unless told another, and
SHALL refuse to start without a token.

#### Scenario: No token file
- **GIVEN** no token at `/etc/wanpire/token`
- **WHEN** `wanpire serve` starts
- **THEN** it exits with a message saying the token is missing and how to make one
