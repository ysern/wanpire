## 1. Render and settle the findings

- [x] 1.1 On a box with Playwright, add a screenshot helper to `tests/ui/test_look.py` (kept out of git: `tests/ui/shots/` in `.gitignore`) and render every page at 360, 720 and 1,280 px in both themes before any change; compare with `review.md` and add to it any deviation the source review missed; verify the shots exist and the review's table is updated
- [x] 1.2 Write `tests/unit/test_web_style.py` (design D9) against the current stylesheet and verify it fails on the literal `#ffffff`, the 700 weights, the 12 px sizes, the 6 px menu radius and the 0.4 s transition
- [x] 1.3 Extend `tests/ui/test_look.py` with the measured rules (D9: band rows and height, menu, panels, buttons, table rows, accent count, sign-in page, eye, dialog) and parametrise the scroll-and-contrast test over 360 px; verify the new tests fail on the current page and the old ones still pass

## 2. Tokens, band and menu

- [x] 2.1 Add `--on-primary` to both `:root` blocks and use it on the primary button; verify the static test's colour check passes
- [x] 2.2 Restack the band (D1): the brand row, the 14 px body-font link line, the sections row evenly spaced, hover underline, 0.3 s transition, 13 px labels at every width; verify the band tests and the band contrast test pass at 360, 720 and 1,280 px
- [x] 2.3 Rebuild the side menu (D2): tint, stretched height, full-width accent group with a CSS chevron, 40 px items, 28 px child indent, muted siblings; verify the menu tests pass and the below-720 row layout still has no sideways scroll

## 3. Panels, forms, buttons and cards

- [x] 3.1 Set the panels' padding and spacing, the frame's 24 px gap, the 220/280 px form columns, and turn the footer into the last panel's action row with the "Source" link and its branch icon (D8); verify the panel and footer tests and the 720 px scroll-width test pass
- [x] 3.2 Retune inputs (12 px padding, focus ring, placeholder, disabled fill) and make the group-head labels bold in `index.html`; verify the static test and the forms' contrast at every width
- [x] 3.3 Retune the primary button (D8) and `.action`, `.state`, `.band-link` to weight 400; delete `.secondary` and `.buttons`; verify the button tests pass and no `.secondary` is found on any page
- [x] 3.4 Restructure `.card` (D7): inner panel, `.two` hairline, `.card-title` on the preview, 38 px rows; amend the skill's §8 with the title rule; verify the cards' contrast and the one-primary count at every width
- [x] 3.5 Add the password eye (D6) to the five password fields with its sprite symbol and the toggle handler; verify the eye test shows and hides the text

## 4. Actions, messages and the dialog

- [x] 4.1 Write the failing UI tests for the moved messages (`#link-message` "Applied" and "Cleared", muted success, danger refusal, top-line error) and the danger text actions, then route `say()` by place (D3) and move Clear, End this lease and Sign out (D4); verify those tests and `test_web_ui.py` pass
- [x] 4.2 Rewrite the two end-another's-lease tests to use `#end-dialog`, then build the dialog (D5) and remove `window.prompt`; verify both tests pass, cancelled and confirmed, and the dialog's contrast in both themes

## 5. Tables, places and the sign-in page

- [x] 5.1 Set table rows to 56 px, write "---" for missing values in `app.js`, and render the empty queue as one muted pill; verify the table tests and `test_adapters_page.py` pass
- [x] 5.2 Replace the "▸" glyph with the CSS chevron and restyle `.tag` as an outlined primary word at 13 px; amend the skill's §9; verify the accent-count test passes with Tokyo open
- [x] 5.3 Paint the sign-in page in the band's colour with the top row, and set the card's halo and padding (D8); amend the skill's §12; verify the sign-in and set-up tests pass at 360 and 1,280 px in both themes

## 6. Close

- [x] 6.1 Run the whole suite (`pytest tests/unit tests/ui`) and the static test on this machine; verify everything passes and the screenshot run of 1.1 shows the finished page at the three widths in both themes
- [x] 6.2 Record the assumptions in `docs/open-questions.md` (the footer's "Source" action, band 160 to 180 px, card titles, tag colour, Sign out as primary, the wine sign-in page, the mark untouched), amend the skill's §2 height and palette table, and write the journal entry; verify the three files mention this change
