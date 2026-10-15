## The web page — house-style review, 2026-10-15, source review, light and dark

Reviewed against `.claude/skills/web-ui-house-style/SKILL.md` (section numbers below are its),
reading `src/wanpire/web/style.css`, `index.html` and `app.js`, with the measured numbers taken
from the stylesheet. The page was then rendered on 2026-10-15 at 360, 720 and 1,280 px in both themes
(`WANPIRE_SHOTS=before pytest tests/ui/test_look.py -k screenshots`, the shots in
`tests/ui/shots/before/`, out of git): every finding below was seen as described, and the
render added none. The layout numbers in "Seen" are the stylesheet's declared values.

| # | Where | Rule (section) | Seen | Expected | Rank |
|---|-------|----------------|------|----------|------|
| 1 | Band | 2, the band's rows | One row: the brand at the left, the sections at the right (`.band-inner` flex, `space-between`) | A top row (mark, name, tagline) with the link line under the mark, and a second row of sections evenly spaced on the column | Breaks the look |
| 2 | Band, link line | 2, 13 font | `700 16px ui-monospace, Menlo, Consolas` | The system sans-serif, 14 px, weight 400; monospace is for `code` only | Off-measure |
| 3 | Band | 13 motion | `transition: background 0.4s` | 0.2 to 0.3 s | Off-measure |
| 4 | Band, sections | 2 hover | No hover rule on `.sections a` | The label underlines or the circle softens | Polish |
| 5 | Band, sections below 600 px | 13 sizes | Labels 12 px | 13 px is the smallest size | Off-measure |
| 6 | Side menu | 3 background | `--panel` (white) | `--tint` or the page grey | Breaks the look |
| 7 | Side menu | 3 height | `align-items: start`: the menu is as tall as its items | The same height as the content beside it | Off-measure |
| 8 | Side menu, open group | 3 the open group | Inset bar: `margin: 0 8px`, radius 6 px | A full-width accent bar | Breaks the look |
| 9 | Side menu, children | 3 colours | Every child in `--text` | The current child bold in the body colour; its siblings in `--muted` | Off-measure |
| 10 | Side menu, items | 3 density | 8 px vertical padding: about 36 px tall; text at 30 px | 40 px tall; children indented 12 px past the 16 px padding | Off-measure |
| 11 | Side menu, group | 3 chevron | None | A thin chevron at the right of a group with children | Polish |
| 12 | Frame | 1 two layouts | 18 px between the menu and the content panel | 24 px | Off-measure |
| 13 | Panels | 1 padding, 13 density | `padding: 22px 24px`, 18 px between panels | About 40 px top, 32 to 40 px at the sides beside a menu; 16 px between panels | Off-measure |
| 14 | Footer | 1 footer | A loose muted 13 px line under the panels, "wanpire, an open-source link emulator" | A footer is inside the last panel under a hairline and holds uppercase text actions; the page has none | Off-measure |
| 15 | `#message` | 11 messages | A white panel at the top of the main column for every result ("Applied.", "Released.", errors) | One line of muted text where the result belongs, under the button; a `--danger` line for an error | Breaks the look |
| 16 | Section head actions | 4, 13 weights | `.action` weight 700 | 14 px regular text in `--primary-text` | Off-measure |
| 17 | Link section, Clear | 4 destructive actions | Clear in `--primary-text` | A destructive action is text in `--danger` | Off-measure |
| 18 | Broker section, End this lease | 4, 6, 14 | A boxed `secondary danger` button, not uppercase, under the table | A `--danger` text action in the section's head row | Breaks the look |
| 19 | Settings, Sign out | 6 secondary | A boxed secondary button, 32 px, not uppercase, not at the control column | The section's one action: a primary at the control column (or an uppercase secondary) | Breaks the look |
| 20 | Settings, Signed in as | 8 list of values | A one-row `.card` | A "Label:" at the label column and the value at the control column | Polish |
| 21 | Forms, columns | 5 two columns | `minmax(120px, 270px)` and `minmax(0, 350px)`: the wide-panel widths, beside a menu on every page | About 220 px and 280 px beside a side menu | Off-measure |
| 22 | Forms, group heads | 5 bold labels | "Hold the link:", "Inbound adapter:", "Outbound adapter:" regular | Bold: the skill names "Hold the link:"; the adapter drop-downs open the Wi-Fi fields under them | Off-measure |
| 23 | Inputs | 5 inputs | 8 px side padding; focus outline offset 0 with the border made transparent | 12 px side padding; a 2 px outline in `--primary-1` offset 2 px | Off-measure |
| 24 | Inputs | 5 placeholder, disabled | The browser's placeholder grey; no disabled fill | Placeholder in `--muted`; a disabled field in a pale grey | Polish |
| 25 | Password fields | 5 inputs | Plain password fields (sign-in, set-up, change the password) | A show/hide eye icon inside the field at the right | Polish |
| 26 | Primary button | 6 primary | 34 px tall, weight 700, gradient at 135°, glow `0 4px 14px`, no hover, disabled keeps the gradient and the glow at 0.45, focus ring in `--accent`, text `#ffffff` literal | 28 to 30 px, weight 400, gradient left to right, glow `0 0 4px, 0 4px 4px`, hover opacity 0.75, disabled grey at half opacity with no glow, focus in the primary, the colour from a token | Off-measure |
| 27 | Status line under a button | 6 | `#roles-message`, `#pw-message` left-aligned | Muted, centred under the button | Polish |
| 28 | Lease state line | 13 weights | `.state` weight 700 | 400: it is not a title or a group head | Off-measure |
| 29 | Status cards | 8 status card | The tint panel holds the two columns directly; no vertical hairline between the two groups | A tint panel holding a white inner panel; the two groups split by a vertical hairline; a title when the card is not the section's whole body | Off-measure |
| 30 | Status cards | 8 rows | Rows about 34 px apart | About 38 px | Off-measure |
| 31 | Tables | 9 rows | Rows about 38 px tall (`padding: 9px 12px`) | About 56 px | Off-measure |
| 32 | Tables, missing values | 9 | "-" | "---" | Polish |
| 33 | Broker table, empty | 9 empty state | Five cells, "nobody" in the second | One pill holding one muted line | Polish |
| 34 | Endpoints, place chevron | 13 icons | A text glyph "▸" at 16 px | A line drawing, not an icon in text | Polish |
| 35 | Endpoints, channel tag | 13 accent, 2 | "default" on an accent fill, 12 px | The accent marks the active item only; 12 px is not a size | Breaks the look |
| 36 | Messages of success | 11 | "help good": green text for "The roles are saved" and "The password was changed" | A success is stated in muted text; green is for state words | Polish |
| 37 | End another's lease | 11 dialogs | The browser's `window.prompt` | A modal dialog: tint header strip with a bold title and a close cross, a form body, one primary button and one text action, over a 45 % scrim | Off-measure |
| 38 | Set-up and sign-in page | 12 | The card on the page grey; no top row | The whole page the band's colour, the mark and the name in a top row | Breaks the look |
| 39 | Sign-in card | 12 | Halo `0 0 140px 50px`; 40 px side padding | `0 0 100px --halo`; about 44 px | Off-measure |
| 40 | Stylesheet | 1 themes, 13 | `color: #ffffff` on the primary button, outside `:root` | Every colour from a custom property | Off-measure |
| 41 | Look test | 1 width, 15 | Scroll and contrast measured at 720 and 1,280 px (360 px only for the set-up card and an open place) | 360, 720 and 1,280 px, both themes, every page | Off-measure |

Passes:
- 1 Page: light grey page, white panels, radius 10 px, no shadow on any panel; the content column 1,070 px; both themes by `prefers-color-scheme`; no class names a theme.
- 2 Band: 160 px tall; calm pastel with no link and the wine gradient with one; the mark at 52 px, the name 24 px bold, the tagline 13 px; 44 px circles with a 1.5 px outline and 1.7 px line icons; the active circle accent-filled with its label bold; the band's inks from tokens.
- 4 Section anatomy: title 16 px bold; one muted 14 px sentence; a hairline; secondary actions at the top right.
- 5 Forms: labels left ending in a colon; rows 44 px apart with nothing between them; inputs 30 px, radius 5 px, token fill and border; the `.pair` row of equal selects; help text 13 px muted under the control; errors in `--danger` beside the field before anything is sent; labels stack on a phone.
- 6 Buttons: one primary per section (counted by the test); full width of the control column; uppercase.
- 8 State words: `--good` and `--warn` by meaning only.
- 9 Tables: a tint card, radius 10 px; bold header on the tint with no rule; rows as `--pill` pills with 6 px of tint between them; no grid lines, no stripes, no button in a row; places open with a chevron to a grid of `.channel` cards with a bold name, a muted sentence and a right-aligned figures table with tabular numbers.
- 12 Card: 420 by 480 px, radius 10 px, centred within 4 px; centred 22 px title with a muted lead; bold 14 px labels above full-width inputs; a full-width primary; placeholders only.
- 13 Type: the system sans stack, nothing fetched; 14 px body, 13 px help and tags, 16 px titles; `--text` a dark slate; `--muted` 5.4:1 on white; radii 5, 8, 10 and 50 %; icons inline SVG, line-drawn, 1.7 px stroke; uppercase on buttons only.
- 14 Nothing fetched from elsewhere (tested); no label to the right of a control; no web font, icon font or framework.

Not reviewable:
- The rendered page at 360, 720 and 1,280 px: no browser on the reviewing machine. The numbers above are the stylesheet's.
- Toggle switches, checkboxes, radio choices, help icons, disclosures, tabs, log views, counters on icons, units in inputs, ranges, tooltips, spinners: the page has none.
- The mark's own colours (`#i-mark` in `index.html`, in blue, red and green): the mark is the `logo` capability's, still waiting for the owner's pick (A53); a picked logo replaces it in a change of its own.
