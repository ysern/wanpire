## Context

D8 of `design-the-link-emulator/design.md` gives the server three faces; the REST API exists
(`add-the-rest-api`). This change adds the web UI, a client of that API and nothing more: it
gets no route of its own and no shortcut into the core.

## Goals / Non-Goals

**Goals:** the page described in the spec; tests in a real browser; the look D8 describes.

**Non-Goals:** raw figures in the page (the REST API and the CLI take them; a later change can
add a form); changing the mode or the adapter mapping (not in the API yet); scenarios (the
engine has none yet); TLS; more than one user account.

## Decisions

### U1. Three static files, no build step

`src/wanpire/web/index.html`, `style.css`, `app.js` and `favicon.svg`, shipped as package data
and served by FastAPI's `StaticFiles` at `/`, mounted after the API so `/api/v1` and `/docs`
win. Plain JS (ES2020, `fetch`), a few hundred lines, readable without tooling.

Not taken: a framework (React, Vue, htmx): a build step or a dependency for one page; server-side
templates: the page would then be a second interface to the core instead of a client of the API.

### U2. The token and the ticket in the browser

The page asks for the token once and keeps it in `localStorage`, so a phone does not ask every
visit; "Forget token" removes it. The lease's ticket lives in `sessionStorage`, one per tab, so a
second tab is a second client. Closing or reloading the page releases its lease (U3): a page that
is not open cannot keep a link it is not watching. Static files, `/docs` and
`/openapi.json` need no token: they hold no data, and the same text is in the source.

Not taken: a login cookie (a second way to authenticate, and agents do not keep cookies); guarding
`/docs` (it hides nothing that is not public, and it is how a person learns the API).

### U3. Polling while open, releasing on close

The page refreshes the status every 5 s. While it has a ticket it polls it at a third of the
lease's TTL (the same rule the skill gives agents), and on `pagehide` it releases with a
`keepalive` request. A browser that dies without that is covered by the broker's TTL and the
engine's dead-man, like any other client.

Not taken: keeping the lease across a reload (the page would have to tell a reload from a
close, and a link left applied by a closed tab is what the broker exists to prevent).

### U4. Who the page is

The page asks for the lease as `who = "web: <name>"`, the name typed once and kept with the
token, and a purpose typed each time. The status shows it like any other client's.

### U5. The look, written for wanpire

A home router's admin page: a title bar with the name, a status line, then sections with a plain
heading each. One column, at most 800 px. System fonts. Light: white page, near-black text, one
blue accent for actions, red only for ending another's lease, green and amber only for state.
Dark: the same roles on a near-black page, chosen by `prefers-color-scheme`. Forms have their
label on the left (stacked on a phone); figures sit in plain tables with right-aligned numbers.
No icons where a word will do, no animation, no web fonts.

### U6. Tests in a browser, against the real app

`tests/ui/` starts uvicorn in a thread on a free port with the real `create_app`, the recording
engine and a real broker (a real clock, short TTLs where a test needs one), and drives the page
with Playwright's headless Chromium. Ending another's lease is one `prompt()`, which is both the confirmation (OK or
Cancel) and the reason; it is answered through Playwright's
dialog handler. The tests skip if Playwright or its browser is missing, so the unit suite still
runs on a bare Pi.

Not taken: testing the JS in Node with a fake DOM (it would not catch what a browser does with
the page); Selenium (heavier, needs a driver installed separately).

## Risks / Trade-offs

- **The token in `localStorage`** is readable by any script on the page. → The page loads no
  third-party script; "Forget token" is there for a shared browser.
- **Plain HTTP**: the token crosses the control network in clear. → As for the API (R5 of
  `add-the-rest-api`): a trusted control network, or a reverse proxy with TLS.
