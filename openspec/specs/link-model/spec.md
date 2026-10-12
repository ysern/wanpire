# link-model Specification

## Purpose
Describes a link wanpire emulates, one direction at a time, and fixes what each setting means
so that what a user asks for is what the line does, whatever the kernel's own defaults are.

## Requirements

### Requirement: A link has two directions described independently

A link SHALL be described as two directions, *down* (towards the device under test) and *up*
(away from it). Each direction SHALL accept: delay (ms), jitter (ms), jitter distribution
(`normal`, `uniform`, `pareto`, `paretonormal`), random loss (%), burst loss as a mean loss (%)
with a mean burst length (packets), bandwidth (Mbit/s), duplication (%), and reordering (%).
Every setting SHALL be optional and SHALL default to no impairment.

#### Scenario: An asymmetric link
- **WHEN** a link is described with 150 ms delay down and 20 ms delay up
- **THEN** the down direction carries 150 ms and the up direction 20 ms

#### Scenario: An empty description
- **WHEN** a direction is described with no settings
- **THEN** that direction adds no delay, no loss and no limit

### Requirement: Invalid figures are refused with a reason

A description SHALL be refused, with a message naming the setting and the allowed range, when a
delay or jitter is negative or above 10,000 ms, a percentage is outside 0 to 100, a bandwidth is
not positive, a burst length is below 1, both random and burst loss are set on one direction, a
jitter is larger than its delay, or the distribution is not one of those listed.

#### Scenario: Loss above 100%
- **WHEN** a direction asks for 120% loss
- **THEN** the description is refused with a message naming `loss` and the range 0 to 100

#### Scenario: Two loss models at once
- **WHEN** a direction asks for both random loss and burst loss
- **THEN** the description is refused with a message saying only one loss model may be set

### Requirement: Jitter means a normal spread that keeps packets in order

Unless the description says otherwise, jitter SHALL follow a normal distribution with the
jitter as its standard deviation, and packets SHALL leave in the order they arrived. Reordering
SHALL happen only when a reordering percentage is asked.

#### Scenario: Jitter alone does not reorder
- **GIVEN** a direction with 50 ms delay and 10 ms jitter and no reordering asked
- **WHEN** 10,000 packets cross it at 1,000 packets per second
- **THEN** none arrives out of order
- **AND** the delays' standard deviation is within 20% of 10 ms

#### Scenario: Reordering when asked
- **GIVEN** a direction with 20 ms delay and 25% reordering
- **WHEN** 10,000 packets cross it at 1,000 packets per second
- **THEN** some packets arrive out of order

### Requirement: Burst loss is described by its mean and its burst length

Burst loss SHALL be given as a mean loss and a mean burst length, and SHALL produce, over a long
run, that mean loss in bursts of that mean length. Netem's loss correlation SHALL NOT be used to
produce it.

#### Scenario: Three per cent in bursts of three
- **GIVEN** a direction with burst loss of 3% in bursts of 3 packets
- **WHEN** 10,000 packets cross it
- **THEN** between 2% and 4% are lost
- **AND** the lost packets' mean run length is between 2 and 4.5

### Requirement: The queue is long enough for the delay asked

A direction's queue SHALL hold at least what arrives during its delay plus three times its
jitter, at its bandwidth (or the adapter's line rate when no bandwidth is asked), with half
again as margin; it SHALL never be shorter than 1,000 packets, and SHALL be capped by a memory
budget per direction (64 MB by default) at an assumed 2 KB per queued packet.

#### Scenario: A long delay at a high rate
- **GIVEN** a direction with 150 ms delay and 100 Mbit/s bandwidth
- **WHEN** a steady 95 Mbit/s of 1,400-byte packets crosses it for 15 seconds
- **THEN** the engine's own queue drops no packet

#### Scenario: The cap
- **GIVEN** a direction with 10,000 ms delay on a 1,000 Mbit/s adapter
- **WHEN** its queue length is worked out
- **THEN** it is 32,768 packets (64 MB at 2 KB each)
