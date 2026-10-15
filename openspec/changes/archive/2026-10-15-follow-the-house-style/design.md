## Context

See `proposal.md` for why and `review.md` for the 41 findings. The page is one stylesheet
(`style.css`, 410 lines), one page (`index.html`) and one script (`app.js`); its tests run the
real app with a recording engine under Playwright (`tests/ui/conftest.py`), and need no root.
Every page sits beside the side menu, so the rule's "beside a side menu" numbers apply
everywhere. The page already keeps every colour in `:root` tokens with one exception, so the
work is a measured retune, not a rebuild. This machine has no browser; the rendered check runs
on a box with Playwright.

## Goals / Non-Goals

**Goals:** every finding of rank *Breaks the look* and *Off-measure* fixed; the polish items
fixed where they are a stylesheet or a small markup change; a test for each rule the skill
states as a number, so the page cannot drift back; the skill amended where the fix needed a
rule it lacked.

**Non-Goals:** a new logo or any change to the mark's colours (the `logo` capability, waiting on
the owner); controls the page does not use (toggles, checkboxes, radios, tabs, log views,
tooltips, help icons); a Settings page that changes the box; a custom-drawn select chevron (the
browser's is kept: the alternatives need a literal colour in a data URI).

## Decisions

### D1. The band stacks: brand, link line, sections

`.band-inner` becomes a column: a top row (`.brand`), the link line, then `.sections` as a row
with `justify-content: space-between` across the column. The link line is `14px` in the body
font, weight 400, in the band's ink. At 360 px the sections wrap into two rows of circles and
the band grows; the look test allows that. The band's height becomes 160 to 180 px at 1,280 px,
and the skill's "about 160" is amended to say so.

Not taken: the link line beside the brand in the top row (the spec and the skill say under the
mark); the sections row at the right, under the brand only (not "evenly spaced on the column");
dropping the tagline to stay at 160 (the skill names it).

### D2. The side menu is a stretched tint column

`.frame` uses `align-items: stretch`; `.side` is a flex column whose visible `nav` grows to
fill it, on `--tint`. The open group is a block with no margin and no radius of its own; the
menu's `overflow: hidden` clips it to the 10 px corners. Items are `min-height: 40px` flex
rows; children are padded `16px + 12px` with the dot at 16 px. The group's chevron is a 7 px
CSS-border chevron (`border-right`, `border-bottom`, rotated), coloured by `currentColor`, so no
colour is painted outside the tokens. The same drawing replaces the "▸" glyph on a place.

Not taken: an SVG chevron in a `::before` (needs a data URI with a literal colour, or a mask,
which is more rule than it is worth); leaving the menu white (the rule is explicit).

### D3. Messages move to where they belong; `say()` takes a place

`app.js`'s `say(text, kind)` becomes `say(place, text, kind)` writing to `#lease-message`,
`#link-message`, `#broker-message` (new `p.help` lines under Ask, Apply and in the Broker
section) or `#message` at the top for errors reaching the box. `kind` is `"bad"` or nothing;
the `good` kind goes, so a success is muted. `#message` is a plain line in `--danger`, no panel.
The tests that read `#message` for "Applied" and "Cleared" read `#link-message`.

Not taken: keeping one global message unboxed (the rule says under the button); a toast (the
style has no such thing).

### D4. The actions: text where the rule says text, one primary per section

- `#clear` and `#end-lease` become `button.action.danger` (`color: var(--danger)`) in their
  section's `.head`. `#end-lease` stays hidden unless another holds the lease.
- `#signout` becomes the Access section's `button.primary` in a `.form` grid at the control
  column; "Signed in as" becomes a form-like row (`<span>` label, `<span id="me">` value), so the
  section reads as a two-column list and the card class is used for figures only.
- `button.secondary`, `.buttons` and `.secondary.danger` are removed from the stylesheet as
  unused. If a secondary is needed later it is written to the rule then (uppercase, the control
  column's width).

Not taken: keeping Sign out secondary and making it uppercase (a secondary with no primary
beside it is a boxed text action); Release as a danger action (releasing is the normal end of
a turn, not destructive).

### D5. Ending another's lease in a `<dialog>`

A native `<dialog id="end-dialog">` holds a header strip on the tint (bold 16 px title, a close
cross as a text button), a `.form` body with the holder's name and purpose in a sentence and a
reason field, and an actions row with one primary ("End the lease") and a Cancel `.action`.
`::backdrop` is 45 % black. The script opens it with `showModal()`, and the form's submit sends
`DELETE lease/holder` with the typed reason or the old default. The two UI tests stop listening
for a browser dialog and fill `#end-reason` then press `#end-confirm` or `#end-cancel`.

Not taken: keeping `window.prompt` (it cannot wear the style, and the dialog rule exists for
this one case); a custom overlay div (the element does focus trapping and Escape for free).

### D6. Password fields get an eye

Each password input is wrapped in `.password` (relative) with a `button.eye` holding an inline
SVG eye, absolutely at the right inside the field; the input gets right padding for it. One
delegated click handler toggles `type` between `password` and `text` and the button's
`aria-pressed`. The icon is one more `<symbol>` in the page's sprite, drawn for wanpire.

Not taken: a "show password" checkbox beside the field (the rule says an icon inside the field);
leaving it (a stated rule, five fields, a small handler).

### D7. Status cards: an inner panel, a hairline, a title when needed

`.card` becomes the tint wrapper with an optional `.card-title` (16 px bold) and an inner
`.card-body` on `--panel` holding the `dl` grid. A `.two` card (preview, counters) draws
`border-right: 1px solid var(--hair)` on its odd children so the down and up groups are split by
one vertical hairline; the markup keeps alternating down/up rows, which the grid already lays
left and right. Rows are 38 px apart. The preview card gets the title "Figures each way"; the
state and the counters cards are their sections' whole body and take the section's title, a
rule the skill gains.

Not taken: reordering the markup into two `dl`s (more change in `app.js` and the tests for the
same picture); a title on every card ("State of the box" above "State of the box").

### D8. Measured values go to the tokens and the sheet

- `--on-primary: #ffffff` in both themes replaces the literal on the button; the skill's table
  gains the row.
- Panels: `padding: 40px 32px`; `margin-bottom: 16px`; the frame's gap 24 px. At 720 px the
  content panel is 486 px wide and the form's `minmax(120px, 220px) minmax(0, 280px)` columns
  fit in the 422 px inside it; the 360 px layout stacks as before.
- Buttons: 30 px, weight 400, `linear-gradient(to right, …)`, `box-shadow: 0 0 4px var(--glow),
  0 4px 4px var(--glow)`, `:hover { opacity: .75 }`, `:disabled { background: var(--input-line);
  box-shadow: none; opacity: .5 }`, focus `outline: 2px solid var(--primary-1); outline-offset:
  2px`.
- Inputs: `padding: 0 12px`; focus keeps the border and offsets the outline 2 px;
  `::placeholder { color: var(--muted) }`; `:disabled { background: var(--tint) }`.
- `.action`, `.state`, `.band-link`: weight 400. `.tag`: 13 px, `1px solid var(--primary-text)`,
  text `--primary-text`, no fill; the skill's §9 gains the sentence.
- Tables: `td { padding: 18px 12px }` (56 px rows); `fillTable` and `loadAdapters` write "---";
  the empty queue is one `td` with `colspan` and the muted line.
- Sign-in: `.signin-wrap` paints `linear-gradient(135deg, var(--band-1), var(--band-2))` with a
  `.signin-top` row (mark 52 px, name 24 px bold) in `--band-ink` above the card; the card's
  `box-shadow: 0 0 100px var(--halo)` and `padding: 36px 44px`.
- The footer is one `<footer>` at the end of `main`, after the pages, painted as the tail of
  the last visible panel: that panel loses its bottom radius and margin
  (`.page:not([hidden]) > .panel:last-child`), and the footer carries `--panel`, the bottom
  radius, the panel's side padding and an inner row with a top hairline. The row is
  right-aligned and holds one `a.foot-action`: uppercase 14 px in `--text` with a 16 px line
  icon (a branch, drawn for wanpire) before it, labelled "Source", linking to the repository
  with `rel="noopener"`. A link is not a fetch, so the nothing-from-elsewhere test is unmoved.
- The band's transition 0.3 s; the place chevron's 0.2 s.

Not taken: a wine gradient only when a link is applied on the sign-in page (the page has no
session yet and may not read the status); the host's own mark as the icon (the page names no
vendor; the address is the link's, not the page's); a footer inside every page's last panel
(five copies of one line).

### D9. Two tests hold the rules

- `tests/unit/test_web_style.py` reads `style.css` as text, strips the two `:root` blocks, and
  asserts: no `#rgb`, `rgb(`, `hsl(` or named colour outside them (a short allow-list for
  `transparent`, `currentColor`, `none`); every `font-weight` in {400, 700}; every `font-size`
  in {13, 14, 16, 20, 22, 24} px; every `border-radius` value in {5, 6, 8, 10} px or 50 %;
  no `box-shadow` on a selector matching `.panel`, `.card`, `.table`, `td` or `.place`; every
  transition duration in 0.2 to 0.3 s; no `@import`, `url(http` or `@font-face`. It also reads
  `index.html` and asserts no `style="` with a colour and no `<link>` to another host, with the
  mark's `<symbol>` exempt. It runs on any machine, no browser.
- `tests/ui/test_look.py` gains: the band's rows and height (D1); the menu's tint, height, bar
  width and child weights (D2); panel padding-top 36 to 44 px and 16 px between panels; primary
  buttons 28 to 30 px with `text-transform: uppercase`, and no `.secondary` anywhere; table rows
  50 to 62 px; the accent counted exactly twice on the Endpoints page with Tokyo open; the
  sign-in page's background gradient and top row; the dialog's backdrop and one primary; the
  eye. `test_no_sideways_scroll_and_aa_contrast` is parametrised over 360, 720 and 1,280 px.
  The accent count reads every element's computed `background-color` against the resolved
  `--accent`, so a stray accent anywhere fails it.

Not taken: a visual regression suite of screenshots (brittle; the rules are numbers); linting
the CSS with an external tool (a dependency for a 40-line test).

## Risks / Trade-offs

- [The 720 px layout could overflow with wider panel padding and the fixed form columns] →
  the columns are `minmax`, the preview card wraps with `overflow-wrap`, and the look test's
  scroll-width check at 720 px fails before the change lands.
- [The band's growth to 180 px changes the first impression] → within the skill's amended
  tolerance; the owner reviews the screenshots in the journal entry.
- [The message move changes where "Applied." appears; a person used to the top line looks
  there] → the line is under the button they just pressed; the top keeps the errors.
- [The dialog's tests race the native `<dialog>` open] → Playwright waits for `#end-dialog` to
  be visible before filling.
- [The static test is stricter than the skill in places (an allow-list of values)] → each
  assertion names the skill's section; a rule the page needs later is added to the skill and the
  test together, as the skill asks.
- [Nothing here was rendered before planning] → task 1.1 renders first and amends the tasks if
  the screenshots show a deviation the source review missed.
