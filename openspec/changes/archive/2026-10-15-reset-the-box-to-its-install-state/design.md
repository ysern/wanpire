## Context

See `proposal.md` for what a reset is and the five ways of asking for it. The pieces exist:
`Account.reset()` removes the account and a running server sees it on its next call;
`save_config` writes the configuration atomically with mode 0600; `Modes.down`/`up` set the
line; the unit restarts the server on a non-zero exit (`Restart=on-failure`) and runs `reset`
and `up` before `serve`; the install writes the configuration through `write_file … 600` and
refuses other roles on an installed box. The page has a modal dialog (follow-the-house-style)
and danger text actions.

## Goals / Non-Goals

**Goals:** one reset function, called from the CLI and the API; the install-time
configuration kept as the factory state; the page's Start over section.

**Non-Goals:** the boot-partition trigger and the GPIO button (options 3 and 4, O11); a
reset that re-detects adapters; resetting the install itself; a reset through the MCP.

## Decisions

### D1. The factory state is a copy the install makes, not a re-detection

`install.sh` writes `factory.json` beside the configuration from the same `config_json` (or
copies an existing configuration when no factory copy exists). The detection logic stays in
the shell script, where it reads sysfs with the install's options (`--control`, `--inbound`,
`--outbound`, `--wifi-country`); the Python side needs only to copy a file back.

Not taken: moving the detection into `wanpire` (a second detector to keep in step with the
first); recording the factory roles inside `wanpire.json` under a key (a reset would then
need to rewrite the file it is restoring, and the page's roles change would have to carry the
key through).

### D2. One function, `factory.reset(config_path, account_path, factory_path)`

A new `src/wanpire/factory.py` holds `reset()`: refuse if the factory copy is missing
(`NoFactoryCopy`), validate it with `config_from_dict` (no adapter check: the box may have
other adapters now), write it over the configuration with `save_config`, then
`Account(...).reset()`. It returns the restored `Config`. The CLI and the API call it; the
restart is the caller's.

### D3. The CLI restarts the unit; the API exits and lets the unit restart it

`wanpire factory-reset`: at a terminal asks `Reset the box to its install state? [yes/N]`
unless `--yes`; calls `reset()`; then, if `systemctl is-active wanpire.service` is 0, runs
`systemctl restart wanpire.service` (the unit's pre-start then runs `reset` and `up` with the
restored roles); else runs `modes.down(old)` and `modes.up(new)` itself. Prints what it did.

`POST /api/v1/factory-reset`: `confirm` must be `reset` (422), the broker must be free (409
naming the holder, the same message the roles use), then the handler calls `reset()`, answers
202 `{"resetting": true}`, and a thread sleeps one second and calls `os._exit(3)`. The unit
restarts the server; its pre-start clears and sets the line up with the restored roles; the
account is gone so the first visit makes it. Without systemd (a dev run) the process ends,
which is the honest outcome.

Not taken: restarting from inside the request (`systemctl restart` kills the request before
its answer, and the server would need `sudo`); reloading the configuration in place without a
restart (the sessions, the leases and the engine's state would need resetting one by one, and
the roles' `change` path already takes the line down and up, but the control adapter may be
shared with inbound in router mode, so the line's teardown can cut the very session; the unit's
restart is what a reboot does, and it is tested).

### D4. The page

Settings / Access gains a section "Start over": a title, one muted sentence, and in the head a
danger action "Reset the box…". The dialog follows the house style (tint header strip, a form
with the word field, one primary "RESET THE BOX" disabled until the field reads `reset`, a
Cancel action). On 202 the page shows "Resetting; the page comes back when the box answers."
under the action and polls `GET /api/v1/setup` every two seconds; when it answers `needed`, the
page calls `showSetup()`.

### D5. Tests

`tests/install`: the factory copy on a first install, on a second install without one, and
unchanged after a page change (the staged root makes these file checks). `tests/unit`:
`factory.reset` restores and removes, refuses without a copy; the CLI's prompt, `--yes`, and
which restart path it takes (a fake runner); the API's 202, 409 and 422 and that the exit is
scheduled (a fake exit). `tests/ui`: the dialog's disabled primary, cancel, and the reset
flow against a test box whose "exit" is a fake that flips the account to none.

## Risks / Trade-offs

- [Anyone with the account can wipe the box] → the same bar as changing the roles, and the
  install's note that the first visit makes the account stands; the typed word stops a slip.
- [A reset while a lease is held would end someone's run] → refused 409; release first.
- [The server exits with 3 and `Restart=on-failure` brings it back after `RestartSec=5`] → the
  page polls; five seconds is what a boot takes anyway.
- [A box installed before this change has no factory copy] → the next `install.sh` run makes
  one from the configuration it finds, and `factory-reset` says so until then.
- [The factory copy names an adapter the box no longer has] → the restored configuration
  loads unchecked and the line waits for it (serve-with-the-line-down), so the box is still
  reachable and the roles can be changed from the page.
