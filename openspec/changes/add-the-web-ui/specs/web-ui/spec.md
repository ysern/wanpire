## Purpose

A web page on the box, a client of the REST API, from which a person drives the link.

## ADDED Requirements

### Requirement: The page is served by the box and needs the token for data

The server SHALL serve the web UI's static files at `/` without the token. The page SHALL send
the token with every call to `/api/v1`, and SHALL ask for it when it has none or when a call is
refused with 401.

#### Scenario: A first visit
- **GIVEN** a browser that has never opened the page
- **WHEN** the person opens `/`
- **THEN** the page asks for the token, and shows the status once a right one is given

#### Scenario: A wrong token
- **GIVEN** the page asking for the token
- **WHEN** the person gives a wrong one
- **THEN** the page says the token was refused and asks again

### Requirement: The status line shows the box at a glance

The page SHALL show the mode, whether a link is applied, the holder with its purpose and how
long it has held the link, and the number queued; it SHALL refresh them every few seconds.

#### Scenario: Someone else holds the link
- **GIVEN** an agent holds the lease for "soak test"
- **WHEN** the page shows the status
- **THEN** it names the agent and its purpose, and how long it has held the link

### Requirement: A link is described by two endpoints and a channel each

The page SHALL offer every shipped endpoint for each end, and for each the channels it has, its
default chosen first. When both ends are chosen it SHALL show the link's figures each way
(delay, jitter, loss, bandwidth) and the path's round trip and where it came from, from the
REST API's preview, without changing the link.

#### Scenario: London to Los Angeles
- **GIVEN** the page with the token
- **WHEN** the person picks London for the near end and Los Angeles on 4G for the far end
- **THEN** the page shows the delay and bandwidth both ways and the path's round trip, and the
  link is not changed

### Requirement: Changes go through the lease

To apply or clear the person SHALL first ask for the link with a name and a purpose. If it is
held, the page SHALL show its place in the queue and poll at a third of the TTL until it holds
the lease. Apply and Clear SHALL be offered only while the page holds the lease. Release SHALL
end the page's lease or leave the queue. When the lease ends without the page, the page SHALL
say why.

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

### Requirement: The counters are shown

The page SHALL show, each way, whether a link is applied and its counters: packets, bytes, the
packets wanpire dropped, those the bandwidth's queue dropped, and those queued.

#### Scenario: A link carrying traffic
- **GIVEN** a link applied that has passed 1,000 packets down
- **WHEN** the page refreshes
- **THEN** the counters show 1,000 packets down

### Requirement: Another's lease is ended by hand only after a confirmation

The page SHALL offer to end the current holder's lease when the page does not hold it. It SHALL
ask for a confirmation and a reason first, and SHALL do nothing if the person cancels.

#### Scenario: Cancelled
- **GIVEN** an agent holds the lease
- **WHEN** the person presses End lease and cancels the confirmation
- **THEN** the agent still holds the lease

#### Scenario: Confirmed
- **GIVEN** an agent holds the lease
- **WHEN** the person presses End lease, gives the reason "bench needed" and confirms
- **THEN** the lease is ended with that reason

### Requirement: The page is plain and readable on a phone

The page SHALL use one column at most about 800 px wide, system fonts, and SHALL follow the
browser's light or dark preference. At a phone's width (360 px) nothing SHALL need scrolling
sideways.

#### Scenario: On a phone
- **GIVEN** a 360 px wide window
- **WHEN** the page shows a preview and the counters
- **THEN** the page is no wider than the window
