## MODIFIED Requirements

### Requirement: The status line shows the box at a glance

The page SHALL show the mode, whether the line is up, whether a link is applied, the holder with
its purpose and how long it has held the link, and the number queued; it SHALL refresh them every
few seconds. The line's row SHALL read "up" in the good colour, or "down: <the reason>" in the
danger colour when a configured adapter is not plugged in.

#### Scenario: Someone else holds the link
- **GIVEN** an agent holds the lease for "soak test"
- **WHEN** the page shows the status
- **THEN** it names the agent and its purpose, and how long it has held the link

#### Scenario: The stick is unplugged
- **GIVEN** the box started with its outbound Wi-Fi stick unplugged
- **WHEN** the page shows the status
- **THEN** the line's row says it is down because that adapter is not plugged in, in the danger colour

### Requirement: Changes go through the lease

To apply or clear the person SHALL first ask for the link with a name and a purpose. If it is
held, the page SHALL show its place in the queue and poll at a third of the TTL until it holds
the lease. Apply SHALL be offered only while the page holds the lease and the line is up; Clear
SHALL be offered only while the page holds the lease. Release SHALL end the page's lease or leave
the queue. When the lease ends without the page, the page SHALL say why.

#### Scenario: Apply and release
- **GIVEN** a free link
- **WHEN** the person asks for it, applies London to Los Angeles on 4G, then releases
- **THEN** the box applied that link with the page's ticket, and the lease was released

#### Scenario: Waiting in the queue
- **GIVEN** an agent holds the lease
- **WHEN** the person asks for the link
- **THEN** the page says it is first in the queue and Apply is not offered; when the agent
  releases, the page holds the lease within one poll

#### Scenario: Ended elsewhere
- **GIVEN** the page holds the lease
- **WHEN** the lease is ended by hand with the reason "bench needed"
- **THEN** the page says its lease ended, with that reason, and offers to ask again

#### Scenario: The line is down
- **GIVEN** the page holds the lease and the line is down
- **WHEN** the Link section is shown
- **THEN** Apply is not offered, and the section says the line is down and why

### Requirement: The Adapters page sets the inbound and the outbound adapter

The Adapters / Roles page SHALL show two drop-downs, *Inbound adapter* and *Outbound adapter*,
each offering the adapters the API offers and set to the current roles. A configured adapter the
box does not have SHALL stay the drop-down's chosen entry, marked "(not plugged in)", with a line
in the danger colour under it saying to plug it in or to pick another and Save. When the adapter
picked as inbound is Wi-Fi, *Network to join* and its *Password* SHALL be shown below that
drop-down, filled with the network it joins now when it has one. When the adapter picked as
outbound is Wi-Fi, the access point's *Network name* and *Password* SHALL be shown below that
drop-down, filled with its current access point when it has one. Otherwise they SHALL be hidden.
*Save* SHALL check, before sending anything, that the two adapters differ, that a missing adapter
is not picked, that a Wi-Fi inbound adapter is not picked in bridge mode, that a network name has
1 to 32 bytes, that an access point's password has 8 to 63 printable ASCII characters and that a
network to join's password has those, or 64 hexadecimal digits, or none; and say what is wrong
beside the field. Then it SHALL send the roles and say whether the box took them. The table of
every adapter, its kind, role, state and speed SHALL stay below the form.

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

#### Scenario: The configured outbound adapter is unplugged
- **GIVEN** a box configured with outbound `wlx1`, which is not plugged in
- **WHEN** the Adapters page is shown
- **THEN** the outbound drop-down shows `wlx1 (not plugged in)` chosen, a danger line under it says to plug it in or pick another and Save, and pressing Save as it is sends nothing

#### Scenario: Fixed from the page
- **GIVEN** the same page
- **WHEN** the person picks `eth1` as outbound and presses Save, and the box takes it
- **THEN** the page says the roles are saved, and the status shows the line up
