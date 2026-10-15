## MODIFIED Requirements

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

## ADDED Requirements

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
