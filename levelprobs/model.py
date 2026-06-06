"""Core data model: bars and sessions.

A *session* is one trading day. It holds the regular-trading-hours (RTH)
5-minute bars plus the overnight high/low that preceded the RTH open. The
probability engine only needs the RTH path plus a few reference levels, so
the model is deliberately small and source-agnostic: synthetic data and real
CSV data both produce the same `Session` objects.
"""
from dataclasses import dataclass, field
from datetime import date, time

# RTH grid (US equity index futures, ET). 09:30 -> 16:00 on a 5-min grid.
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
BAR_MINUTES = 5
BARS_PER_RTH = ((16 - 9) * 60 + (0 - 30)) // BAR_MINUTES  # = 78


@dataclass(frozen=True)
class Bar:
    o: float
    h: float
    l: float
    c: float


@dataclass
class Session:
    day: date
    bars: list                 # list[Bar], the RTH 5-min bars (len == BARS_PER_RTH)
    overnight_high: float
    overnight_low: float
    prior_close: float = field(default=0.0)   # prior RTH close, filled by loader

    # --- reference levels derived from THIS session's RTH ---
    @property
    def rth_open(self) -> float:
        return self.bars[0].o

    @property
    def rth_close(self) -> float:
        return self.bars[-1].c

    @property
    def rth_high(self) -> float:
        return max(b.h for b in self.bars)

    @property
    def rth_low(self) -> float:
        return min(b.l for b in self.bars)

    @property
    def rth_range(self) -> float:
        return self.rth_high - self.rth_low


def bar_index_for(t: time) -> int:
    """Map a wall-clock RTH time to its 5-min bar index (0..BARS_PER_RTH-1)."""
    minutes = (t.hour - RTH_OPEN.hour) * 60 + (t.minute - RTH_OPEN.minute)
    idx = minutes // BAR_MINUTES
    return max(0, min(BARS_PER_RTH - 1, idx))


def label_for_bar(i: int) -> str:
    """Human label like '10:25' for bar index i."""
    total = RTH_OPEN.hour * 60 + RTH_OPEN.minute + i * BAR_MINUTES
    return f"{total // 60:02d}:{total % 60:02d}"
