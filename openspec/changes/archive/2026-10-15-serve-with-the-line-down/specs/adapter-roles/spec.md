## ADDED Requirements

### Requirement: A configuration names its missing line adapters

A configuration loaded without the adapter check SHALL be able to say which of its line adapters
(inbound and outbound) the box does not have now, so that the box can start with the line down
and say why. The control adapter SHALL NOT be among them: without it the box cannot be reached,
and its absence is refused as before.

#### Scenario: The outbound adapter is unplugged
- **GIVEN** a configuration with control `wlan0`, inbound `eth0` and outbound `[wlx1]`, on a box that has `wlan0` and `eth0`
- **WHEN** it is loaded without the adapter check and asked for its missing adapters
- **THEN** it names `wlx1` as the outbound adapter that is not plugged in

#### Scenario: Everything plugged in
- **GIVEN** the same configuration on a box that has `wlan0`, `eth0` and `wlx1`
- **WHEN** it is asked for its missing adapters
- **THEN** there are none
