## ADDED Requirements

### Requirement: The line waits for an adapter that is not plugged in

When a line adapter named in the configuration does not exist, setting the mode up at boot SHALL
NOT fail the box: `wanpire up` SHALL say which adapter is missing and exit 0 with the line down,
and the server SHALL start. While the line is down the server SHALL look for the missing
adapters every few seconds and SHALL set the mode up as soon as they exist, without a restart.
Tearing a mode down SHALL succeed when a line adapter is missing, removing whatever is there.

#### Scenario: The stick is unplugged at boot
- **GIVEN** a configuration whose outbound adapter is a USB Wi-Fi stick that is not plugged in
- **WHEN** the unit runs `wanpire up` and then `wanpire serve`
- **THEN** `up` exits 0 saying the line waits for that adapter, the server listens on the control address, and the status says the line is down naming the adapter

#### Scenario: The stick is plugged in later
- **GIVEN** the server running with the line down for a missing outbound adapter
- **WHEN** the adapter appears
- **THEN** within a few seconds the mode is set up with the configured roles and the status says the line is up

#### Scenario: Teardown with a missing adapter
- **GIVEN** bridge mode set up, then its outbound adapter removed
- **WHEN** the mode is torn down
- **THEN** the bridge is gone and the call does not fail

#### Scenario: The control adapter is missing
- **GIVEN** a configuration whose control adapter the box does not have
- **WHEN** `wanpire serve` starts
- **THEN** it refuses with a message naming the control adapter, as there is nothing to listen on
