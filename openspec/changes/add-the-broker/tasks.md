## 1. Broker (no root)

- [x] 1.1 Failing tests: the first asks; two more queue in order; a holder asking again keeps its lease
- [x] 1.2 Failing tests: a queued request expires unpolled and the rest move up
- [x] 1.3 Failing tests: release passes on and clears; silence expires, clears, passes on, and is told; nobody waiting
- [x] 1.4 Failing tests: a change without the lease names the holder; a change renews; the status
- [x] 1.5 Failing tests: ended by hand with a reason; a failing clear still passes the lease on
- [x] 1.6 Implement `broker.py` until green

## 2. Close

- [x] 2.1 Journal and open questions

## 3. A lease for a length of time (K7, the owner, 2026-10-11)

- [x] 3.1 Failing tests: a timed lease holds without calls and ends at its length, told why; until released never expires; counted from the grant; the status gives the hold and the time remaining; a queued timed request still polls
- [x] 3.2 `broker.py` until green; the REST API's `hold` and the dead-man (rest-api R8); the page's dropdown and Remaining column (web-ui U8)
