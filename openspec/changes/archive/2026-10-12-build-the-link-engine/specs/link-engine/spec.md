## Purpose

Applies a described link to the line, replaces it, clears it and reads it back, touching only
the outbound adapter so that the control channel can never be impaired.

## ADDED Requirements

### Requirement: Both directions are impaired on the outbound adapter only

Applying a link SHALL impair *down* on the outbound adapter's egress and *up* on its ingress,
and SHALL change nothing on any other adapter.

#### Scenario: Delay each way
- **GIVEN** an outbound adapter between two hosts, A behind it and B beyond it
- **WHEN** a link with 50 ms down and 50 ms up is applied
- **THEN** a ping from A to B takes 100 ms more than before, within 1 ms

#### Scenario: Other adapters untouched
- **GIVEN** a box with a control adapter and an outbound adapter
- **WHEN** a link is applied and later cleared
- **THEN** the control adapter's queueing configuration is the same as before, throughout

### Requirement: Applying replaces the whole link

Applying a link to an adapter that already carries one SHALL replace it entirely: no setting of
the earlier link SHALL survive unless the new one asks for it.

#### Scenario: Reordering does not linger
- **GIVEN** a link with 20 ms delay and 25% reordering is applied
- **WHEN** a link with only 2% loss is applied
- **THEN** the line reorders nothing and loses about 2%

### Requirement: Clearing leaves the adapter as it was

Clearing SHALL remove everything the engine added to the adapter, including any helper device,
and SHALL succeed when there is nothing to clear.

#### Scenario: Clear after apply
- **GIVEN** a link is applied
- **WHEN** it is cleared
- **THEN** the adapter's queueing configuration is what it was before the first apply
- **AND** no helper device made by the engine remains

#### Scenario: Clear twice
- **WHEN** an adapter with no link is cleared
- **THEN** the call succeeds and changes nothing

### Requirement: The link reads back with who dropped what

Reading a link SHALL return, per direction, what is applied, packets and bytes sent, packets
dropped by the engine itself, and packets queued now.

#### Scenario: Counting the engine's own drops
- **GIVEN** a link with 5% loss down
- **WHEN** 10,000 packets cross it and the link is read
- **THEN** the down direction reports about 500 packets dropped by the engine

### Requirement: An applied link has a lifetime

A link SHALL be applied with a lifetime (default 120 s). It SHALL be cleared when its lifetime
runs out unless renewed, whether or not the process that applied it is still running.

#### Scenario: Not renewed
- **GIVEN** a link applied with a lifetime of 5 s
- **WHEN** 7 s pass with no renewal
- **THEN** the adapter carries no link

#### Scenario: Renewed
- **GIVEN** a link applied with a lifetime of 5 s
- **WHEN** it is renewed every 2 s for 10 s
- **THEN** the link is still applied at the end

### Requirement: The engine refuses the control adapter

Applying a link to the adapter mapped as control SHALL be refused with a message saying so.

#### Scenario: Wrong adapter
- **GIVEN** the configuration names `wlan0` as the control adapter
- **WHEN** a link is applied to `wlan0`
- **THEN** it is refused and `wlan0` is unchanged
