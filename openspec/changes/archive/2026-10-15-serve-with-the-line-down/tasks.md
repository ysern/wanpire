## 1. The configuration and the CLI

- [x] 1.1 Failing tests in `tests/unit/test_config.py`: `Config.missing` names an absent outbound adapter, an absent inbound one, both, and none; `missing_reason` is one sentence naming the role and the adapter; then implement them and verify the tests pass
- [x] 1.2 Failing tests in `tests/unit/test_cli.py`: `wanpire up` with a missing line adapter exits 0, prints "the line waits for …" and does not call `modes.up`; with a missing control adapter it exits 2 naming it; `wanpire adapters` prints the roles with an adapter missing; then implement `_up` and the unchecked load in `_print_adapters` and verify the tests pass
- [x] 1.3 Failing test in `tests/unit/test_engine.py` (or `test_netem.py`): `clear` on an adapter that does not exist returns without error; verify it passes as the engine is today, or make it so

## 2. The line's state in the server

- [x] 2.1 Failing tests in `tests/unit/test_roles.py`: `line_view()` down with `missing` and `reason`, up after `watch()` finds the adapter and `modes.up` is called once; still down with the refusal's text when `modes.up` refuses; `change` while down brings the line up, and a failed change leaves the old file and the line down; then implement `line_up`, `missing`, `line_view`, `watch` and the change path, and verify the tests pass
- [x] 2.2 Failing tests in `tests/unit/test_api.py`: the status carries `line`; `PUT /link` is 409 with the reason while down and the engine is not called; `DELETE /link` succeeds; `GET /roles` carries `missing`; `PUT /roles` to present adapters while down answers 200 and the status then says up; the tick calls `watch`; then wire `serve` and `create_app` and verify the tests pass
- [x] 2.3 Failing test in `tests/unit/test_cli.py`: `serve` with a missing outbound adapter starts and the app's status says the line is down (the existing `serve` tests' pattern); then implement and verify

## 3. The page

- [x] 3.1 Failing UI tests in `tests/ui/test_web_ui.py`: the State card's line row reads "up" in the good colour and "down: outbound … is not plugged in" in the danger colour (a test box whose config names an absent adapter); Apply is disabled while down with the reason under it; then implement in `index.html` and `app.js` and verify the tests pass, with the house-style look test still green
- [x] 3.2 Failing UI tests in `tests/ui/test_adapters_page.py`: the outbound drop-down shows "wlx1 (not plugged in)" chosen with the danger line under it, Save as it is sends nothing, and picking `eth1` and saving brings the line up; then implement in `app.js` and verify the tests pass

## 4. Close

- [x] 4.1 Add the `up` scenario to `tests/install/test_install.py` if the staged stub can express it (else note it is covered by 1.2) and verify `pytest tests/unit tests/ui tests/install` passes
- [x] 4.2 On the Pi with the stick out: copy the tree, upgrade the package, restart the service, and verify the page is up with the line down; plug the stick in and verify the line comes up within a few seconds without a restart
- [x] 4.3 Record the assumptions in `docs/open-questions.md` (the tick poll, the fatal control adapter, the no-op clear) and write the journal entry; verify both mention this change
