## MODIFIED Requirements

### Requirement: Impairments are cleared at boot

The unit SHALL run `wanpire reset`, which clears every configured outbound adapter, then
`wanpire up`, before it serves; it SHALL restart the server when it fails. A line adapter that is
not plugged in SHALL NOT fail the unit: `reset` and `up` SHALL both exit 0 with it missing, so the
server starts with the line down and the page can say so.

#### Scenario: The unit
- **GIVEN** the unit written by the script
- **WHEN** it is read
- **THEN** `wanpire reset` runs before `wanpire up`, both before `wanpire serve`

#### Scenario: Reset
- **GIVEN** a configuration with outbound `eth1`
- **WHEN** `wanpire reset` runs
- **THEN** the engine clears `eth1`, and the control adapter is never touched

#### Scenario: The outbound adapter is unplugged at boot
- **GIVEN** a configuration with outbound `wlx1`, which the box does not have at boot
- **WHEN** the unit's pre-start steps run
- **THEN** both exit 0, `up` saying the line waits for `wlx1`, and the server is started
