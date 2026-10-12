# rest-api Specification

## Purpose
The one way into wanpire's engine, for people (through the web UI), agents (through the MCP)
and scripts alike, so that one account check and one broker apply to all of them.

## Requirements

### Requirement: The box has one account, made on the first visit

The box SHALL have one account, a user name and a password, kept on the box as a salted
scrypt hash and never in clear. While it has none, `GET /api/v1/setup` SHALL say so without
credentials, `POST /api/v1/setup` with `user` and `password` SHALL make it and sign the caller
in, and every other route under `/api/v1` SHALL be answered 403 saying the account must be made
first. Once the account exists, `POST /api/v1/setup` SHALL be answered 409. A password SHALL have
at least 8 characters, and a user name SHALL be 1 to 32 letters, digits, dots, dashes or
underscores; otherwise 422 with the reason.

#### Scenario: The first visit
- **GIVEN** a box with no account
- **WHEN** `POST /api/v1/setup` is called with `admin` and a password of 12 characters
- **THEN** the account is made, the answer is 201 and carries a session cookie
- **AND** a second `POST /api/v1/setup` is answered 409

#### Scenario: Before the account exists
- **GIVEN** a box with no account
- **WHEN** `GET /api/v1/status` is called
- **THEN** the answer is 403 saying the account must be made first on the box's web page

#### Scenario: A short password
- **WHEN** `POST /api/v1/setup` is called with a password of 5 characters
- **THEN** the answer is 422 naming the password's length, and no account is made

### Requirement: Every route needs the account

Every route under `/api/v1` but `setup` and `session` SHALL require the account: HTTP Basic
credentials (`Authorization: Basic ...`), which agents and scripts send with every call, or the
session cookie a browser got by signing in. A wrong or missing one SHALL be answered 401, and
the user name and the password SHALL be compared in constant time.

#### Scenario: No credentials
- **WHEN** `GET /api/v1/status` is called without credentials
- **THEN** the answer is 401 and nothing else is said

#### Scenario: Basic credentials
- **WHEN** `GET /api/v1/status` is called with the account's user and password
- **THEN** the answer is 200 with the mode, the outbound adapter, the link and the broker's holder and queue

#### Scenario: A wrong password
- **WHEN** `GET /api/v1/status` is called with the right user and a wrong password
- **THEN** the answer is 401

### Requirement: A browser signs in and out with a session

`POST /api/v1/session` with `user` and `password` SHALL set an `HttpOnly`, `SameSite=Strict`
session cookie and return the user name; `GET /api/v1/session` SHALL return the signed-in user
or 401; `DELETE /api/v1/session` SHALL end the session. `PUT /api/v1/account/password` with the
current and a new password SHALL change it and end every other session.

#### Scenario: Signing in
- **GIVEN** the account `admin`
- **WHEN** a browser posts `admin` and its password to `/api/v1/session` and then reads the status
- **THEN** the status is answered 200 on the cookie alone

#### Scenario: Signing out
- **GIVEN** a signed-in browser
- **WHEN** it calls `DELETE /api/v1/session` and then reads the status
- **THEN** the status is answered 401

#### Scenario: Changing the password
- **GIVEN** the account `admin`
- **WHEN** the password is changed with the right current one
- **THEN** the old password is refused and the new one accepted

### Requirement: The status names the link applied

`GET /api/v1/status` SHALL carry `applied`: the two ends with their channels resolved when the
link was applied from ends (`{"near": "london:generic", "far": "los-angeles:mobile-4g"}`),
`{"figures": true}` when it was applied from raw figures, and `null` when the engine reports
no link applied, whatever cleared it.

#### Scenario: Applied from two ends
- **GIVEN** the holder applied `{"near": "london", "far": "los-angeles:mobile-4g"}`
- **WHEN** anyone reads the status
- **THEN** `applied` is `{"near": "london:generic", "far": "los-angeles:mobile-4g"}`, London's default channel resolved

#### Scenario: Applied from figures
- **GIVEN** the holder applied `{"down": {"delay_ms": 40}, "up": {"delay_ms": 40}}`
- **WHEN** anyone reads the status
- **THEN** `applied` is `{"figures": true}`

#### Scenario: Cleared, by hand or by the broker
- **GIVEN** a link applied from two ends
- **WHEN** the holder clears it, or its lease ends and the broker clears it, and the status is read
- **THEN** `applied` is `null`

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

### Requirement: A lease can be asked for a length of time

`POST /api/v1/lease` MAY carry `hold`: a number of seconds from 60 to 604,800, or
`"until-released"`; without it the lease lives while used. Any other value SHALL be answered 422.
The status SHALL give the holder's and each request's `hold`, and the holder's `remaining_s`
(`null` until released).

#### Scenario: An hour
- **WHEN** A posts `{"who": "web: admin", "purpose": "demo", "hold": 3600}` to a free link
- **THEN** A holds the lease, and the status gives `hold` 3600 and `remaining_s` 3600

#### Scenario: A length out of range
- **WHEN** a request carries `"hold": 10`
- **THEN** the answer is 422 naming the range

### Requirement: The lease drives the dead-man

A link SHALL be applied with the lease's TTL as its dead-man lifetime, and every poll by the
holder SHALL renew the dead-man while a link is applied. Under a timed lease the lifetime SHALL be
the lease's remaining time; under a lease until released there SHALL be no dead-man.

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

`wanpire serve` SHALL listen on the control adapter's IPv4 address unless told another. It SHALL
start without an account, and say in its log that the account is made on the box's web page or
with `wanpire account`.

#### Scenario: No account yet
- **GIVEN** no account at `/etc/wanpire/account`
- **WHEN** `wanpire serve` starts
- **THEN** it serves, logs that the account is still to be made, and answers the first visit's setup

### Requirement: The account is set or removed on the box itself

`wanpire account set <user>` SHALL set the account, reading the password from standard input,
and `wanpire account reset` SHALL remove it, so that the next visit makes it again: the box's
reset button, for a forgotten password. They are run over SSH on the box (`ssh <box> sudo
wanpire account set admin`), which is how a forgotten password is recovered. Both SHALL need
write access to the account file, and a running server SHALL see the change on its next call,
without a restart.

#### Scenario: A new password over SSH
- **GIVEN** the account `admin`, its password forgotten
- **WHEN** `sudo wanpire account set admin` is run over SSH with a new password on standard input
- **THEN** the running server accepts the new password and refuses the old one

#### Scenario: A forgotten password
- **GIVEN** the account `admin`
- **WHEN** `wanpire account reset` is run on the box and the web page is opened
- **THEN** the page asks to make the account

### Requirement: The roles can be read and changed

`GET /api/v1/roles` SHALL return the mode, the control, inbound and outbound adapters, the access
point of a Wi-Fi outbound adapter, the network a Wi-Fi inbound adapter joins, and the adapters that may be picked for inbound and
outbound: every adapter but virtual ones and the control adapter when it is Wi-Fi.
`PUT /api/v1/roles` SHALL take an inbound and an outbound adapter, the network to join for a Wi-Fi
inbound one (`wifi_clients`) and an access point for a Wi-Fi outbound one (`access_points`); validate them as the configuration is validated; refuse one adapter in both roles;
then take the mode down, write the configuration and set the mode up again with it. A refused
change SHALL leave the box and the file as they were. A change SHALL be refused with 409 while a
link is applied or a lease is held.

#### Scenario: Reading the roles
- **GIVEN** a box in bridge mode with control `wlan0`, inbound `eth0` and outbound `eth1`, and a USB Wi-Fi adapter `wlan1`
- **WHEN** a client asks `GET /api/v1/roles`
- **THEN** the answer names inbound `eth0` and outbound `eth1`, and offers `eth0`, `eth1` and `wlan1`, not `wlan0`

#### Scenario: One adapter in both roles
- **GIVEN** the same box
- **WHEN** a client puts inbound `eth1` and outbound `eth1`
- **THEN** the answer is 422 with a message saying inbound and outbound must be different adapters, and nothing changes

#### Scenario: Outbound becomes an access point
- **GIVEN** the same box, no link applied and no lease held
- **WHEN** a client puts inbound `eth0` and outbound `wlan1` with network name `lab-ap` and a valid password
- **THEN** the answer is 200, the configuration names outbound `wlan1` with that access point, and the mode is set up again with it

#### Scenario: A Wi-Fi inbound in bridge mode
- **GIVEN** the same box, in bridge mode
- **WHEN** a client puts inbound `wlan1` with a network to join, and outbound `eth1`
- **THEN** the answer is 422 with a message saying a Wi-Fi client cannot be a bridge port, and nothing changes

#### Scenario: Inbound joins a network in router mode
- **GIVEN** a box in router mode with inbound `eth0` and outbound `eth1`, no link applied and no lease held
- **WHEN** a client puts inbound `wlan1` with the network to join `upstream`, and outbound `eth1`
- **THEN** the answer is 200, the configuration names inbound `wlan1` joining `upstream`, and the mode is set up again with it

#### Scenario: A link is applied
- **GIVEN** the same box with a link applied
- **WHEN** a client puts new roles
- **THEN** the answer is 409 with a message saying the roles change only with no link applied and no lease held
