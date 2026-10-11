"""Who drives the link: one holder at a time, a queue behind it, both kept alive by use.

A client asks with who it is and its purpose, and gets a ticket. A free link gives the ticket
the **lease**; otherwise the ticket waits in a **queue**, in order of arrival.

- A queued ticket lives while it is polled (``queue_ttl_s``, 60 s by default).
- A lease lives while its holder calls (``lease_ttl_s``, 120 s by default), unless it was asked
  with a ``hold``: a number of seconds, which it lasts from its grant without any call, or
  ``"until-released"``, which never expires by time.
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
UNTIL_RELEASED = "until-released"
MIN_HOLD_S = 60
MAX_HOLD_S = 7 * 24 * 3600


class BrokerError(RuntimeError):
    pass


class InvalidHold(ValueError):
    """A lease's length that is neither seconds in range nor until released."""


def check_hold(hold):
    """None (while used), seconds from 60 s to 7 days, or ``"until-released"``."""
    if hold is None or hold == UNTIL_RELEASED:
        return hold
    if isinstance(hold, bool) or not isinstance(hold, (int, float)) or \
            not MIN_HOLD_S <= hold <= MAX_HOLD_S:
        raise InvalidHold(f"a lease's hold is a number of seconds from {MIN_HOLD_S} to "
                          f"{MAX_HOLD_S}, or {UNTIL_RELEASED!r}; not {hold!r}")
    return float(hold)


def _length(seconds: float) -> str:
    m = round(seconds / 60)
    if m < 60:
        return f"{m} min"
    if m % (24 * 60) == 0:
        d = m // (24 * 60)
        return f"{d} day" + ("s" if d > 1 else "")
    return f"{m / 60:g} h"


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
    hold: float | str | None = None  # None: while used; seconds; or UNTIL_RELEASED


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

    def request(self, who: str, purpose: str, hold=None) -> Answer:
        """Ask for the link: the lease if it is free, a place in the queue otherwise."""
        hold = check_hold(hold)
        with self._lock:
            now = self._settle()
            e = _Entry(secrets.token_hex(16), who, purpose, now, now, hold=hold)
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

    def lifetime_s(self, ticket: str) -> float | None:
        """The dead-man's lifetime for a link applied under ``ticket``'s lease: the TTL for a
        lease that lives while used, the time left for a timed one, None until released."""
        with self._lock:
            now = self._settle()
            e = self._find(ticket)
            if e.hold is None:
                return self.lease_ttl_s
            return self._remaining(e, now)

    def status(self) -> dict:
        with self._lock:
            now = self._settle()
            h = self._holder
            return {
                "holder": None if h is None else {
                    "who": h.who, "purpose": h.purpose,
                    "held_s": round(now - h.granted_at, 1),
                    "expires_in_s": self._expires_in(h, now),
                    "hold": h.hold,
                    "remaining_s": self._remaining(h, now),
                },
                "queue": [{"who": q.who, "purpose": q.purpose, "hold": q.hold,
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

    def _remaining(self, e: _Entry, now: float) -> float | None:
        """A lease's time left: None until released; for one that lives while used, its TTL."""
        if e.hold == UNTIL_RELEASED:
            return None
        if e.hold is None:
            return round(e.last_seen + self.lease_ttl_s - now, 1)
        return round(e.granted_at + e.hold - now, 1)

    def _expires_in(self, e: _Entry, now: float) -> float | None:
        if e is self._holder:
            return self._remaining(e, now)
        return round(e.last_seen + self.queue_ttl_s - now, 1)

    def _answer(self, e: _Entry, now: float) -> Answer:
        if e is self._holder:
            return Answer(e.ticket, True, 0, self._expires_in(e, now))
        return Answer(e.ticket, False, self._queue.index(e) + 1, self._expires_in(e, now))

    def _settle(self) -> float:
        now = self._clock()
        h = self._holder
        if h and h.hold is None and now - h.last_seen > self.lease_ttl_s:
            self._ended[h.ticket] = (
                f"your lease expired: no call for more than {self.lease_ttl_s:g} s")
            self._end_lease(now)
        elif h and isinstance(h.hold, float) and now >= h.granted_at + h.hold:
            self._ended[h.ticket] = f"your lease's {_length(h.hold)} ended"
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
