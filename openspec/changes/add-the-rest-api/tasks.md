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
