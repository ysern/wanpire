## Why

A person should be able to drive wanpire from a phone or a laptop without reading the API: pick
two places and a channel at each, see what the link will be, apply it, read what the box is
doing to the packets, and see who else is using the box. The design (D8) puts a web UI on the
same server as the REST API, as one more client of it.

## What Changes

- **Static pages served by `wanpire serve`** at `/`: one HTML page, one stylesheet, one plain
  script. The page calls `/api/v1` only, with the box's token, like any other client.
- **What the page does:** asks for the token once; shows a status line (mode, the link's state,
  the holder and since when, the queue); picks two endpoints and a channel for each and shows
  the link's figures both ways and how they were worked out; asks for the lease, waits in the
  queue while the page is open, applies, clears and releases; reads the counters; lists the
  queue and ends another holder's lease by hand after a confirmation and a reason.
- **The look** follows D8's rule: a home router's admin page, one column, system fonts, few
  colours, light and dark, readable on a phone; no framework, no build step.
- **Page tests** in a headless browser (Playwright) against the real app with a recording
  engine, written before the page.

## Decided and assumed

Decided by the design (D8): static pages, plain JS calling the REST API, the router-admin look.
Assumed here (also in `docs/open-questions.md`):

- the static files and `/docs`, `/openapi.json` are served without the token: they hold no
  data, and the API they describe is published with the source; every route under `/api/v1`
  still needs it;
- the token is kept in the browser's local storage once entered, the ticket in its session
  storage (one tab, one ticket);
- the page polls its ticket at a third of the TTL only while it is open, and releases its lease
  when the page is closed; the box's dead-man covers a browser that dies;
- scenarios are not shown: the engine has none yet.

## Capabilities

### New Capabilities

- `web-ui`: the page, what it shows and what it lets a person do.

### Modified Capabilities

None. The REST API is used as it is.

## Impact

- New `src/wanpire/web/` (index.html, app.js, style.css, favicon.svg), served from `api.py`.
- Test-only dependency: `playwright` (and its Chromium), in a `ui-test` extra; the page tests
  skip where it is missing.
