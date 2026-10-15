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

The page SHALL show the mode, whether the line is up, whether a link is applied, the holder with
its purpose and how long it has held the link, and the number queued; it SHALL refresh them every
few seconds. The line's row SHALL read "up" in the good colour, or "down: <the reason>" in the
danger colour when a configured adapter is not plugged in.

#### Scenario: Someone else holds the link
- **GIVEN** an agent holds the lease for "soak test"
- **WHEN** the page shows the status
- **THEN** it names the agent and its purpose, and how long it has held the link

#### Scenario: The stick is unplugged
- **GIVEN** the box started with its outbound Wi-Fi stick unplugged
- **WHEN** the page shows the status
- **THEN** the line's row says it is down because that adapter is not plugged in, in the danger colour

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
the lease. Apply SHALL be offered only while the page holds the lease and the line is up; Clear
SHALL be offered only while the page holds the lease. Release SHALL end the page's lease or leave
the queue. When the lease ends without the page, the page SHALL say why.

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

#### Scenario: The line is down
- **GIVEN** the page holds the lease and the line is down
- **WHEN** the Link section is shown
- **THEN** Apply is not offered, and the section says the line is down and why

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

The page SHALL offer to end the current holder's lease when the page does not hold it, as a
text action in the Broker section's head. It SHALL ask for a confirmation and a reason first in
a dialog of its own, naming the holder and its purpose, with one primary button that ends the
lease and a Cancel text action, and SHALL do nothing if the person cancels.

#### Scenario: Cancelled
- **GIVEN** an agent holds the lease
- **WHEN** the person presses End this lease and cancels the dialog
- **THEN** the agent still holds the lease

#### Scenario: Confirmed
- **GIVEN** an agent holds the lease
- **WHEN** the person presses End this lease, gives the reason "bench needed" and confirms
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

The page SHALL follow the house style written in `.claude/skills/web-ui-house-style/SKILL.md`:
a header band with the sections Link, Broker, Adapters, Endpoints and Settings, the active one
marked; a side menu for a section's sub-pages; white panels on a light grey page in a centred
column of about 1,070 px; forms with labels on the left; at most one primary button per
section; and SHALL follow the browser's light or dark preference. It SHALL fetch nothing from
elsewhere. The points below SHALL hold on every page and be measured by the page's tests; the
rest of the style is reviewed by the skill's checklist.

- The band has two rows: the mark, the name and the tagline, with the link line under the mark
  in the body font; then the five sections, left-aligned on the column and 16 px apart, the gap
  the band keeps to the frame below it. The band is 160 to 180 px tall.
- The side menu is on the tint, as tall as the content beside it; its open group is a
  full-width accent bar; its items are 40 px tall; the current child is bold and its siblings
  muted.
- The accent colour appears on exactly two things on a page: the active section's circle and
  the open menu group.
- A panel's content starts about 40 px from its top; panels stack 16 px apart.
- A primary button is 28 to 30 px tall, uppercase, the full width of its control column, and
  the only button of its section. Every other action is text: in the primary colour, or in the
  danger colour when it ends or clears something. There is no boxed secondary button.
- A table's rows are pills about 56 px tall; a missing value reads "---"; an empty table is one
  pill holding one muted line.
- A password field shows its text while its eye icon is pressed.
- The stylesheet paints every colour from a custom property, uses only the weights 400 and 700,
  the sizes 13, 14, 16, 20, 22 and 24 px, the radii 5, 6, 8, 10 px and 50 %, no shadow on a
  panel, a card or a row, and transitions of 0.2 to 0.3 s.
- The set-up and sign-in page is the band's colour behind a centred white card of 380 to 460 px
  with the mark and the name in a row above it.
- The page's footer is inside the last panel, under a hairline, right-aligned: one uppercase
  text action with a line icon, "Source", linking to the project's repository.

#### Scenario: Going to a section
- **GIVEN** the page on Link
- **WHEN** the person picks Broker in the header band
- **THEN** Broker is marked active, and the holder and the queue are shown

#### Scenario: Nothing from elsewhere
- **GIVEN** the page loading
- **WHEN** every request it makes is listed
- **THEN** each goes to the box itself

#### Scenario: The band's two rows
- **GIVEN** a 1,280 px window signed in
- **WHEN** the band is measured
- **THEN** the sections' row lies below the brand's row, its first circle at the column's left
  and each as far from the next as the band is from the frame below, and the band is 160 to
  180 px tall

#### Scenario: The accent marks the active items only
- **GIVEN** the Endpoints page with a place opened, which shows a default channel's tag
- **WHEN** every element painted in the accent colour is counted
- **THEN** there are two: the Endpoints circle in the band and the open Endpoints group in the menu

#### Scenario: The menu's open group
- **GIVEN** the Link section's Traffic page
- **WHEN** the side menu is measured
- **THEN** the menu is on the tint and as tall as the content panel beside it, the Link group's
  bar is the menu's full width, Traffic is bold and Set the link is muted

#### Scenario: One kind of button
- **GIVEN** every page in turn
- **WHEN** its buttons are measured
- **THEN** each section has at most one primary, 28 to 30 px tall and uppercase, and no other
  boxed button; Clear and End this lease are text in the danger colour

#### Scenario: The queue is empty
- **GIVEN** nobody holds or waits for the link
- **WHEN** the Broker page is shown
- **THEN** the queue table holds one row with one muted line saying nobody is using the box

#### Scenario: The footer's source link
- **GIVEN** any page signed in
- **WHEN** the bottom of the page is read
- **THEN** the last panel ends with a hairline and, right-aligned under it, an uppercase
  "Source" action with a line icon that links to the project's repository

#### Scenario: A password shown
- **GIVEN** the sign-in card with a password typed
- **WHEN** the person presses the eye in the password field
- **THEN** the password is shown as text, and pressing again hides it

#### Scenario: The stylesheet keeps to the tokens
- **GIVEN** the stylesheet
- **WHEN** every colour, weight, size, radius, shadow and transition outside the `:root` blocks is read
- **THEN** each is a custom property or one of the house style's values

### Requirement: The page is readable at every width and in both themes

At 360 px, 720 px and 1,280 px, in the light and the dark theme, on every page, nothing SHALL
need scrolling sideways, and every visible text SHALL have a contrast of at least 4.5:1 with its
background (3:1 for large text), as WCAG 2.2 AA asks. At 360 px the menu, the band's rows and the
forms' columns stack.

#### Scenario: Contrast in the dark
- **GIVEN** a 1,280 px window that prefers the dark theme
- **WHEN** the page shows the link's figures and the counters
- **THEN** every visible text has at least 4.5:1 against its background

#### Scenario: On a phone
- **GIVEN** a 360 px wide window
- **WHEN** each page is shown in turn, the preview and the counters included
- **THEN** no page is wider than the window, and every visible text meets the contrast

### Requirement: The Adapters page sets the inbound and the outbound adapter

The Adapters / Roles page SHALL show two drop-downs, *Inbound adapter* and *Outbound adapter*,
each offering the adapters the API offers and set to the current roles. A configured adapter the
box does not have SHALL stay the drop-down's chosen entry, marked "(not plugged in)", with a line
in the danger colour under it saying to plug it in or to pick another and Save. When the adapter
picked as inbound is Wi-Fi, *Network to join* and its *Password* SHALL be shown below that
drop-down, filled with the network it joins now when it has one. When the adapter picked as
outbound is Wi-Fi, the access point's *Network name* and *Password* SHALL be shown below that
drop-down, filled with its current access point when it has one. Otherwise they SHALL be hidden.
*Save* SHALL check, before sending anything, that the two adapters differ, that a missing adapter
is not picked, that a Wi-Fi inbound adapter is not picked in bridge mode, that a network name has
1 to 32 bytes, that an access point's password has 8 to 63 printable ASCII characters and that a
network to join's password has those, or 64 hexadecimal digits, or none; and say what is wrong
beside the field. Then it SHALL send the roles and say whether the box took them. The table of
every adapter, its kind, role, state and speed SHALL stay below the form.

#### Scenario: Picking a Wi-Fi outbound adapter
- **GIVEN** the Adapters page with outbound `eth1`
- **WHEN** the person picks the Wi-Fi adapter `wlan1` as outbound
- **THEN** a network name and a password field appear below the outbound drop-down, and none below the inbound one

#### Scenario: Picking a Wi-Fi inbound adapter
- **GIVEN** the Adapters page with inbound `eth0`
- **WHEN** the person picks the Wi-Fi adapter `wlan1` as inbound
- **THEN** a network to join and a password field appear below the inbound drop-down, and none below the outbound one

#### Scenario: Picking a wired adapter again
- **GIVEN** the Adapters page with `wlan1` picked as outbound and its fields shown
- **WHEN** the person picks `eth1` as outbound
- **THEN** the network name and password fields are hidden

#### Scenario: The same adapter twice
- **GIVEN** the Adapters page
- **WHEN** the person picks `eth1` as both inbound and outbound and presses Save
- **THEN** the page says the two adapters must differ, and sends nothing

#### Scenario: A Wi-Fi inbound in bridge mode
- **GIVEN** the Adapters page of a box in bridge mode
- **WHEN** the person picks `wlan1` as inbound and presses Save
- **THEN** the page says a Wi-Fi inbound adapter works in router mode only, and sends nothing

#### Scenario: A short password
- **GIVEN** `wlan1` picked as outbound with network name `lab-ap` and password `short`
- **WHEN** the person presses Save
- **THEN** the page says a password has 8 to 63 printable ASCII characters, and sends nothing

#### Scenario: Saved
- **GIVEN** `wlan1` picked as outbound with network name `lab-ap` and a valid password
- **WHEN** the person presses Save and the box takes it
- **THEN** the page says the roles are saved, and the table shows `wlan1` as outbound

#### Scenario: An open network to join, saved
- **GIVEN** the Adapters page of a box in router mode, `wlan1` picked as inbound with network to join `upstream` and no password
- **WHEN** the person presses Save and the box takes it
- **THEN** the page says the roles are saved, and the table shows `wlan1` as inbound

#### Scenario: The configured outbound adapter is unplugged
- **GIVEN** a box configured with outbound `wlx1`, which is not plugged in
- **WHEN** the Adapters page is shown
- **THEN** the outbound drop-down shows `wlx1 (not plugged in)` chosen, a danger line under it says to plug it in or pick another and Save, and pressing Save as it is sends nothing

#### Scenario: Fixed from the page
- **GIVEN** the same page
- **WHEN** the person picks `eth1` as outbound and presses Save, and the box takes it
- **THEN** the page says the roles are saved, and the status shows the line up

### Requirement: A result is said in the section it belongs to

The page SHALL say the result of an action as one line under the button that caused it: the
lease's answers under Ask for the link, the link's under Apply, a lease ended by hand in the
Broker section, the roles' under Save, the password's under Change. A success SHALL be stated
in the muted colour; a refusal SHALL be a line in the danger colour. Only an error reaching the
box SHALL be said at the top of the page, as a danger line with no box around it.

#### Scenario: Applied
- **GIVEN** the page holding the lease
- **WHEN** the person applies a link
- **THEN** "Applied." is said under Apply, in the muted colour, and nothing at the top of the page

#### Scenario: Refused
- **GIVEN** the page holding the lease
- **WHEN** the box refuses the link
- **THEN** the box's reason is said under Apply, in the danger colour

#### Scenario: The box cannot be reached
- **GIVEN** the page open
- **WHEN** a refresh fails to reach the box
- **THEN** a danger line at the top of the page says the box cannot be reached
