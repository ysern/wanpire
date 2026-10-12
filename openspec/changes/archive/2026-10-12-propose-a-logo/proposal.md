## Why

wanpire needs a face for its README, its web page's favicon and the article that will present
it. The owner's idea (the plan's B8): the vampire is the small computer itself, in its case,
sitting on the line and sucking the traffic. Nothing is final until the owner picks.

## What Changes

- **A few logo proposals** in `docs/logo-proposals/`, each as three SVGs: in full colour, in one
  colour, and simplified for a favicon (16 and 32 px), with a page showing them side by side.
- **The idea, read by the agents:** a generic small-computer case, two-tone, a grey rounded lid
  over a black base, ports along its sides; the lid's front is a cartoony face with big eyes;
  two fangs bite into an Ethernet cable, and packets drain from the cable into the mouth;
  perhaps a cape's collar.
- **Colours from the web page's palette:** the wine red (`#a0213a` to `#6e1022`) and the amber
  accent (`#f2b134`), with the case's grey (`#c9ccd1`) and near-black (`#1d1f22`).
- **A test** that every proposal is well-formed SVG with a view box, fetches nothing, and that
  each one-colour version uses one colour.

## Decided and assumed

Decided by the plan (B8): generic case, no single-board computer's name or fruit logo, only the
project's own drawing in the repository, legible small and in one colour, the owner picks.
Assumed here (also in `docs/open-questions.md`): three proposals; drawn by hand as SVG; the
favicon in the web page stays the current placeholder until the owner picks (👤).

## Capabilities

### New Capabilities

- `logo`: what a proposal must be (forms, legibility, no trademark).

### Modified Capabilities

None.

## Impact

- New `docs/logo-proposals/` (SVGs and a `README.md`), `tests/unit/test_logo_proposals.py`.
