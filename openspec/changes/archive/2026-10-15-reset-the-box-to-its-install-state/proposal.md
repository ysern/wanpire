## Why

A box that has been configured, tried and handed on should be able to go back to the state it
was in right after the install: no account, the roles the install found, no Wi-Fi networks or
passwords, nothing applied. Today the parts exist separately and each needs SSH and root:
`wanpire account reset` for the account, editing `/etc/wanpire/wanpire.json` for the roles, or
`install.sh uninstall --purge` and an install for everything. A person at the page has no
"start over" at all. The owner asked for one on 2026-10-15.

## What a reset means

Back to the install's state, nothing more:

| Restored | How |
|---|---|
| The roles, the mode, the router network, the country | from a **factory copy** of the configuration the install wrote, `/etc/wanpire/factory.json` |
| Wi-Fi access points and networks to join, with their passwords | gone with the configuration |
| The account | removed: the next visit makes it (as `wanpire account reset`) |
| Sessions, leases, the queue, any link applied | gone with the server's restart |
| The line | torn down and set up again with the restored roles |

Not touched: the install itself (the virtual environment, the unit, the netplan drop-in, the
Wi-Fi driver), the box's own network settings, the regulatory country's system setting.
Those are `install.sh uninstall`.

## The options for how it is asked (O11, the owner picks)

1. **On the box, over SSH or a console: `sudo wanpire factory-reset`** (asks "yes" unless
   `--yes`). The baseline every other trigger calls. Needs root on the box, which is the right
   bar for wiping it. **Recommended, in this change.**
2. **On the page: Settings > Access > "Reset the box to its install state"**, a danger text
   action opening the page's dialog, which says what is lost and asks the word `reset` to be
   typed; `POST /api/v1/factory-reset`. The person at the page is the one who set the box up,
   and the account is the same bar the roles have. The server does the reset and restarts
   itself; the page waits and comes back on the set-up card. **Recommended, in this change:
   it is what the owner asked for.**
3. **A file on the boot partition**: `wanpire-reset` placed in `/boot/firmware` (the Pi's, a
   FAT partition any laptop can write) makes the unit reset at the next boot and delete the
   file. Covers the case with no password *and* no SSH, which `account reset` does not. Needs
   the install to know the boot partition. **An option; not in this change unless picked.**
4. **A button**: a GPIO pin held for ten seconds. Pi-specific hardware and wiring; the project
   is for any small Linux box. **Not recommended.**
5. **Reinstall**: `install.sh uninstall --purge` then `install.sh`. Exists today; slow, needs
   the checkout on the box. Stays as the deepest reset.

The recommendation is 1 and 2 now, 3 if the owner wants a no-credentials path. It goes to
`docs/open-questions.md` as O11.

## What Changes

- **The install keeps a factory copy**: when it writes `/etc/wanpire/wanpire.json` it also
  writes `/etc/wanpire/factory.json` (root only); on an installed box without one it copies the
  configuration it finds, saying so. `uninstall --purge` removes it with the rest.
- **`wanpire factory-reset [--yes]`** on the box: restores the configuration from the factory
  copy, removes the account, and restarts the unit when one runs (else tears the mode down and
  up itself). Without a factory copy it refuses and says to run the install again, which makes
  one.
- **`POST /api/v1/factory-reset`** with `{"confirm": "reset"}`: needs the account; refused 409
  while a lease is held; answers 202 and then performs the reset and restarts the server, so
  the next request finds a box with no account. Not offered by the MCP (a person's decision,
  as ending another's lease is, A43).
- **The page**: a "Start over" section on Settings / Access with a danger text action, the
  dialog by the house style, and a waiting line until the set-up card comes back.

## Decided and assumed

Decided by the owner: a reset exists. Assumed (also in `docs/open-questions.md`): the factory
state is the install-time configuration, not a re-detection of the adapters (the detection
lives in the shell script, and the box may have other adapters now); the server restarts
itself by exiting non-zero so the unit's `Restart=on-failure` brings it back through `reset`
and `up`; the reset refuses while a lease is held rather than ending it (someone's work is
running); the typed word is `reset`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install`: the factory copy (new requirement) and `--purge` removing it.
- `rest-api`: the reset on the box and through the API (new requirement).
- `web-ui`: the Start over section and its dialog (new requirement).

## Impact

- `install/install.sh`; `src/wanpire/cli.py`, `account.py` (unchanged, reused), a new
  `src/wanpire/factory.py` (the reset as one function the CLI and the API call), `api.py`,
  `web/index.html`, `web/app.js`.
- Tests in `tests/install`, `tests/unit` (factory, cli, api), `tests/ui`.
- No new dependency.
