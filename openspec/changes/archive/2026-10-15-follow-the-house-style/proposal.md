## Why

The house style (`.claude/skills/web-ui-house-style/SKILL.md`, added on 2026-10-14) wrote the
page's settings-console look down as measured rules, and the page was built before those numbers
were settled. A review of the page against it (`review.md` beside this file) found 41 deviations:
9 that break the look (the band in one row instead of two, a white side menu with an inset open
group, boxed and lowercase secondary buttons, a global message panel, an accent-filled tag, the
sign-in card on a grey page), 25 off-measure (heights, paddings, weights, columns, a monospace
band line, a literal colour), and 7 of polish. Nothing enforces the rules but the contrast and
one-primary-per-section tests, so the page drifts. This change brings the page to the rules and
makes the tests hold it there.

## What Changes

- **The band** takes two rows: the mark, the name and the tagline, with the link line under the
  mark in the body font at 14 px; then the five sections evenly spaced across the column. Hover
  underlines a section's label. The band's transition is 0.3 s.
- **The side menu** is on the tint, as tall as the content beside it, 24 px from it; the open
  group is a full-width accent bar with a thin chevron; items are 40 px tall; the current child is
  bold in the body colour with the primary dot, its siblings muted.
- **Panels** get the rule's padding (40 px top, 32 px sides beside the menu) and stack 16 px apart.
  The loose footer line becomes the rule's footer: inside the last panel of the page, under a
  hairline, one uppercase text action with a line icon, right-aligned, "Source", linking to the
  project's repository (the owner asked for the link, 2026-10-15).
- **Messages** are said where they belong: a line under Ask for the lease, under Apply for the
  link, in the Broker section for a lease ended by hand; the page-level line keeps only errors
  reaching the box, as a `--danger` line with no box. A success is muted, never green.
- **Actions**: Clear and End another's lease become `--danger` text actions in their section's
  head; Sign out becomes the Access section's primary button at the control column; `.action`
  is regular weight. No secondary button remains.
- **Forms** beside the menu use 220 and 280 px columns; group-head labels (Hold the link, the two
  adapter drop-downs) are bold; inputs get 12 px side padding, the rule's focus ring, a muted
  placeholder and a pale disabled fill; every password field gets a show/hide eye.
- **Buttons** measure as the rule says: 30 px, regular weight, the gradient left to right, the
  stated glow, hover at 0.75, a grey glow-less disabled state, a primary focus ring, and the
  text colour from a new `--on-primary` token.
- **Status cards** hold a white inner panel; two-group cards split by a vertical hairline; the
  preview card gets a title; rows are 38 px apart.
- **Tables**: rows 56 px tall, "---" for a missing value, the empty queue as one muted pill. The
  place chevron and the menu chevron are drawn with CSS borders, not a text glyph. The channel
  tag is an outlined word in the primary text colour.
- **Ending another's lease** asks in the page's own modal dialog (reason field, one primary
  button, a Cancel text action) instead of the browser's prompt.
- **The set-up and sign-in page** is the wine band's colour behind the card, with the mark and
  the name in a top row; the halo and the card's padding take the rule's values.
- **Tests**: a static stylesheet test (no browser needed) rejects a literal colour outside
  `:root`, a weight other than 400 or 700, a size outside 13/14/16/20/22/24, a radius outside
  5/6/8/10/50 %, a shadow on a panel and a transition outside 0.2 to 0.3 s. The look test runs
  every page at 360 px too and measures the band's rows, the menu, the panels, the buttons, the
  table rows, the dialog and that the accent appears exactly twice on a page.
- **The skill** gains what the fix needed and it lacked: the `--on-primary` token, the band's
  height with the link line (160 to 180 px), the tag's colour, when a status card has a title, and
  the sign-in page's top row.

## Decided and assumed

Decided by the skill: every measured value above. Assumed here (also in
`docs/open-questions.md`): the footer's one action is labelled "Source" with a generic branch
icon, not the host's name or mark (no vendor is named on the page); the band
grows to at most 180 px because the link line is a row of its own; a status card that is a
section's whole body takes the section's title; the tag is outlined in the primary text colour;
Sign out is the Access section's primary; the sign-in page uses the wine gradient (a browser
that has not signed in cannot know whether a link is applied); the mark's colours stay as they
are until the owner picks a logo.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-ui`: "The page looks like a home router's admin interface" becomes "The page follows the
  house style", naming the rule set and the measured points the tests hold; "The page is
  readable at every width and in both themes" adds 360 px to every page's measurement; "Another's
  lease is ended by hand only after a confirmation" asks in the page's own dialog; a new
  requirement says where a message is shown.

## Impact

- `src/wanpire/web/style.css`: most of the sheet; `index.html`: the band, the menu, the sign-in
  page, the sections' heads, the message lines, the dialog, the password fields; `app.js`: the
  message routing, the dialog, the eye, the empty queue and "---".
- `tests/ui/test_look.py` extended; `tests/ui/test_web_ui.py` and `test_adapters_page.py` where
  they read `#message`, the browser dialog or "-"; a new `tests/unit/test_web_style.py`.
- `.claude/skills/web-ui-house-style/SKILL.md`, `docs/open-questions.md`,
  `docs/build-journal.md`.
- No API change; no dependency change.
