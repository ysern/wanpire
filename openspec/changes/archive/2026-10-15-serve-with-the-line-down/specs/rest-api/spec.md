## MODIFIED Requirements

### Requirement: The status names the link applied

`GET /api/v1/status` SHALL carry `applied`: the two ends with their channels resolved when the
link was applied from ends (`{"near": "london:generic", "far": "los-angeles:mobile-4g"}`),
`{"figures": true}` when it was applied from raw figures, and `null` when the engine reports
no link applied, whatever cleared it. It SHALL also carry `line`: `{"up": true}` while the mode
is set up, or `{"up": false, "missing": [...], "reason": "..."}` naming the configured line
adapters the box does not have and saying so in one sentence.

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

#### Scenario: The line is down
- **GIVEN** the server started with outbound `wlx1` not plugged in
- **WHEN** anyone reads the status
- **THEN** `line` is `{"up": false, "missing": ["wlx1"], "reason": "outbound adapter wlx1 is not plugged in"}`

### Requirement: Changing the link needs the lease

`PUT /api/v1/link` and `DELETE /api/v1/link` SHALL need the holder's ticket, and SHALL be
answered 409 naming the holder otherwise. `PUT` SHALL accept either raw figures
(`{"down": {...}, "up": {...}}`) or two ends (`{"near": "london:consumer-fibre", "far":
"tokyo"}`), and SHALL answer 422 with the reason for an invalid one. Reading the link SHALL need
no ticket. While the line is down, `PUT` SHALL be answered 409 with the line's reason and the
engine SHALL NOT be called; `DELETE` SHALL succeed, there being nothing on a missing adapter.

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

#### Scenario: Apply with the line down
- **GIVEN** the holder of the lease, and the line down for a missing outbound adapter
- **WHEN** the holder puts a link
- **THEN** the answer is 409 saying the outbound adapter is not plugged in, and the engine is not called

### Requirement: The roles can be read and changed

`GET /api/v1/roles` SHALL return the mode, the control, inbound and outbound adapters, the access
point of a Wi-Fi outbound adapter, the network a Wi-Fi inbound adapter joins, and the adapters that may be picked for inbound and
outbound: every adapter but virtual ones and the control adapter when it is Wi-Fi. It SHALL
also return `missing`: the configured line adapters the box does not have now.
`PUT /api/v1/roles` SHALL take an inbound and an outbound adapter, the network to join for a Wi-Fi
inbound one (`wifi_clients`) and an access point for a Wi-Fi outbound one (`access_points`); validate them as the configuration is validated; refuse one adapter in both roles;
then take the mode down, write the configuration and set the mode up again with it. A refused
change SHALL leave the box and the file as they were. A change SHALL be refused with 409 while a
link is applied or a lease is held. A change SHALL be allowed while the line is down, and a
change to present adapters SHALL bring the line up.

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

#### Scenario: Reading the roles with the line down
- **GIVEN** a box configured with outbound `wlx1`, which is not plugged in
- **WHEN** a client asks `GET /api/v1/roles`
- **THEN** the answer names outbound `wlx1` and lists `wlx1` under `missing`

#### Scenario: Fixing the roles with the line down
- **GIVEN** the same box, no lease held
- **WHEN** a client puts inbound `eth0` and outbound `eth1`
- **THEN** the answer is 200, the configuration names outbound `eth1`, the mode is set up with it and the status says the line is up
