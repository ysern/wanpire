## Context

See `proposal.md`. Today `config_from_dict(data, adapters)` refuses a configuration whose
adapter is absent, and both `wanpire up` and `wanpire serve` load with the adapter check, so a
missing USB adapter stops the unit in its pre-start step. `wanpire reset` already loads without
the check ("they may be missing"), `Modes.down` already looks indexes up and skips what is not
there, and `Roles.change` already validates a new mapping against the live adapter list. The API
has a tick every `tick_s` seconds (the broker's) that can carry one more check. Nothing in the
engine holds the outbound adapter's name: it is read from `roles.config` at each call.

## Goals / Non-Goals

**Goals:** the server up whenever the control adapter is; the line's state visible in the
status, the MCP and the page; the line back on its own when the adapter returns; the roles
fixable from the page while the line is down.

**Non-Goals:** hot-plugging in the other direction (an adapter pulled while the mode is up is
left to the kernel, which drops it from the bridge; the next tick notices and the status says
down); several outbound adapters; a udev or systemd-path trigger; the install's detection
logic.

## Decisions

### D1. The configuration loads unchecked, then names what is missing

`Config.missing(adapters) -> tuple[str, ...]` returns the line adapters (inbound, outbound)
not in the given list, and `Config.missing_reason(adapters) -> str` the one sentence
("outbound adapter wlx… is not plugged in"; both named when both are). `config_from_dict` is
unchanged, so `Roles.change` and the install's `wanpire adapters` check keep refusing a bad
mapping. `serve` and `up` load with `adapters=None`, refuse if the control adapter is absent
(a new check, same message as today's), and treat the rest as the line's state.

Not taken: a `strict=False` flag on `config_from_dict` that skips the existence check but keeps
the others (the Wi-Fi checks need the adapter's kind, which a missing adapter has not: the
whole adapter-dependent part is deferred until it exists); a default mapping when one is
missing (the roles are the owner's).

### D2. `wanpire up` exits 0 with the line down

`_up` (new, replacing the generic `up`/`down` branch in `main`) loads unchecked; with missing
line adapters it prints "wanpire: the line waits for outbound adapter wlx…: not plugged in" to
stderr and returns 0 without calling `modes.up`. `down` is unchanged (already tolerant). The
unit file does not change; the install's unit scenario is unchanged and one is added.

Not taken: `ExecStartPre=-/opt/…/wanpire up` (the dash makes every failure non-fatal, bad
mappings included); moving `up` into `serve` (the unit's order, reset then up then serve, is a
spec and a journal entry; keeping `up` a step keeps the boot legible).

### D3. The server owns the line's state and brings it up on its tick

`Roles` gains `line_up: bool`, `missing: tuple[str, ...]`, `line_view() -> dict` and
`watch() -> None`. `serve` sets `line_up` from `up`'s outcome: it computes `missing` the same
way; if empty, `up` ran, so `line_up = True`; else `False`. The API's tick calls
`roles.watch()`: when `line_up` is false it lists the adapters, and if none of the configured
ones is missing it calls `modes.up(config)` under the roles lock, sets `line_up`, and logs one
line. A failure (`ModeRefused`) is logged and retried at the next tick with `missing` empty and
`reason` the refusal's text, so the status still says why. In the test bed (`tick_s=None`,
`modes=None`) `watch()` is a no-op and tests call it by hand.

`Roles.change` with the line down: `modes.down(old)` runs (tolerant), the file is written,
`modes.up(new)` runs; on failure the old file is put back and `modes.up(old)` is attempted
only when old's adapters exist, else the line stays down with the old configuration. After a
successful change `line_up = True`.

Not taken: udev rules (root-written, distro-specific, and a second code path); pyroute2's
netlink link events (a thread and a socket for what a five-second poll does); a `systemd.path`
unit watching `/sys/class/net` (one more file for the install, and it would restart the
server, dropping sessions and leases).

### D4. The API: `line` on the status, 409 on apply, roles while down

`status()` adds `"line": roles.line_view()`. `apply_link` checks `roles.line_up` after
`broker.require(ticket)` and raises `_Status(409, reason)`; `clear_link` does not check (the
engine's clear on a missing adapter is what `wanpire reset` does at boot, and it passed with
the stick out; a unit test pins it). `read_roles` adds `"missing"`. `change_roles` keeps its
409 for a link applied or a lease held, which cannot be the case while the line is down except
for the lease. The MCP's `wanpire_status` already returns the status document whole.

### D5. The page

- `refresh()` writes the State card's new row `#line-state`: "up" with class `good`, or
  "down: <reason>" with class `bad`; `showLease()` disables Apply when `!lineUp` and the Link
  section's `#link-message` says the line is down (muted, not an error of the person's).
- `loadRoles()` reads `missing`; for each role whose adapter is missing it appends an option
  `<name> (not plugged in)` with `data-missing`, selects it, and fills `#role-error` (or a new
  per-role line) with the danger sentence; Save refuses a missing pick before sending, like the
  other checks, with the same sentence.

Not taken: hiding the Link section while the line is down (the preview still works and is
useful); auto-selecting another adapter in the drop-down (the page would then save roles the
owner never chose).

### D6. Tests

Unit: `Config.missing` and `missing_reason`; `cli up` with a missing adapter exits 0 and
prints the line, with a missing control exits 2; `Roles.watch` brings the line up when a fake
adapter list gains the adapter, and leaves it down when `modes.up` refuses; `api` status
`line`, 409 on PUT link, 204 on DELETE link, roles `missing`, a roles change while down. UI:
the State card's row, Apply disabled with the reason, the Adapters page's "(not plugged in)"
entry and the refusal, then a fix from the page. Install: the unit is unchanged; `tests/install`
gains the `up` scenario through the staged `wanpire` stub if the stub supports it, else it is
covered by the CLI unit test (the unit file does not change).

## Risks / Trade-offs

- [Five seconds between plugging in and the line coming up] → acceptable for a hand at the
  box; the status says "down" meanwhile, and the page refreshes at the same rate.
- [An adapter that exists but is refused by `modes.up` (no AP support, wrong kind) loops a
  refusal every tick] → the refusal is logged once per change of text, and the status carries
  it; the page's Adapters section is the way out.
- [`Roles.change` while down leaves the line down if the new mapping fails and the old cannot
  come up] → the file holds the old mapping and the status says why; nothing is lost.
- [Clearing a link on a missing adapter] → pinned by a unit test on the engine's `clear`,
  which today returns without error for an unknown device.
