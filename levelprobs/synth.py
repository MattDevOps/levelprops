"""Synthetic ES/NQ/SPX bar generator.

Produces realistic-looking 5-minute RTH sessions plus an overnight high/low,
so the whole engine runs end-to-end with zero external data. The output type
(`list[Session]`, oldest first) is identical to what a real CSV loader would
produce, so swapping in real data later is a drop-in replacement.

The walk is a gentle log-space Ornstein-Uhlenbeck (mean-reverting) process
around the instrument's anchor price. Mean reversion keeps five years of tape
inside a believable band (instead of a pure random walk drifting to absurd
levels) while still allowing multi-day swings, trends, and overnight gaps.

Determinism: fully seeded. No wall-clock or RNG-without-seed, so two runs with
the same args give identical sessions (and identical probabilities).
"""
import math
import random
from datetime import date, timedelta

from .instruments import Instrument
from .model import Bar, Session, BARS_PER_RTH

_ETH_STEPS = 24       # coarse overnight steps used only for ON high/low + RTH open
_MR_KAPPA = 0.0010    # mean-reversion pull per bar toward log(anchor)


def _intraday_smile(i: int, n: int) -> float:
    """Vol multiplier across the session: elevated at the open and into close."""
    x = i / max(1, n - 1)
    return 1.0 + 0.9 * math.exp(-x / 0.12) + 0.5 * math.exp(-(1 - x) / 0.10)


def _trading_days_back(anchor: date, n: int) -> list:
    """Return n trading days (Mon-Fri) ending at `anchor`, oldest first."""
    days, d = [], anchor
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def generate_sessions(inst: Instrument, n_sessions: int, anchor: date,
                      seed: int = 7) -> list:
    """Generate `n_sessions` sessions of synthetic RTH bars, oldest first."""
    rng = random.Random(seed)
    days = _trading_days_back(anchor, n_sessions)

    bars_per_year = 252 * BARS_PER_RTH
    bar_sigma = inst.annual_vol / math.sqrt(bars_per_year)
    eth_sigma = bar_sigma * 0.6           # overnight is quieter per unit time
    log_anchor = math.log(inst.anchor_price)

    log_p = log_anchor
    sessions = []
    prior_close = math.exp(log_p)

    for day in days:
        # --- overnight: drift toward anchor + noise, set ON high/low + RTH open ---
        on_hi = on_lo = math.exp(log_p)
        for _ in range(_ETH_STEPS):
            log_p += _MR_KAPPA * (log_anchor - log_p) + eth_sigma * rng.gauss(0, 1)
            p = math.exp(log_p)
            on_hi, on_lo = max(on_hi, p), min(on_lo, p)

        # --- RTH: 78 5-min bars with an intraday vol smile ---
        bars = []
        for i in range(BARS_PER_RTH):
            sig = bar_sigma * _intraday_smile(i, BARS_PER_RTH)
            o = math.exp(log_p)
            path = [o]
            for _ in range(4):  # 4 sub-moves -> realistic bar high/low
                log_p += _MR_KAPPA / 4 * (log_anchor - log_p) + (sig / 2.0) * rng.gauss(0, 1)
                path.append(math.exp(log_p))
            h, l, c = max(path), min(path), path[-1]
            bars.append(Bar(round(o, 2), round(h, 2), round(l, 2), round(c, 2)))

        sessions.append(Session(
            day=day, bars=bars,
            overnight_high=round(on_hi, 2), overnight_low=round(on_lo, 2),
            prior_close=round(prior_close, 2),
        ))
        prior_close = bars[-1].c

    return sessions
