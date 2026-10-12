## ADDED Requirements

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
