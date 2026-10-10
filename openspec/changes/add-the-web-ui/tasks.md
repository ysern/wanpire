## 1. Tests first (Playwright, headless)

- [x] 1.1 A test bed: the real app on a free port, a recording engine, a broker; a page fixture
- [x] 1.2 Failing tests: served without the token; asks for the token; a wrong token is refused
- [x] 1.3 Failing tests: the status line names the holder and the queue; the counters
- [x] 1.4 Failing tests: endpoints and channels; the preview leaves the link alone
- [x] 1.5 Failing tests: ask, apply, clear, release; queued then granted; ended elsewhere
- [x] 1.6 Failing tests: end another's lease, cancelled and confirmed
- [x] 1.7 Failing test: no sideways scroll at 360 px; dark mode follows the preference

## 2. The page

- [x] 2.1 Serve `web/` from the app, as package data
- [x] 2.2 `index.html`, `style.css`, `app.js` until green

## 3. Close

- [x] 3.1 Try it on the Pi against a namespace bed, from a phone-sized window
- [x] 3.2 Journal, open questions, README

## 4. Revision: the router-admin look (the owner's style rules)

- [x] 4.1 Design U5 rewritten with the rules in wanpire's own words; the spec's look requirements
- [x] 4.2 Failing tests: sections in the header band and the side menu; nothing fetched from elsewhere
- [x] 4.3 Failing tests: at 720 and 1,280 px, light and dark: no sideways scroll, contrast AA
- [x] 4.4 Restyle `index.html`, `style.css`, `app.js` until green; the existing tests follow the sections
- [x] 4.5 Journal, open questions

## 5. Revision: after the first use (the owner, 2026-10-11)

- [x] 5.1 Spec and design U2; the REST API's R6 first
- [x] 5.2 Failing tests: set up on a new box (made, signed in; passwords differ; too short); sign in, wrong password, coming back, sign out; change the password; no credential in the browser's storage
- [x] 5.3 `index.html`, `style.css`, `app.js` until green; the look tests still pass
- [x] 5.4 Try it on the Pi; journal, open questions
