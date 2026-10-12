# logo Specification

## Purpose
wanpire's logo: a generic small-computer case as a cartoon vampire biting the line.

## Requirements

### Requirement: Each proposal comes in three forms

Each proposal SHALL be a full-colour SVG, a one-colour SVG and a favicon SVG simplified to read
at 16 and 32 px, each with a view box and no reference to anything outside the file.

#### Scenario: A proposal checked
- **GIVEN** a proposal in `docs/logo-proposals/`
- **WHEN** the tests parse its three files
- **THEN** each is well-formed SVG with a view box and no external reference, and the
  one-colour file uses a single colour

### Requirement: The logo is generic

A proposal SHALL show a generic small-computer case and SHALL NOT carry any product's name,
logo or trademark.

#### Scenario: No trademark
- **GIVEN** any proposal
- **WHEN** its text and shapes are read
- **THEN** it holds no product name and no fruit or other maker's mark

### Requirement: The owner picks

The proposals SHALL stay proposals until the owner picks one; the pick SHALL be recorded in
`docs/open-questions.md`.

#### Scenario: Not yet picked
- **GIVEN** the proposals committed
- **WHEN** `docs/open-questions.md` is read
- **THEN** the choice of logo is listed as needing the owner
