"""The statistical core.

Two estimators, both recency-weighted (recent sessions count more):

1. first_break_stats  -> the friend's metrics box: of all sessions, how often
   did price break the prior-day HIGH before the prior-day LOW (and vice versa),
   plus the average up/down excursion. This is the directional bias.

2. touch_probability  -> P(price reaches a level before the RTH close), given
   the current time-of-day and current volatility. This is the "91% that 7530
   gets hit" number.

Recency weighting: weight = 0.5 ** (age_in_sessions / halflife). With the
default halflife of 252 (one trading year), a session one year ago carries half
the weight of today's, and a session five years ago carries ~1/32 — so the last
252 sessions dominate the estimate while older history still nudges it.
"""
from .model import Session, BARS_PER_RTH


def make_weight_fn(halflife_sessions: float = 252.0):
    """Return weight_fn(age) where age is sessions-ago (0 = most recent)."""
    def weight_fn(age: int) -> float:
        return 0.5 ** (age / halflife_sessions)
    return weight_fn


def current_atr(sessions: list, n: int = 14) -> float:
    """Recent average RTH range — the volatility scale for 'today'."""
    recent = sessions[-n:] if len(sessions) >= n else sessions
    return sum(s.rth_range for s in recent) / max(1, len(recent))


# ---------------------------------------------------------------- first break

def first_break_stats(sessions: list, window: int = 252, weight_fn=None) -> dict:
    """Recency-weighted broke-high-first / broke-low-first over the last `window`
    sessions. `window` ~ 252 trading sessions ~ 365 calendar days (the friend's
    'Last 365 Days')."""
    if weight_fn is None:
        weight_fn = make_weight_fn()
    # need a prior session for each, so start at index 1
    usable = sessions[max(1, len(sessions) - window):]
    n_total = len(sessions)

    w_high = w_low = w_neither = w_sum = 0.0
    up_w = dn_w = exc_w = 0.0
    for s in usable:
        prior = sessions[sessions.index(s) - 1]
        pdh, pdl = prior.rth_high, prior.rth_low
        age = (n_total - 1) - sessions.index(s)
        w = weight_fn(age)
        w_sum += w

        first = _first_break_direction(s, pdh, pdl)
        if first == "high":
            w_high += w
        elif first == "low":
            w_low += w
        else:
            w_neither += w

        up_w += w * (s.rth_high - s.rth_open)
        dn_w += w * (s.rth_open - s.rth_low)
        exc_w += w

    if w_sum == 0:
        return {"broke_high": 0, "broke_low": 0, "neither": 0,
                "avg_up": 0, "avg_dn": 0, "n": 0}
    return {
        "broke_high": w_high / w_sum,
        "broke_low": w_low / w_sum,
        "neither": w_neither / w_sum,
        "avg_up": up_w / exc_w,
        "avg_dn": dn_w / exc_w,
        "n": len(usable),
    }


def _first_break_direction(s: Session, pdh: float, pdl: float) -> str:
    for b in s.bars:
        hit_high = b.h >= pdh
        hit_low = b.l <= pdl
        if hit_high and hit_low:
            # both in one bar: attribute to whichever the open was nearer to
            return "high" if abs(b.o - pdh) <= abs(b.o - pdl) else "low"
        if hit_high:
            return "high"
        if hit_low:
            return "low"
    return "neither"


# ------------------------------------------------------------ touch probability

def touch_probability(sessions: list, bar_index: int, needed_points: float,
                      direction: str, cur_atr: float, weight_fn=None) -> float:
    """P(price moves at least `needed_points` in `direction` from `bar_index`
    to the RTH close), estimated from the recency-weighted distribution of
    historical remaining-session excursions, vol-normalized by `cur_atr`.

    direction: 'up' or 'down'. Returns a probability in [0, 1].
    """
    if needed_points <= 0:
        return 1.0
    if weight_fn is None:
        weight_fn = make_weight_fn()
    if cur_atr <= 0:
        return 0.0

    needed_norm = needed_points / cur_atr
    n_total = len(sessions)
    hit_w = w_sum = 0.0
    for idx, s in enumerate(sessions):
        scale = s.rth_range
        if scale <= 0:
            continue
        price_now = s.bars[bar_index].o
        rest = s.bars[bar_index:]
        if direction == "up":
            exc = max(b.h for b in rest) - price_now
        else:
            exc = price_now - min(b.l for b in rest)
        exc_norm = exc / scale
        w = weight_fn((n_total - 1) - idx)
        w_sum += w
        if exc_norm >= needed_norm:
            hit_w += w
    return hit_w / w_sum if w_sum else 0.0
