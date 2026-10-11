## ADDED Requirements

### Requirement: The Adapters page sets the inbound and the outbound adapter

The Adapters / Roles page SHALL show two drop-downs, *Inbound adapter* and *Outbound adapter*,
each offering the adapters the API offers and set to the current roles. When the adapter picked
in one of them is Wi-Fi, its *Network name* and *Password* SHALL be shown below that drop-down,
filled with its current access point when it has one; otherwise they SHALL be hidden. *Save*
SHALL check, before sending anything, that the two adapters differ, that a network name has 1 to
32 bytes and a password 8 to 63 printable ASCII characters, and say what is wrong beside the
field; then send the roles and say whether the box took them. The table of every adapter, its
kind, role, state and speed SHALL stay below the form.

#### Scenario: Picking a Wi-Fi adapter
- **GIVEN** the Adapters page with outbound `eth1`
- **WHEN** the person picks the Wi-Fi adapter `wlan1` as outbound
- **THEN** a network name and a password field appear below the outbound drop-down, and none below the inbound one

#### Scenario: Picking a wired adapter again
- **GIVEN** the Adapters page with `wlan1` picked as outbound and its fields shown
- **WHEN** the person picks `eth1` as outbound
- **THEN** the network name and password fields are hidden

#### Scenario: The same adapter twice
- **GIVEN** the Adapters page
- **WHEN** the person picks `eth1` as both inbound and outbound and presses Save
- **THEN** the page says the two adapters must differ, and sends nothing

#### Scenario: A short password
- **GIVEN** `wlan1` picked as outbound with network name `lab-ap` and password `short`
- **WHEN** the person presses Save
- **THEN** the page says a password has 8 to 63 printable ASCII characters, and sends nothing

#### Scenario: Saved
- **GIVEN** `wlan1` picked as outbound with network name `lab-ap` and a valid password
- **WHEN** the person presses Save and the box takes it
- **THEN** the page says the roles are saved, and the table shows `wlan1` as outbound
