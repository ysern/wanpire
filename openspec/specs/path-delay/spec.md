# path-delay Specification

## Purpose
Works out the path between two ends, and combines it with each end's channel into a link the
engine can apply, preferring measured figures that may be shipped and falling back to a formula
whose error is known.

## Requirements

### Requirement: Only redistributable measurements ship, with their attribution

The shipped path table SHALL contain only figures whose licence allows redistribution under
the project's MIT licence, and SHALL carry its source's name, URL, licence, dataset date and the
attribution its licence asks for. A script in the repository SHALL rebuild the table from the
source.

#### Scenario: The table names its source
- **WHEN** the shipped path table is read
- **THEN** it names its source, its licence `CC-BY-4.0`, its dataset date and an attribution

### Requirement: The path comes from the endpoint, then the table, then the formula

The round trip of the path between two ends SHALL be, in this order: a measured path that one
end's preset gives for the other; the table, when each end lies within 1,000 km of a table
site, as the mean of the two directions between those sites, corrected by the formula's
difference between the ends and the sites; otherwise the formula. The result SHALL say which
was used.

#### Scenario: A measured path in the preset wins
- **GIVEN** a preset that gives 100 ms as its path to `tokyo`
- **WHEN** the path from it to Tokyo is worked out
- **THEN** it is 100 ms and its origin is the preset

#### Scenario: Two ends near table sites
- **GIVEN** London and Tokyo, each within 1,000 km of a table site
- **WHEN** the path between them is worked out
- **THEN** its origin is the table and it is within 5 ms of the table's figure between those sites

#### Scenario: An end far from every site
- **GIVEN** an end in the middle of the Pacific, more than 1,000 km from every site
- **WHEN** the path from it to London is worked out
- **THEN** its origin is the formula

### Requirement: The formula is fitted and its error is published

The formula SHALL be `rtt = 2 × great_circle_km × route_factor / 200 + router_ms`, with a
route factor per unordered pair of world regions and one router term, fitted against the
shipped table by a script in the repository. The fitted parameters and the error left over,
pair by pair and summarised per region pair, SHALL be committed. A region pair without enough
measured pairs SHALL use the global factor.

#### Scenario: The formula is close to the table it was fitted on
- **WHEN** the formula is evaluated on every table pair more than 300 km apart
- **THEN** the median absolute error is below 15%

#### Scenario: An unfitted region pair
- **GIVEN** two regions with no fitted factor between them
- **WHEN** the formula is evaluated between them
- **THEN** the global factor is used and the result says so

### Requirement: Two ends and their channels combine into one link

Given a near end (the device under test's) and a far end, each with a channel, the link SHALL
be: *down* delay = path / 2 + far channel's *up* delay + near channel's *down* delay, and *up*
delay = path / 2 + near channel's *up* delay + far channel's *down* delay; jitters adding in
quadrature; losses compounding as `1 − (1 − a)(1 − b)`, kept as burst loss with the longer mean
burst when either channel's loss comes in bursts; bandwidth the narrower of the sender's *up*
and the receiver's *down*. The result SHALL be a plain link the engine accepts, with an account
of how each figure was obtained.

#### Scenario: London consumer fibre to Los Angeles 4G
- **GIVEN** a path of 140 ms, a near channel with 5 ms delay and 3 ms jitter each way, 0.1% loss, 500 Mbit/s down and 100 up, and a far channel with 25 ms delay and 4 ms jitter each way, 1% loss, 50 Mbit/s down and 10 up
- **WHEN** they combine
- **THEN** down is 100 ms delay, 5 ms jitter, 1.099% loss and 10 Mbit/s
- **AND** up is 100 ms delay, 5 ms jitter, 1.099% loss and 50 Mbit/s

#### Scenario: Burst loss is kept
- **GIVEN** a near channel with 1% random loss and a far channel with 2% loss in bursts of 4
- **WHEN** they combine
- **THEN** the loss is 2.98% in bursts of 4

### Requirement: The CLI takes two ends

`wanpire preview <near> <far>` SHALL print the combined link and how it was worked out, without
root; `wanpire apply --adapter <outbound> <near> <far>` SHALL apply it; raw figures SHALL still
be accepted.

#### Scenario: Preview needs no root
- **WHEN** `wanpire preview london:consumer-fibre los-angeles:mobile-4g` runs as an ordinary user
- **THEN** it prints the link's down and up figures and the path's origin, and changes nothing

#### Scenario: Apply from two ends
- **WHEN** `wanpire apply --adapter <outbound> london new-york` runs
- **THEN** the engine is given the same link that `preview london new-york` prints
