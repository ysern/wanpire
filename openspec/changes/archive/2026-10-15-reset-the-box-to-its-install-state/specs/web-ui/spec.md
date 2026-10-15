## ADDED Requirements

### Requirement: The page offers to reset the box to its install state

Settings / Access SHALL have a section "Start over" saying what a reset restores and what is
lost, with a text action in the danger colour that opens the page's own dialog. The dialog
SHALL name what is lost (the account, the roles and Wi-Fi networks set since the install, any
link and lease), ask for the word `reset` to be typed, and offer one primary button and a
Cancel action; the primary SHALL stay disabled until the word is typed. On confirmation the page
SHALL post the reset, say that the box is resetting, and poll until the box answers again, then
show the set-up card.

#### Scenario: Cancelled
- **GIVEN** the Access page
- **WHEN** the person opens the reset dialog and cancels
- **THEN** nothing is sent and the page is unchanged

#### Scenario: The word is not typed
- **GIVEN** the reset dialog open
- **WHEN** the word field is empty or reads anything but `reset`
- **THEN** the primary button is disabled

#### Scenario: Reset
- **GIVEN** the reset dialog open, no lease held
- **WHEN** the person types `reset` and confirms
- **THEN** the page says the box is resetting, and when the box answers again the page shows the set-up card
