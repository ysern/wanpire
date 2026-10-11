## Purpose

Decides who drives the link, one client at a time, so that whatever a client measures is the
link it asked for, and so that a client that crashes never blocks the others.

## ADDED Requirements

### Requirement: A free link is leased; a busy one queues in order of arrival

A client SHALL ask for the link with who it is and its purpose, and SHALL receive a ticket. If
the link is free and nobody is queued, the ticket SHALL hold the lease; otherwise it SHALL be
queued behind the requests already waiting, and told its position.

#### Scenario: The first asks
- **GIVEN** a free link
- **WHEN** client A asks for it
- **THEN** A holds the lease

#### Scenario: Two more ask
- **GIVEN** A holds the lease
- **WHEN** B asks, then C asks
- **THEN** B is queued at position 1 and C at position 2

### Requirement: A queued request lives only while it is polled

Each poll of a queued request SHALL renew its TTL (60 s by default). A request not polled within
its TTL SHALL leave the queue, and those behind it SHALL move up.

#### Scenario: A crashed client leaves the queue
- **GIVEN** A holds the lease, B and C are queued
- **WHEN** C polls every 20 s and B stops polling for 61 s
- **THEN** B has left the queue and C is at position 1

### Requirement: A lease lives only while it is used, and passes on

A lease SHALL be renewed by every call its holder makes (default TTL 120 s). When a lease ends,
by release or by expiry, the link SHALL be cleared, and then the lease SHALL pass to the first in
the queue, whose lease TTL starts then.

#### Scenario: The holder releases
- **GIVEN** A holds the lease and B is queued
- **WHEN** A releases it
- **THEN** the link is cleared, and B holds the lease

#### Scenario: The holder goes silent
- **GIVEN** A holds the lease, B is queued and keeps polling
- **WHEN** A makes no call for 121 s
- **THEN** the link is cleared, B holds the lease, and A's next call is told its lease expired

#### Scenario: Nobody waiting
- **GIVEN** A holds the lease and nobody is queued
- **WHEN** A releases it
- **THEN** the link is cleared and free

### Requirement: A lease can be asked for a length of time, or until released

A request MAY name how long its lease holds: a number of seconds (from 60 s to 7 days), or
until released. Such a lease SHALL need no call from its holder: a timed one SHALL end at its
length counted from when it was granted, one until released only when released or ended by
hand. A request that names neither SHALL be a lease that lives while used, as above. The
status SHALL say each lease's and each request's length, and the holder's time remaining.
While queued, every request SHALL still be polled.

#### Scenario: An hour
- **GIVEN** A asks for the link for 3,600 s and is granted it
- **WHEN** A makes no call for 3,599 s
- **THEN** A still holds the lease, with 1 s remaining; at 3,600 s it ends, the link is
  cleared, and A's next call is told its hour ended

#### Scenario: Until released
- **GIVEN** A asks for the link until released
- **WHEN** a day passes with no call from A
- **THEN** A still holds the lease, and the status says it holds until released

#### Scenario: Counted from the grant
- **GIVEN** B is queued behind A for 600 s and keeps polling
- **WHEN** A releases after 300 s
- **THEN** B's 600 s start then

### Requirement: Only changes need the lease

A change to the link SHALL be refused unless it carries the holder's ticket, with a message
naming the holder; a change that carries it SHALL renew the lease. Reading the status SHALL need
no ticket.

#### Scenario: A change without the lease
- **GIVEN** A holds the lease
- **WHEN** B asks to change the link
- **THEN** it is refused with a message naming A and its purpose

#### Scenario: The status is open
- **GIVEN** A holds the lease for "nightly soak" and B is queued
- **WHEN** anyone reads the status
- **THEN** it shows A, its purpose, since when, when the lease runs out, and B in the queue

### Requirement: A lease can be ended by hand, and the holder is told why

Ending the lease by hand SHALL clear the link, pass the lease on as when it is released, and
record a reason that the former holder SHALL be given on its next call.

#### Scenario: Ended from the web page
- **GIVEN** A holds the lease
- **WHEN** a person ends it with the reason "the lab needs the line"
- **THEN** the link is cleared, and A's next call is refused with "the lab needs the line"
