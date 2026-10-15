## Why

On 2026-10-15 the box came back on the home network with its USB Wi-Fi stick and USB Ethernet
adapter unplugged. Its unit runs `wanpire reset`, `wanpire up` and then `wanpire serve`;
`up` loads the configuration checked against the adapters, which refuses because the saved
outbound adapter `wlx…` does not exist, so the unit fails and restarts every five seconds. The
web page, the REST API and the MCP are all down, and the only ways back are to plug the stick
in or to edit `/etc/wanpire/wanpire.json` over SSH or a console. A missing line adapter should
take the line down, not the box's own interface: the page is where the roles get fixed.

## What Changes

- **The server always starts.** When a line adapter named in the configuration (inbound or
  outbound) is not plugged in, `wanpire up` says which and exits 0 without setting the mode up,
  and `wanpire serve` starts with the line **down**. A missing *control* adapter is still fatal:
  the server has nothing to listen on.
- **The line comes up on its own** when the adapter appears: the server checks the adapters on
  its tick (every few seconds) while the line is down and sets the mode up as soon as the
  configured ones exist. Plugging the stick back in is enough; no restart.
- **The status says so.** `GET /api/v1/status` carries `line`: `{"up": true}` or `{"up": false,
  "missing": ["wlx…"], "reason": "outbound adapter wlx… is not plugged in"}`. The MCP's
  `wanpire_status` passes it through unchanged.
- **Applying a link is refused** with 409 and the reason while the line is down; clearing is
  allowed (nothing is on a missing adapter). **The roles can be changed** while the line is
  down, which is the way out when the adapter is gone for good: pick present adapters and Save.
  `GET /api/v1/roles` names the missing adapter so the page can show the configured truth.
- **The page shows it**: the State of the box card gets a "Line:" row, "up" or "down: outbound
  wlx… is not plugged in" in the danger colour; Apply is offered only while the line is up; the
  Adapters / Roles page keeps the configured adapter in its drop-down marked "(not plugged in)"
  and says under it what to do.
- `wanpire adapters` prints the roles from the configuration even when an adapter is missing,
  instead of "no roles".
- Teardown already tolerates a missing adapter; a test says so.

## Decided and assumed

Decided: a missing line adapter is a state of the line, not a failure of the box. Assumed
(also in `docs/open-questions.md`): the server polls the adapter list on its tick rather than
listening to udev (no new dependency, no root-only rule, five seconds is quick enough for a
hand plugging a stick in); a missing control adapter stays fatal; clearing a link on a missing
adapter is a no-op, not an error.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `adapter-roles`: a configuration can say which of its line adapters are missing instead of
  refusing to load (new requirement).
- `line-modes`: the line waits for an adapter that is not plugged in, and comes up when it is
  (new requirement).
- `install`: "Impairments are cleared at boot" no longer lets a missing line adapter fail the
  unit.
- `rest-api`: the status carries the line's state; applying needs the line up; the roles can be
  read and changed while it is down, naming the missing adapter.
- `web-ui`: the status card shows the line; Apply is offered only with the line up; the
  Adapters page shows a missing configured adapter.

## Impact

- `src/wanpire/config.py` (`Config.missing`), `cli.py` (`up`, `serve`, `adapters`), `roles.py`
  (the line's state and its watcher), `api.py` (status, link, roles, the tick), `web/app.js`
  and `index.html`.
- Tests in `tests/unit` (config, roles, cli, api), `tests/ui`, `tests/install` (the unit is
  unchanged; one scenario added for `up`).
- No change to the unit file or the install script's steps; no new dependency.
