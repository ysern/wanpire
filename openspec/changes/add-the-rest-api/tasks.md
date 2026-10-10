## 1. The API (no root)

- [x] 1.1 Failing tests: the token (none, wrong, right); status
- [x] 1.2 Failing tests: lease ask, queue, poll, release and pass on; unknown ticket 404; ended by hand 410
- [x] 1.3 Failing tests: link put from figures and from two ends, without the lease 409, invalid 422, delete; read open
- [x] 1.4 Failing tests: the dead-man renewed by the holder's poll; applied with the lease's TTL
- [x] 1.5 Failing tests: endpoints, one endpoint, preview (engine untouched), adapters
- [x] 1.6 Implement `api.py` until green

## 2. Serve

- [x] 2.1 Failing tests: `serve` without a token refuses; the control address is read
- [x] 2.2 Implement; start it on the Pi against a namespace bed and call it over HTTP

## 3. Close

- [x] 3.1 Journal, open questions, README

## 4. One account instead of the token (R6, the owner, 2026-10-11)

- [ ] 4.1 Failing tests: the account file (set, verify, wrong password, reset, a change seen by a running server, mode 0600, never the password in clear)
- [ ] 4.2 Failing tests: setup (needed, made once, 409 after, 403 elsewhere before it, 422 for a short password or a bad name)
- [ ] 4.3 Failing tests: Basic (none, wrong, right); session (sign in, cookie alone, sign out, password change ends other sessions)
- [ ] 4.4 Implement `account.py` and the routes until green; replace the token everywhere it was taken
- [ ] 4.5 `wanpire account set|reset`; `serve` starts without an account
