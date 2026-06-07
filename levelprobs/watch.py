"""Live watch loop: poll a feed, recompute, fire desktop alerts.

Each tick it recomputes the ladder, asks alerts.find_setups() whether there's a
tradeable setup (>= min_prob AND >= min_points of capturable move), and fires a
de-duplicated desktop notification if so. Prints a one-line status every tick so
you can see it working in the terminal too.
"""
import time

from .api import compute
from .alerts import find_setups
from .notify import desktop, Deduper
from .report import G, R, Y, DIM, B, X, _pct

# Alerts are restricted to this instrument only (user preference).
ALERT_SYMBOL = "SPX"


def _status_line(res, setups) -> str:
    bias = res["bias"]
    lean = G + "BUY" if bias["broke_high"] >= bias["broke_low"] else R + "SELL"
    tag = ""
    if setups:
        s = setups[0]
        col = G if s.direction == "up" else R
        tag = (f"  {col}{B}ALERT {s.side_word} -> {s.target:g} "
               f"({_pct(s.prob)}, {s.points:.0f}p){X}")
    return (f"{DIM}{res['time_label']} ET{X}  px {B}{res['price']:.2f}{X}  "
            f"lean {lean}{X}{DIM}({_pct(max(bias['broke_high'], bias['broke_low']))}){X}"
            f"{tag}")


def watch(feed, symbol, min_prob=0.80, min_points=15.0, halflife=252,
          poll_seconds=15.0, max_ticks=None, verbose=True):
    """Run the live loop until the feed is exhausted or max_ticks reached."""
    if symbol.upper() != ALERT_SYMBOL:
        raise ValueError(f"alerts are restricted to {ALERT_SYMBOL} only "
                         f"(got {symbol!r})")
    dedup = Deduper()
    print(f"{B}watching {symbol}{X} -- alert when P(touch) >= {min_prob:.0%} "
          f"and move >= {min_points:g} pts  {DIM}(Ctrl-C to stop){X}")
    iters = 0
    while True:
        if max_ticks and iters >= max_ticks:
            break
        iters += 1
        snap = feed.snapshot()
        if snap is None:
            print(f"{DIM}feed exhausted -- session over{X}")
            break
        if not getattr(feed, "ready", True):
            print(f"{DIM}waiting for first live price tick...{X}")
            if poll_seconds:
                time.sleep(poll_seconds)
            continue
        if getattr(feed, "market_open", True) is False:
            print(f"{DIM}market closed -- no alerts (last quote "
                  f"{getattr(feed, 'last_quote_et', None)}){X}")
            if poll_seconds:
                time.sleep(poll_seconds)
            continue
        history, today, bar_index, price = snap
        res = compute(symbol, history, today, bar_index, price=price,
                      halflife=halflife)
        setups = find_setups(res, min_prob, min_points)

        if verbose:
            print(_status_line(res, setups))

        active = []
        for s in setups:
            key = (s.direction, round(s.target / 5) * 5)
            active.append(key)
            if dedup.should_fire(key):
                align = "aligns with bias" if s.aligned else "AGAINST bias"
                desktop(
                    f"{symbol} {s.side_word}: {s.target:g} "
                    f"{int(s.prob * 100)}% likely",
                    f"{s.points:.0f} pts to capture from {price:.2f} "
                    f"by close ({align}).",
                    critical=s.points >= 2 * min_points)
        dedup.clear(active)

        if poll_seconds:
            time.sleep(poll_seconds)
