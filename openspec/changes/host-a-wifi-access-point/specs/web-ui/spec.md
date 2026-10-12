## ADDED Requirements

### Requirement: The Adapters page sets the inbound and the outbound adapter

The Adapters / Roles page SHALL show two drop-downs, *Inbound adapter* and *Outbound adapter*,
each offering the adapters the API offers and set to the current roles. When the adapter picked
as inbound is Wi-Fi, *Network to join* and its *Password* SHALL be shown below that drop-down,
filled with the network it joins now when it has one. When the adapter picked as outbound is
Wi-Fi, the access point's *Network name* and *Password* SHALL be shown below that drop-down,
filled with its current access point when it has one. Otherwise they SHALL be hidden. *Save*
SHALL check, before sending anything, that the two adapters differ, that a Wi-Fi inbound adapter
is not picked in bridge mode, that a network name has 1 to 32 bytes, that an access point's
password has 8 to 63 printable ASCII characters and that a network to join's password has those,
or 64 hexadecimal digits, or none; and say what is wrong beside the field. Then it SHALL send the
roles and say whether the box took them. The table of every adapter, its kind, role, state and
speed SHALL stay below the form.

#### Scenario: Picking a Wi-Fi outbound adapter
- **GIVEN** the Adapters page with outbound `eth1`
- **WHEN** the person picks the Wi-Fi adapter `wlan1` as outbound
- **THEN** a network name and a password field appear below the outbound drop-down, and none below the inbound one

#### Scenario: Picking a Wi-Fi inbound adapter
- **GIVEN** the Adapters page with inbound `eth0`
- **WHEN** the person picks the Wi-Fi adapter `wlan1` as inbound
- **THEN** a network to join and a password field appear below the inbound drop-down, and none below the outbound one

#### Scenario: Picking a wired adapter again
- **GIVEN** the Adapters page with `wlan1` picked as outbound and its fields shown
- **WHEN** the person picks `eth1` as outbound
- **THEN** the network name and password fields are hidden

#### Scenario: The same adapter twice
- **GIVEN** the Adapters page
- **WHEN** the person picks `eth1` as both inbound and outbound and presses Save
- **THEN** the page says the two adapters must differ, and sends nothing

#### Scenario: A Wi-Fi inbound in bridge mode
- **GIVEN** the Adapters page of a box in bridge mode
- **WHEN** the person picks `wlan1` as inbound and presses Save
- **THEN** the page says a Wi-Fi inbound adapter works in router mode only, and sends nothing

#### Scenario: A short password
- **GIVEN** `wlan1` picked as outbound with network name `lab-ap` and password `short`
- **WHEN** the person presses Save
- **THEN** the page says a password has 8 to 63 printable ASCII characters, and sends nothing

#### Scenario: Saved
- **GIVEN** `wlan1` picked as outbound with network name `lab-ap` and a valid password
- **WHEN** the person presses Save and the box takes it
- **THEN** the page says the roles are saved, and the table shows `wlan1` as outbound

#### Scenario: An open network to join, saved
- **GIVEN** the Adapters page of a box in router mode, `wlan1` picked as inbound with network to join `upstream` and no password
- **WHEN** the person presses Save and the box takes it
- **THEN** the page says the roles are saved, and the table shows `wlan1` as inbound
