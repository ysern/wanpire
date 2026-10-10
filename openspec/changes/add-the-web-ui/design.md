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

### U2. The session and the ticket in the browser (revised, the owner, 2026-10-11)

The first version asked for the box's token and kept it in `localStorage`. The owner asked for a
home router's way instead (R6 of `add-the-rest-api`): on a box with no account the page shows
**Set up wanpire**, a user name, a password and the password again, checked in the page (8
characters at least, the two the same) before it is sent; on a box with one it shows **Sign
in**. Either ends in a session cookie the page cannot read, so the browser's storage holds no
credential and a returning browser goes straight to the status. Settings / Access shows who is
signed in, changes the password (the current one, the new one twice) and signs out.

The broker's `who` is `web: <user>`, the account's name; the name typed beside the token is gone.
The lease's ticket still lives in `sessionStorage`, one per tab, so a second tab is a second
client. Closing or reloading the page releases its lease (U3): a page that is not open cannot keep
a link it is not watching. Static files, `/docs` and `/openapi.json` need no credentials: they
hold no data, and the same text is in the source.

Not taken: the token in `localStorage` (superseded: a credential any script on the page could
read, and one the owner did not want people to handle); keeping the typed name for `who` (one
account names one owner, and the purpose already tells two people's tabs apart); guarding `/docs`
(it hides nothing that is not public, and it is how a person learns the API).

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

### U5. The look: a home router's admin interface, simple and neat (revised)

The first version was one plain column. The owner asked for the look of a home router's admin
interface, after style rules of the owner's, which wanpire writes out in its own words here.
The style is taken; nobody's brand is.

- **Page.** A light grey page (`#f3f3f3`) with white panels, corners rounded 10 px, no panel
  shadows, in a centred column of about 1,070 px.
- **Header band.** One saturated band about 160 px tall, a gradient of the primary colour,
  carrying the name and the top-level sections as white line icons in 44 px outlined circles,
  each with its label under it: Link, Endpoints, Broker, Adapters, Settings. The active section's
  circle is filled with the accent and its label is bold.
- **Side menu.** About 178 px wide, for a section's sub-pages: the open group is an
  accent-filled bar, the current child is marked with a dot in the primary colour.
- **Sections.** A bold 16 px title, one grey sentence saying what the section is for, and a
  1 px `#e6e6e6` hairline under them; a section's secondary actions are primary-coloured text at
  its top right.
- **Forms.** Two columns: labels ending in a colon on the left (about 270 px), controls about
  350 px wide, rows about 44 px apart, no borders between them. Inputs 28 to 30 px tall, corners
  5 px; help text in grey under its control.
- **Buttons.** At most one primary per section: as wide as the controls, uppercase white 14 px
  text on the primary gradient, corners 5 px, a soft glow of the primary colour. Secondary
  buttons are outlined; other actions are plain text links.
- **Tables.** A pale tinted card (`#f5f7fa`), a bold header, each row a white rounded pill, no
  grid lines. **Status cards** hold two columns of label and value: the link's figures, the
  counters, the box's state.
- **Type.** System fonts (Helvetica Neue, Arial, system-ui), 14 px, 700 for titles; text a
  slate (`#36444b`), not black.
- **Signing in.** Setting up and signing in (U2) are asked for on a centred white card of about 420 × 480 px with a
  large, soft halo tinted with the primary colour.
- **Palette, wanpire's own.** The primary is a wine red, a vampire on the wire: a gradient from
  `#a0213a` to `#6e1022`, deep enough that white text passes WCAG AA on both ends (7.6:1 and
  11.9:1). The accent for "active" is a warm amber (`#f2b134`), with dark wine (`#5a0d1c`) on it.
  Green, amber-brown and a brick red are kept for state and for ending another's lease. A dark
  theme keeps the roles on near-black panels, chosen by `prefers-color-scheme`; both themes meet
  WCAG 2.2 AA contrast for text, and tests measure it.
- **One deviation, for contrast.** The rules' description grey (`#a7a9ac`) is 2.4:1 on white,
  below AA, so the sentence under a title uses a darker grey of the same family (`#646c71`,
  4.8:1 on the tinted card and 5.4:1 on white).
- **Width.** Works from 720 px up; on a phone the menu and the form's columns stack, as a
  stretch, with nothing scrolling sideways.
- **Nothing fetched.** Fonts are the system's, icons are inline SVG drawn for wanpire, and the
  script and the stylesheet are the box's own files.

Not taken: a CSS framework or an icon font (a fetch, a licence and a dependency for a few
glyphs); the first version's single column (the owner's rules supersede it).

### U6. Tests in a browser, against the real app

`tests/ui/` starts uvicorn in a thread on a free port with the real `create_app`, the recording
engine and a real broker (a real clock, short TTLs where a test needs one), and drives the page
with Playwright's headless Chromium. Ending another's lease is one `prompt()`, which is both the confirmation (OK or
Cancel) and the reason; it is answered through Playwright's
dialog handler. The tests skip if Playwright or its browser is missing, so the unit suite still
runs on a bare Pi.

The look is tested too (U5): at 720 and 1,280 px, in the light and the dark theme, nothing
scrolls sideways, and every visible text's contrast with its own background is at least 4.5:1
(3:1 for bold 18.66 px and larger), measured from the computed colours; text on the gradients is
measured against both ends of the gradient.

Not taken: testing the JS in Node with a fake DOM (it would not catch what a browser does with
the page); Selenium (heavier, needs a driver installed separately).

## Risks / Trade-offs

- **A session cookie on a shared browser** keeps the box open to the next person at it. →
  Sign out is in Settings; the session ends when the server restarts.
- **Plain HTTP**: the password crosses the control network in clear when signing in. → As for the
  API (R6 of `add-the-rest-api`): a trusted control network, or a reverse proxy with TLS.
