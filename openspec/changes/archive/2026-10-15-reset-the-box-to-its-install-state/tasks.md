## 1. The factory copy

- [x] 1.1 Failing tests in `tests/install/test_install.py`: a first install writes `factory.json` equal to the configuration in mode 0600; a second install on a box without one copies the configuration and says so; a changed configuration leaves the copy alone; `uninstall --purge` removes it; then change `install.sh` and verify the tests pass

## 2. The reset

- [x] 2.1 Failing tests in `tests/unit/test_factory.py`: `reset()` restores the configuration from the copy and removes the account; refuses without a copy and changes nothing; refuses an invalid copy; then write `src/wanpire/factory.py` and verify the tests pass
- [x] 2.2 Failing tests in `tests/unit/test_cli.py`: `factory-reset` asks at a terminal and stops on anything but "yes"; `--yes` resets; restarts the unit when it is active, else takes the mode down and up (fake runner); says what it did; then implement and verify the tests pass
- [x] 2.3 Failing tests in `tests/unit/test_api.py`: `POST /factory-reset` is 422 without the word, 409 while a lease is held, 202 otherwise with the reset done and the exit scheduled (injected `exit`); the MCP lists no such tool; then implement and verify the tests pass

## 3. The page

- [x] 3.1 Failing UI tests in `tests/ui/test_web_ui.py`: the Start over section and its danger action; the dialog's primary disabled until `reset` is typed; cancel sends nothing; confirming shows the resetting line and ends on the set-up card once the test box reports no account; then implement in `index.html` and `app.js` and verify the tests pass, with the house-style look test still green

## 4. Close

- [x] 4.1 Run `pytest tests/unit tests/ui tests/install` and verify it passes; on the Pi, run the install once to make the factory copy, then reset from the page and verify the set-up card comes back and the roles are the install's
- [x] 4.2 Add O11 (the triggers) and the assumptions to `docs/open-questions.md`, the README's "start over" lines beside the forgotten-password ones, and the journal entry; verify all three mention this change
