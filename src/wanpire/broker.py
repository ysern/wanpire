"""Who drives the link: one holder at a time, a queue behind it, both kept alive by use.

A client asks with who it is and its purpose, and gets a ticket. A free link gives the ticket
the **lease**; otherwise the ticket waits in a **queue**, in order of arrival.

- A queued ticket lives while it is polled (``queue_ttl_s``, 60 s by default).
- A lease lives while its holder calls (``lease_ttl_s``, 120 s by default).
- When a lease ends (released, expired, or ended by hand) the link is cleared, then the lease
  passes to the head of the queue, whose TTL starts then.
- Only changes need the lease (``require``); reading the status needs nothing.

No I/O and no thread: the clock is injected, and every call first settles what the passing
time has done.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT_LEASE_TTL_S = 120
DEFAULT_QUEUE_TTL_S = 60


class BrokerError(RuntimeError):
    pass


class UnknownTicket(BrokerError):
    """The ticket is not held or queued (never was, expired from the queue, or already told)."""


class LeaseEnded(BrokerError):
    """The ticket's lease ended without its holder: expired, or ended by hand. Told once."""


class NotHolder(BrokerError):
    """A change was asked by a ticket that does not hold the lease."""


@dataclass
class _Entry:
    ticket: str
    who: str
    purpose: str
    asked_at: float
    last_seen: float
    granted_at: float | None = None


@dataclass(frozen=True)
class Answer:
    ticket: str
    holds: bool
    position: int  # 0 when holding, 1 for the head of the queue
    expires_in_s: float


class Broker:
    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 on_clear: Callable[[], None] | None = None,
                 lease_ttl_s: float = DEFAULT_LEASE_TTL_S,
                 queue_ttl_s: float = DEFAULT_QUEUE_TTL_S):
        self._clock = clock
        self._on_clear = on_clear or (lambda: None)
        self.lease_ttl_s = lease_ttl_s
        self.queue_ttl_s = queue_ttl_s
        self._holder: _Entry | None = None
        self._queue: list[_Entry] = []
        self._ended: dict[str, str] = {}  # ticket -> why its lease ended, told once
        self._last_clear_error: str | None = None
        self._lock = threading.Lock()

    # -- public -----------------------------------------------------------------------------

    def request(self, who: str, purpose: str) -> Answer:
        """Ask for the link: the lease if it is free, a place in the queue otherwise."""
        with self._lock:
            now = self._settle()
            e = _Entry(secrets.token_hex(16), who, purpose, now, now)
            if self._holder is None and not self._queue:
                e.granted_at = now
                self._holder = e
            else:
                self._queue.append(e)
            return self._answer(e, now)

    def poll(self, ticket: str) -> Answer:
        """Keep a ticket alive: renews a lease or a queued request; says where it stands."""
        with self._lock:
            now = self._settle()
            e = self._find(ticket)
            e.last_seen = now
            return self._answer(e, now)

    def require(self, ticket: str) -> None:
        """Before a change: refuse unless ``ticket`` holds the lease; renew it if it does."""
        with self._lock:
            now = self._settle()
            e = self._find(ticket)
            if e is not self._holder:
                h = self._holder
                held = (f"{h.who} holds it ({h.purpose})" if h else "nobody holds it")
                raise NotHolder(f"a change needs the lease; {held}; you are queued at "
                                f"position {self._queue.index(e) + 1}")
            e.last_seen = now

    def release(self, ticket: str) -> None:
        """Give the lease back, or leave the queue."""
        with self._lock:
            self._settle()
            e = self._find(ticket)
            if e is self._holder:
                self._end_lease()
            else:
                self._queue.remove(e)

    def end_lease(self, reason: str) -> None:
        """End the current lease by hand; its holder is told ``reason`` on its next call."""
        with self._lock:
            self._settle()
            if self._holder:
                self._ended[self._holder.ticket] = f"your lease was ended by hand: {reason}"
                self._end_lease()

    def status(self) -> dict:
        with self._lock:
            now = self._settle()
            h = self._holder
            return {
                "holder": None if h is None else {
                    "who": h.who, "purpose": h.purpose,
                    "held_s": round(now - h.granted_at, 1),
                    "expires_in_s": round(h.last_seen + self.lease_ttl_s - now, 1),
                },
                "queue": [{"who": q.who, "purpose": q.purpose,
                           "waiting_s": round(now - q.asked_at, 1),
                           "expires_in_s": round(q.last_seen + self.queue_ttl_s - now, 1)}
                          for q in self._queue],
                "lease_ttl_s": self.lease_ttl_s,
                "queue_ttl_s": self.queue_ttl_s,
                "last_clear_error": self._last_clear_error,
            }

    # -- inside -----------------------------------------------------------------------------

    def _find(self, ticket: str) -> _Entry:
        if self._holder and self._holder.ticket == ticket:
            return self._holder
        for q in self._queue:
            if q.ticket == ticket:
                return q
        if ticket in self._ended:
            raise LeaseEnded(self._ended.pop(ticket))
        raise UnknownTicket("unknown ticket: it expired from the queue, or was never issued; "
                            "ask for the link again")

    def _answer(self, e: _Entry, now: float) -> Answer:
        if e is self._holder:
            return Answer(e.ticket, True, 0, round(e.last_seen + self.lease_ttl_s - now, 1))
        return Answer(e.ticket, False, self._queue.index(e) + 1,
                      round(e.last_seen + self.queue_ttl_s - now, 1))

    def _settle(self) -> float:
        now = self._clock()
        if self._holder and now - self._holder.last_seen > self.lease_ttl_s:
            self._ended[self._holder.ticket] = (
                f"your lease expired: no call for more than {self.lease_ttl_s:g} s")
            self._end_lease(now)
        self._queue = [q for q in self._queue if now - q.last_seen <= self.queue_ttl_s]
        if self._holder is None and self._queue:
            self._grant(now)
        return now

    def _end_lease(self, now: float | None = None) -> None:
        now = self._clock() if now is None else now
        self._holder = None
        try:
            self._on_clear()
            self._last_clear_error = None
        except Exception as e:  # a stuck lease is worse than a reported failure
            self._last_clear_error = f"{type(e).__name__}: {e}"
        # drop queued requests that died before they could be granted
        self._queue = [q for q in self._queue if now - q.last_seen <= self.queue_ttl_s]
        if self._queue:
            self._grant(now)

    def _grant(self, now: float) -> None:
        e = self._queue.pop(0)
        e.granted_at = now
        e.last_seen = now
        self._holder = e
