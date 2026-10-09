"""What a link is: two directions, each with its own impairments. No I/O here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

DISTRIBUTIONS = ("normal", "uniform", "pareto", "paretonormal")
MAX_DELAY_MS = 10_000


class InvalidLink(ValueError):
    """A link description that cannot be applied, with the reason."""


@dataclass(frozen=True)
class Direction:
    """One direction of a link. Every setting is optional; none means no impairment.

    delay_ms        fixed one-way delay added
    jitter_ms       spread of the delay (standard deviation for ``normal``)
    distribution    shape of the jitter: normal (default), uniform, pareto, paretonormal
    loss_pct        random, independent loss
    burst_loss_pct  mean loss when losses come in bursts...
    burst_length    ...of this mean length, in packets
    rate_mbit       bandwidth, a bottleneck with a bounded queue...
    queue_ms        ...holding at most this much at that bandwidth (default 50 ms)
    duplicate_pct   packets sent twice
    reorder_pct     packets sent ahead of their turn (needs a delay to overtake)
    """

    delay_ms: float = 0
    jitter_ms: float = 0
    distribution: str = "normal"
    loss_pct: float = 0
    burst_loss_pct: float = 0
    burst_length: float = 0
    rate_mbit: float | None = None
    queue_ms: float | None = None
    duplicate_pct: float = 0
    reorder_pct: float = 0

    def __post_init__(self) -> None:
        _range("delay_ms", self.delay_ms, 0, MAX_DELAY_MS)
        _range("jitter_ms", self.jitter_ms, 0, MAX_DELAY_MS)
        for name in ("loss_pct", "burst_loss_pct", "duplicate_pct", "reorder_pct"):
            _range(name, getattr(self, name), 0, 100)
        if self.jitter_ms > self.delay_ms:
            raise InvalidLink(
                f"jitter_ms ({self.jitter_ms}) must not exceed delay_ms ({self.delay_ms})"
            )
        if self.distribution not in DISTRIBUTIONS:
            raise InvalidLink(
                f"distribution must be one of {', '.join(DISTRIBUTIONS)}, not {self.distribution!r}"
            )
        if self.rate_mbit is not None and not self.rate_mbit > 0:
            raise InvalidLink(f"rate_mbit must be positive, not {self.rate_mbit}")
        if self.queue_ms is not None:
            if self.rate_mbit is None:
                raise InvalidLink("queue_ms needs rate_mbit: it is the bottleneck's queue")
            _range("queue_ms", self.queue_ms, 1, 1000)
        if self.loss_pct and self.burst_loss_pct:
            raise InvalidLink(
                "only one loss model may be set: loss_pct (random) or burst_loss_pct (bursts)"
            )
        if self.burst_loss_pct and self.burst_length < 1:
            raise InvalidLink(
                f"burst_length must be at least 1 packet when burst_loss_pct is set, "
                f"not {self.burst_length}"
            )
        if self.reorder_pct and not self.delay_ms:
            raise InvalidLink("reorder_pct needs a delay_ms for packets to overtake")

    def is_clear(self) -> bool:
        return self == Direction()

    def to_dict(self) -> dict:
        defaults = Direction()
        return {k: v for k, v in asdict(self).items() if v != getattr(defaults, k)}

    @classmethod
    def from_dict(cls, data: dict) -> Direction:
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise InvalidLink(
                f"unknown setting(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}"
            )
        return cls(**data)


@dataclass(frozen=True)
class Link:
    """A link: ``down`` travels towards the device under test, ``up`` away from it."""

    down: Direction = field(default_factory=Direction)
    up: Direction = field(default_factory=Direction)

    def to_dict(self) -> dict:
        return {"down": self.down.to_dict(), "up": self.up.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> Link:
        unknown = sorted(set(data) - {"down", "up"})
        if unknown:
            raise InvalidLink(f"a link has only 'down' and 'up', not {', '.join(unknown)}")
        return cls(
            down=Direction.from_dict(data.get("down", {})),
            up=Direction.from_dict(data.get("up", {})),
        )


def _range(name: str, value: float, low: float, high: float) -> None:
    if not low <= value <= high:
        raise InvalidLink(f"{name} must be between {low} and {high}, not {value}")
