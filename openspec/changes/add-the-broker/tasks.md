## 1. Broker (no root)

- [x] 1.1 Failing tests: the first asks; two more queue in order; a holder asking again keeps its lease
- [x] 1.2 Failing tests: a queued request expires unpolled and the rest move up
- [x] 1.3 Failing tests: release passes on and clears; silence expires, clears, passes on, and is told; nobody waiting
- [x] 1.4 Failing tests: a change without the lease names the holder; a change renews; the status
- [x] 1.5 Failing tests: ended by hand with a reason; a failing clear still passes the lease on
- [x] 1.6 Implement `broker.py` until green

## 2. Close

- [x] 2.1 Journal and open questions
