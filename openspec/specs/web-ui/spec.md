# web-ui Specification

## Purpose
A web page on the box, a client of the REST API, from which a person drives the link.

## Requirements

### Requirement: The first visit makes the box's account

The server SHALL serve the web UI's static files at `/` without credentials. When the box has no
account, the page SHALL ask the person to make one, a user name, a password and the password
again, and SHALL sign them in once it is made, as a home router does on its first visit. It
SHALL say what is wrong with a password that is too short or not repeated the same, before
sending anything.

#### Scenario: A new box
- **GIVEN** a box with no account
- **WHEN** the person opens `/`, gives `admin` and the same password of 12 characters twice
- **THEN** the account is made and the page shows the status, signed in as `admin`

#### Scenario: The passwords differ
- **GIVEN** the page asking to make the account
- **WHEN** the person gives two different passwords
- **THEN** the page says they differ, and no account is made

### Requirement: A person signs in with the user name and the password

When the box has an account and the browser has no session, the page SHALL ask for the user name
and the password. It SHALL keep no credential in the browser's storage: the session is a cookie
the page cannot read. It SHALL ask again when a call is refused with 401. Settings SHALL let the
person sign out and change the password.

#### Scenario: Signing in
- **GIVEN** the account `admin`
- **WHEN** the person opens `/` and gives `admin` and its password
- **THEN** the page shows the status

#### Scenario: A wrong password
- **GIVEN** the page asking to sign in
- **WHEN** the person gives a wrong password
- **THEN** the page says the user name or the password was refused and asks again

#### Scenario: Coming back
- **GIVEN** a person who signed in and closed the tab
- **WHEN** they open `/` again in the same browser
- **THEN** the page shows the status without asking

#### Scenario: Signing out
- **GIVEN** a signed-in page
- **WHEN** the person presses Sign out in Settings
- **THEN** the page asks to sign in, and a reload asks again

### Requirement: The header says what the box is doing to the line

The header band SHALL carry, under the logo and aligned to its left, the link the box applies
now, read from the status whoever applied it, in the API's own short form: the two ends when
it was applied from ends (`london:generic <> los-angeles:mobile-4g`), `set by figures` when from
figures, `link applied` when the box applies one the API was not told about, and `no link` when
nothing is applied. While nothing is applied the band
SHALL be a calm pastel; only while a link is applied SHALL it take the primary wine red, so the
state is seen from across the room. Every text on the band SHALL meet WCAG AA in both states
and both themes.

#### Scenario: An agent applies a link
- **GIVEN** the page open, nothing applied, the band pastel
- **WHEN** an agent applies London to Los Angeles, both on generic
- **THEN** within a refresh the band is wine red and reads `london:generic <> los-angeles:generic`

#### Scenario: Cleared
- **GIVEN** a link applied and the band wine red
- **WHEN** the holder clears it
- **THEN** within a refresh the band is pastel and reads `no link`

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
- **GIVEN** the page signed in
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

### Requirement: The person chooses how long to hold the link

The Lease section SHALL offer how long to hold the link: until released (chosen first), 10 min,
30 min, 1 h, 5 h, 1 day, 1 week, or while this page is open. A lease with a length SHALL be kept
when the page is closed, and a page opened again in the same browser SHALL find it held. The
Broker page SHALL show, for the holder, the time remaining, "until released", or "while in use",
and for each request its length.

#### Scenario: An hour, then the page closed
- **GIVEN** a free link
- **WHEN** the person asks for it for 1 h, applies a link and closes the page
- **THEN** the lease and the link are kept, and the Broker page shows about 1 h remaining

#### Scenario: Until released
- **WHEN** the person asks for the link until released
- **THEN** the Broker page shows "until released" for the holder, and the page's Release ends it

#### Scenario: While this page is open
- **WHEN** the person asks for the link while the page is open, and closes the page
- **THEN** the lease is released

### Requirement: The traffic is shown

A page named Traffic (the counters' page until 2026-10-11; the API and the MCP keep the word
"counters") SHALL show, each way, whether a link is applied and its counters: packets, bytes, the
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

### Requirement: Each place opens to show its channels

The Endpoints page SHALL list every shipped place as a closed, read-only row naming the place,
its country, how many channels it offers and its default. Opening a row SHALL list each of its
channels with its description and its figures each way, down and up: delay, jitter, loss and
bandwidth, the default marked. Nothing on it SHALL change the box.

#### Scenario: London opened
- **GIVEN** the Endpoints page
- **WHEN** the person opens London
- **THEN** its twelve channels are listed, generic marked as the default, each with its delay,
  jitter, loss and bandwidth down and up, and there is no control that changes anything

### Requirement: The page looks like a home router's admin interface

The page SHALL carry a header band with the sections Link, Broker, Adapters, Endpoints and
Settings, the active one marked; a side menu for a section's sub-pages; white panels on a light
grey page in a centred column of about 1,070 px; forms with labels on the left; at most one
primary button per section; and SHALL follow the browser's light or dark preference. It SHALL
fetch nothing from elsewhere.

#### Scenario: Going to a section
- **GIVEN** the page on Link
- **WHEN** the person picks Broker in the header band
- **THEN** Broker is marked active, and the holder and the queue are shown

#### Scenario: Nothing from elsewhere
- **GIVEN** the page loading
- **WHEN** every request it makes is listed
- **THEN** each goes to the box itself

### Requirement: The page is readable at every width and in both themes

At 720 px and at 1,280 px, in the light and the dark theme, nothing SHALL need scrolling sideways,
and every visible text SHALL have a contrast of at least 4.5:1 with its background (3:1 for large
text), as WCAG 2.2 AA asks. At a phone's width (360 px) nothing SHALL need scrolling sideways.

#### Scenario: Contrast in the dark
- **GIVEN** a 1,280 px window that prefers the dark theme
- **WHEN** the page shows the link's figures and the counters
- **THEN** every visible text has at least 4.5:1 against its background

#### Scenario: On a phone
- **GIVEN** a 360 px wide window
- **WHEN** the page shows a preview and the counters
- **THEN** the page is no wider than the window
