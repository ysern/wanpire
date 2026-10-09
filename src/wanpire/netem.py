"""A Direction rendered as netem options, closing the traps the spike found. No I/O here.

- Jitter defaults to a normal distribution, and keeps packets in order by setting netem's
  ``rate`` (to the bandwidth asked, or the adapter's line rate), unless reordering is asked.
- Burst loss is the Gilbert-Elliott model; netem's loss correlation is never used (it
  produces almost no loss on the kernels measured).
- Reordering always carries a gap (without one it does nothing).
- The queue is sized for the delay, three jitters and the rate, with half again as margin.
"""

from __future__ import annotations

import math

from .model import Direction

QUEUE_FLOOR = 1000
PACKET_BYTES = 1500  # what one queued packet is assumed to carry, for sizing
QUEUED_PACKET_MEMORY = 2048  # what one queued packet is assumed to cost in memory
QUEUE_MEMORY_BUDGET = 64 * 1024 * 1024  # per direction
QUEUE_MARGIN = 1.5
REORDER_GAP = 5


def _num(x: float) -> str:
    return f"{x:g}"


def gilbert_elliott(loss_pct: float, burst_length: float) -> tuple[float, float]:
    """Mean loss L in bursts of mean length B -> netem gemodel (p, r), in percent.

    Two states, every packet lost in the bad one and none in the good one: the bad state's
    share is p / (p + r) = L, and its mean stay is 1 / r = B.
    """
    loss = loss_pct / 100
    r = 1 / burst_length
    p = loss * r / (1 - loss)
    return p * 100, r * 100


def queue_limit(d: Direction, line_rate_mbit: float) -> int:
    rate_mbit = d.rate_mbit or line_rate_mbit
    hold_s = (d.delay_ms + 3 * d.jitter_ms) / 1000
    packets_per_s = rate_mbit * 1e6 / 8 / PACKET_BYTES
    needed = math.ceil(round(QUEUE_MARGIN * hold_s * packets_per_s, 6))
    cap = QUEUE_MEMORY_BUDGET // QUEUED_PACKET_MEMORY
    return min(max(needed, QUEUE_FLOOR), cap)


def netem_args(d: Direction, line_rate_mbit: float) -> list[str]:
    """The options after ``tc qdisc add dev X root netem``."""
    a: list[str] = []
    if d.delay_ms or d.jitter_ms:
        a += ["delay", f"{_num(d.delay_ms)}ms"]
        if d.jitter_ms:
            a += [f"{_num(d.jitter_ms)}ms", "distribution", d.distribution]
    if d.loss_pct:
        a += ["loss", "random", f"{_num(d.loss_pct)}%"]
    elif d.burst_loss_pct:
        p, r = gilbert_elliott(d.burst_loss_pct, d.burst_length)
        a += ["loss", "gemodel", f"{p:.4f}%", f"{r:.4f}%", "100%", "0%"]
    if d.duplicate_pct:
        a += ["duplicate", f"{_num(d.duplicate_pct)}%"]
    if d.reorder_pct:
        a += ["reorder", f"{_num(d.reorder_pct)}%", "gap", str(REORDER_GAP)]
    rate = d.rate_mbit
    if rate is None and d.jitter_ms and not d.reorder_pct:
        rate = line_rate_mbit  # keeps packets in order under jitter
    if rate is not None:
        a += ["rate", f"{_num(rate)}mbit"]
    a += ["limit", str(queue_limit(d, line_rate_mbit))]
    return a
