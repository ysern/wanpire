## ADDED Requirements

### Requirement: Bandwidth is a bottleneck with a bounded queue

A direction's bandwidth SHALL behave as a bottleneck: traffic above it SHALL wait in a queue
that holds at most `queue_ms` of data at that bandwidth (default 50 ms, from 1 to 1,000), and
SHALL be dropped beyond it. The delay asked SHALL be added on top of that queue. The engine's
delay queue SHALL then be sized at the adapter's line rate, so that drops above the bandwidth
are the bottleneck's, and SHALL be counted apart from the engine's own.

#### Scenario: One TCP flow does not fill a delay-sized queue
- **GIVEN** a direction with 40 ms delay and 20 Mbit/s bandwidth, with the default queue
- **WHEN** one TCP flow fills it for 15 seconds while a ping crosses it
- **THEN** the flow gets at least 90% of 20 Mbit/s
- **AND** no ping takes more than 40 ms plus 50 ms of queue plus 15 ms of margin

#### Scenario: A queue setting without a bandwidth
- **WHEN** a direction asks for a `queue_ms` without a bandwidth
- **THEN** it is refused with a message saying `queue_ms` needs `rate_mbit`
