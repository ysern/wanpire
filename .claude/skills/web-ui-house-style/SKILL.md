---
name: web-ui-house-style
description: Use when building, changing or reviewing wanpire's web page — any section, the set-up and sign-in cards, the band, a form, a table, a status card — for its settings-console look: page and band, navigation, side menu, section anatomy, forms, buttons, tables, read-only status, dialogs, type, colour, and a review checklist with a report format.
---

# The web UI house style

wanpire's page wears one look: a light page, white panels with soft corners and no shadows, one coloured
band carrying the name and the top-level sections, and settings laid out as calm two-column forms. Text
is small, there are almost no borders, and there is generous white space. One primary action per section;
everything else is a text link. The look is deliberately that of a settings console, not a marketing site
and not a dashboard. It lives in one stylesheet, `src/wanpire/web/style.css`, and one page,
`src/wanpire/web/index.html`; `tests/ui/test_look.py` measures it.

**Take the style, never a brand.** The palette is wanpire's own: a wine primary, a vampire on the wire, and
the deep wine as the accent for what is active. Nothing in this file names anyone else's colour, and no page may
introduce one. No provider, vendor or trademark is named in the page or its artwork.

The rules are measured. Where a number is given it is the target, with the tolerance stated; where a word is
given ("about", "roughly") the proportion matters more than the pixel.

## 1. The page

- **Width:** the page works from **720 px** up with nothing scrolling sideways, and at 1280 px it is the
  settled layout. On a phone (360 px) the menu and the form's columns stack, as a stretch, still with
  nothing scrolling sideways. The look test runs at 360, 720 and 1280 px, in both themes. The content
  column is **about 1070 px**, centred; the band spans the full width but its contents align to that
  same column.
- **Background:** a light neutral grey, `--page` (`#f3f3f3` in light). Panels are white, `--panel`,
  **radius 10 px**, **no shadow**. Panels stack **16 px** apart.
- **Two layouts.** A *wide* page is one white panel the full column wide. A page with sub-pages puts a
  **side menu about 178 px** on the left and a white content panel to its right, 24 px between them.
- **Padding inside a panel:** generous. About 40 px top, and 40 to 90 px at the sides (less beside a side
  menu, where the content panel is narrower). Content never touches a panel's edge.
- **A footer**, when there is one, is inside the last panel under a hairline: uppercase 14 px text actions
  with a small line icon each, right-aligned, in the body text colour. wanpire's has one: "Source", a branch
  icon, linking to the repository; the host is not named.
- **Themes:** light and dark, decided by `prefers-color-scheme`, both meeting WCAG 2.2 AA; no class names a
  theme. Every colour comes from a custom property on `:root`. A rule that paints a literal colour is
  wrong before it is looked at.

## 2. The band and the top-level navigation

- **One band, 160 to 180 px tall**, full width: the brand row and the sections make 160, and the link line
  under the mark adds its own row (about 175 at 1,280 px). **It shows the link:** with no link applied it is a calm
  pastel of the wine (`--calm-1` to `--calm-2`, its text and icons in `--calm-ink`); with a link applied it
  is the wine gradient (`--band-1` to `--band-2`, text and icons in `--band-ink`). A short line under the
  mark, aligned to its left, says which, in the API's own form (`london:generic <> los-angeles:generic`,
  `set by figures`, `no link`). No photograph, no illustration beyond the mark.
- **Top row:** the mark (52 px), the name in 24 px bold with a 13 px tagline under it, all in the band's
  ink. Utility links, when any, at the right as a small line icon plus a 13 to 14 px label.
- **Second row: the top-level sections** — Link, Broker, Adapters, Endpoints, Settings — left-aligned on
  the column, 16 px apart: the same gap the band keeps to the frame below it. Each is a **44 px circle with a 1.5 px outline in the band's ink holding a line icon**, and a
  13 to 14 px label under it. **The active section's circle is filled with the accent, its icon in
  `--on-accent`, and its label is bold.** That filled circle is the only accent on the band and, with the
  open side-menu group, the only accent on the page.
- Hover underlines the label or softens the circle; nothing moves.

## 3. The side menu

- A pale panel, `--tint` or the page grey, about 178 px wide, radius 10 px, the same height as the content
  beside it. Below 720 px it goes on top of the content, as one row.
- **Items 40 px tall**, 14 px text in the body colour, 16 px side padding. A group with children shows a thin
  chevron at the right.
- **The open group is a full-width accent-filled bar** with its text in `--on-accent`. **Its children list
  directly under it**, indented 12 px: the current child is marked with a small **primary dot** at the
  left, bold, in the body colour; its siblings are in the muted colour.
- Nothing else in the menu is coloured. No icons on children, no counters, no dividers.

## 4. Section anatomy

Every section of a page, whether a form, a status card or a table, has the same head:

1. **A title**, 16 px, weight 700, body colour.
2. **One sentence** saying what the section is for, 14 px, in the muted colour, directly under the title.
3. **A hairline**, 1 px, `--hair`, the full width of the content.
4. The body, starting about 24 px below.

A section's **secondary actions sit at its top right, above the body**: primary-coloured 14 px text
(`--primary-text`) with an optional small line icon ("Refresh", "Edit"). **A destructive action ("Clear",
"End another's lease") is text in `--danger`**, in the same row. No boxes around any of them.

A page-level title, used only on an overview page, is 20 px regular, centred, and stands alone above a tab
bar. Use it once, if at all.

## 5. Forms

- **Two columns.** The label at the left, **about 270 px wide in a wide panel and about 220 px beside a
  side menu**, 14 px, ending in a colon. The control at the right, **about 350 px wide in a wide panel and
  about 280 px beside a side menu**. A third, optional column to the right of the control holds a
  contextual link in the primary colour, a related checkbox, or a grey hint ("(Optional)"). On a phone the
  label stacks above its control.
- **Rows are about 44 px apart** with no borders, rules or stripes between them.
- **A label is bold when it is a feature's master switch or a group's head**, and regular for the fields under
  it. "Hold the link:" bold with its choice; the fields it opens, regular below it.
- **Inputs and selects:** 28 to 30 px tall, `--input` fill, 1 px border in `--input-line`, radius 5 px,
  14 px text, 12 px side padding. A select has a thin chevron at the right. A password field has a
  show/hide eye icon inside it at the right. A disabled field has a pale grey fill. Focus is a 2 px
  outline in `--primary-1`, offset 2 px. Placeholder text is in the muted colour.
- **A unit** sits inside the input at the right, in the muted colour ("ms", "%"). **A range** is two inputs
  with a short dash between them. **A pair of choices** (the two ends of a link, a city and its channel) is
  a row of equal selects, `.pair`.
- **Help text** sits under the control, 13 px, muted, wrapping at the control's width. What is wrong with a
  field is said there, beside the field, in `--danger`, before anything is sent.
- **Checkbox:** a 16 px square with radius 3 px, a 1 px border; primary-filled with a white tick when on,
  followed by one word ("Enabled"). A checkbox is a setting that takes effect with the section's button.
- **Toggle switch:** a pill about 38 by 20 px, primary when on, grey when off, with a white knob. A toggle is
  **live** state that applies at once. Do not mix the two meanings.
- **An inline help icon:** a small primary-filled circle with a white "?", to the right of the label or the
  checkbox word, opening a tooltip.
- **Collapsed advanced settings** sit behind a primary disclosure triangle and a primary text link.
- **Radio choices** are vertical, each a 16 px circle with its word; a chosen one is primary-ringed.

## 6. Buttons

- **Primary:** the full width of the control column, 28 to 30 px tall, radius 5 px, the wine gradient
  (`--primary-1` to `--primary-2`, left to right), white **uppercase** 14 px text, and a soft glow under it
  (`0 0 4px --glow, 0 4px 4px --glow`). **One per section at most**, and the look test counts them. A
  button that stands alone in a section is placed at the control column, not centred and not at the left.
  Two primary buttons in one section only when they are alternatives of one action, stacked 16 px apart.
- **Secondary:** the same size, `--panel` fill, 1 px outline and uppercase text in `--primary-text`.
- **Disabled:** grey fill at half opacity, no glow.
- **Hover:** opacity about 0.75; **active:** no movement, no darkening beyond that.
- **A text action** (`.action`): 14 px text in `--primary-text` with no box, underlined on hover. **A row
  action:** a small primary line icon with no box.
- **A status line under a button:** muted, centred under it.
- A button never carries a colour other than the primary, and never a shadow other than the glow.

## 7. Tabs

A segmented bar the content width: equal cells, 1 px outline in `--primary-1`, radius 5 px on the ends,
14 px bold text. **The active cell is primary-filled with white text; the others are `--panel` with text in
`--primary-text`.** Used for views of one subject, not for navigation between pages.

## 8. Read-only status

- **A list of values** in a form-like page: "Label:" at the label column and the value at the control
  column, 14 px body colour, rows about 38 px apart. Groups are separated by a hairline, each with a bold
  14 px group head. Nothing is boxed.
- **A status card** (`.card`), for the link's figures, the counters and the box's state: a pale tinted panel
  (`--tint`), radius 10 px, with a bold 16 px title when the card is not its section's whole body (then
  the section's title serves), holding a white inner panel with **two columns of
  "label:" left and value right-aligned**, the values bold with tabular figures, split by a vertical
  hairline when there are two groups.
- **State words** take their colour from their meaning only: `--good`, `--warn`, `--danger`. Never for
  decoration.
- **Counters on an icon** are a small accent circle with a white number at the top right.

## 9. Tables

- **The table is a pale tinted card** (`--tint`), radius 10 px, 8 to 16 px padding. **The header row** is
  bold 14 px body colour on the tint, no rule under it.
- **Each data row is its own rounded pill** in `--pill`, radius 6 to 8 px, **about 56 px tall**, with
  **6 to 8 px of the tint between rows** (`border-spacing`). There are **no grid lines** and no zebra
  stripes.
- Columns align with the header; the first column may start with a line-art icon in the primary colour. A
  cell may carry a second, smaller line in the muted colour under the main one. A missing value is "---".
- Live state in a row is a toggle; actions are primary line icons in the last column.
- **The empty state** is one pill holding one muted line ("No entries.").
- **Expandable rows** (`.place` on the Endpoints page) carry a chevron at the left that turns down when
  open; what opens is a grid of `.channel` cards on the tint, each with a bold name, a `.tag` (one 13 px word in `--primary-text` with a 1 px
  outline of the same, radius 10 px, no fill: the accent is for the active item), a muted sentence and a small right-aligned figures table with tabular numbers.
- No pagination controls unless the table is long; then simple numbered pages, 32 px squares, no borders.

## 10. Log and text views

A bordered box the content width: 1 px `--hair` border, radius 5 px, fixed height with its own scrollbar,
16 px padding, the body font at 14 px (not monospace), one entry per line. Above it: a filter select at the
left, then a search input with a magnifier inside its right end, and the section's "Refresh" and "Clear"
actions at the right of the same row.

## 11. Dialogs, tooltips and messages

- **A modal dialog:** a `--panel` box, radius 10 px, no visible border, over a scrim of about 45% black (`--scrim`).
  Its header strip is the tint with a 16 px bold title and a muted close cross at the right; its body is a
  form by the rules above; its actions are one primary button and one text action.
- **A tooltip:** a tinted popup, radius 5 px, a 2 px soft drop shadow at 12% black, 14 px body text, at most
  300 px wide, with a small arrow.
- **A message in a section:** one line of muted text where the result belongs, under the button or the
  field; the band carries what the box is doing, so the message keeps a short acknowledgement only. A
  success is stated, not celebrated; no green banners. An error in a section is a `--danger` line.
- **A loading state** is a primary spinner in place, never a skeleton screen.

## 12. The set-up and sign-in cards

- **The whole page is the band's colour** behind the card, the wine gradient `--band-1` to `--band-2`
  whatever the link's state (the page has no session yet), with at most a faint pale wave at the bottom.
  The top row is the mark (52 px) and the name (24 px bold) in `--band-ink`, on the column; the card keeps
  its own mark.
- **A centred white card, about 420 by 480 px** (the test allows 380 to 460 wide, centred within 4 px),
  radius 10 px, with a very large soft wine-tinted halo (`0 0 100px --halo`). It holds, with about 44 px
  side padding: the mark (56 px, centred); a **centred bold 22 px title** with a muted lead line; bold
  14 px labels above full-width inputs (the one place a label sits above its control); a full-width
  primary button; and a **right-aligned text link** under the button when there is a second way in.
- The card never names a host, an address or a person: placeholders only, as the public repository asks.

## 13. Type and colour

| Token kind | Rule |
| --- | --- |
| Font | The system's sans-serif stack (Helvetica Neue, Arial, system-ui). Nothing fetched. `code` at 13 px. |
| Sizes | **14 px** for everything by default. 13 px for help text, tags and the band's tagline. 16 px for section titles. 20 px for a page-level title. 22 px for the card's title, 24 px for the name on the band. Nothing larger in text; icons may be. |
| Weights | 400 for body. **700** for titles, group heads, master-switch labels, table headers, the active nav label, the card's labels, a status card's values. No 500 or 600. |
| Line height | 1.45 for body; titles at about 1.2. |
| Text | A dark slate (`--text`), never pure black. |
| Muted | For descriptions, help, placeholders, inactive menu items and secondary cell lines (`--muted`, `#646c71`). **It must still pass AA on white and on the tint:** a lighter grey reads right but fails 4.5:1, which is why the value is as dark as it is (5.4:1 on white, 4.8:1 on the tint). |
| Hairline | 1 px in `--hair`, a light neutral. |
| Primary | Band when live, buttons, links, actions, checkmarks, toggles, focus, dots, line-art icons. White on it (`--on-primary`) passes AA at both ends of the gradient (7.6:1 and 11.9:1). Links and actions on a panel use `--primary-text`, which the dark theme lightens. |
| Accent | **The active item and counters only:** the active nav circle, the open menu group, a counter badge. Never a button, never text on white. |
| Danger, good, warn | State and destructive actions. Never decoration. |
| Radii | **10 px** panels, cards, dialogs, menu. **5 px** inputs, buttons, tabs, log boxes. **6 to 8 px** table-row pills and channel cards. **50%** icon circles and dots. 20 px toggles. |
| Shadows | **None on panels, cards or rows.** The button glow, the card's halo, a 2 px tooltip shadow. Nothing else. |
| Motion | 0.2 to 0.3 s ease on colour and opacity. Nothing slides, bounces or scales. |
| Icons | Line icons, 1.5 to 1.7 px stroke, inline SVG drawn for wanpire, in the primary colour on panels and in the band's ink on the band. No icon font, no filled icons, no emoji, no icon in running text. |
| Uppercase | Buttons and a footer's actions. Nowhere else. |
| Density | 44 px form rows, 40 px menu rows, 56 px table rows, 16 px between panels. Do not tighten these to fit; let the page scroll. |

### wanpire's palette

The values a reviewer compares against are the custom properties at the top of `src/wanpire/web/style.css`,
which is the one source; this table is a copy for reading, and the file wins where they differ.

| Role | Property | Light | Dark |
| --- | --- | --- | --- |
| Page | `--page` | `#f3f3f3` | `#121316` |
| Panel | `--panel` | `#ffffff` | `#1c1e22` |
| Text | `--text` | `#36444b` | `#dfe3e6` |
| Muted | `--muted` | `#646c71` | `#9aa3a8` |
| Hairline | `--hair` | `#e6e6e6` | `#2c2f35` |
| Tint (tables, status cards, channel cards) | `--tint` | `#f5f7fa` | `#23262b` |
| Table-row pill | `--pill` | `#ffffff` | `#2b2e34` |
| Input fill | `--input` | `#ffffff` | `#15171a` |
| Input border | `--input-line` | `#cfd4d8` | `#454a52` |
| Primary gradient (buttons) | `--primary-1` to `--primary-2` | `#a0213a` to `#6e1022` | the same |
| Primary as text on a panel | `--primary-text` | `#a0213a` | `#ff8fa3` |
| Band with a link | `--band-1` to `--band-2`, ink `--band-ink` | `#a0213a` to `#6e1022`, `#ffffff` | `#7d1729` to `#4f0b18`, `#ffffff` |
| Band with no link | `--calm-1` to `--calm-2`, ink `--calm-ink` | `#f7e6ea` to `#efd3da`, `#5a0d1c` | `#2b2427` to `#231c1f`, `#ecd7dc` |
| Accent (active only) | `--accent` | `#6e1022` | `#6e1022` |
| Text on accent | `--on-accent` | `#ffffff` | `#ffffff` |
| Text on a primary button | `--on-primary` | `#ffffff` | `#ffffff` |
| A dialog's scrim | `--scrim` | black at 45% | black at 45% |
| Button glow | `--glow` | wine at 35% | `#ff8fa3` at 22% |
| Card halo | `--halo` | wine at 16% | `#ff8fa3` at 10% |
| Danger | `--danger` | `#b3261e` | `#ff8a80` |
| Good | `--good` | `#1e7d3c` | `#6fd38d` |
| Warn | `--warn` | `#8a5a00` | `#f2c14e` |

The primary is a wine red deep enough that white on it passes AA at both ends; the accent is the deep wine (`#6e1022`, the gradient's far end) so that the active item wears the
page's one colour and still stands off the live band's light end, with white on it (11.9:1); the calm band is a pastel of the same wine so that the band
changes meaning without changing family. Where this file says "primary", "accent", "tint" or "muted", it
means these properties.

## 14. What the style never does

- No dark panel on a light page, no coloured section backgrounds, no card with its own shadow.
- No more than one accent on screen beyond the active markers, and no colour used for decoration alone.
- No illustration in a form, no hero image, no icon in body text.
- No borders between form rows, no grid lines in tables, no zebra striping.
- No button that is not uppercase, no two primaries side by side, no button in a table row.
- No label to the right of its control, except a checkbox's own word.
- No web font, no icon font, no CSS framework, no fetch of any kind from anywhere but the box itself.
- No sideways scroll at any width from 360 px up.
- No host, address, MAC, SSID or person's name in the page, its examples or its tests: placeholders only.

## 15. Reviewing the page

Review the rendered page, not only its source: the rules are about what a person sees.

1. **Render** the page at 360, 720 and 1280 px wide in both themes, headless, and keep the screenshots out
   of git. `tests/ui/test_look.py` renders it with Playwright against the real app on a free port with a
   recording engine: `WANPIRE_SHOTS=<stage> pytest tests/ui/test_look.py -k screenshots` draws every page
   at the three widths in both themes into `tests/ui/shots/<stage>/`.
2. **Walk the checklist** in order, section by section of the page, comparing against sections 1 to 14
   above. For each rule, record *pass*, *deviation* or *missing*. A deviation says what the page does, what
   the rule says, and the measured number where a number applies.
3. **Check the source for the causes that screenshots hide** (`tests/unit/test_web_style.py` does, without
   a browser): a literal colour outside the `:root` blocks;
   a weight of 500 or 600; a shadow on a panel; a font-size other than 13, 14, 16, 20, 22 or 24; a radius
   other than 5, 6, 8, 10 or 50%; a media query that breaks the columns above 720 px; a fetch to any host;
   a value in an example that is not a placeholder.
4. **Check both themes for contrast**, every text-on-background pair at WCAG 2.2 AA (4.5:1 for text, 3:1 for
   large text); behind a gradient both ends count. The look test measures every visible text; a colour a
   page adds is covered by it or the test is extended first.
5. **Rank the findings.** *Breaks the look*: a wrong layout kind, a second accent, shadows on panels, a
   non-uppercase or boxed secondary button, a bordered or striped table, a label column that is not a
   column, a sideways scroll. *Off-measure*: sizes, spacing, radii, weights outside the rule by more than
   the tolerance. *Polish*: a missing hover state, a missing empty state, a help text in the wrong place.

### Report format

```
## <Page or section> — house-style review, <date>, <widths> px, light and dark

| # | Where | Rule (section) | Seen | Expected | Rank |
|---|-------|----------------|------|----------|------|
| 1 | Adapters table | 9 rows | 1 px grid lines, 40 px rows | pills, 56 px, 6 to 8 px gaps | Breaks the look |

Passes: <the sections that passed, in one line each>
Not reviewable: <states the review could not reach, and why>
```

A review changes nothing by itself. A fix is a change to the stylesheet or the page, test-first, as every
wanpire change is; a rule the fix needs and this file lacks is added here in the same change.
