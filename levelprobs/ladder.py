"""Auto-scan price ladder.

Instead of asking for specific targets, this sweeps EVERY rung of the price
ladder outward from the current price -- up and down on a fixed step -- and
scores P(touch before close) for each, stopping each side once the probability
fizzles below a floor. That answers "what's the likelihood of any number
getting hit, whatever it finds" with no input. Named reference levels
(prior-day H/L/C, overnight range, order blocks, round numbers) are snapped
onto the nearest rung as tags so context rides along with the raw ladder.
"""
import math

from .engine import touch_probability


def build_ladder(sessions, bar_index, price, cur_atr, step, weight_fn,
                 named=None, min_prob=0.03, max_rungs_per_side=40):
    """Return rungs as list of dicts {price, prob, above, tags} sorted high->low.

    named: optional list of (level_price, label) to tag onto nearby rungs.
    """
    named = named or []

    def scan(direction):
        rungs = []
        # first rung is the next clean multiple of step past current price
        if direction == "up":
            p = math.floor(price / step) * step + step
        else:
            p = math.ceil(price / step) * step - step
        for _ in range(max_rungs_per_side):
            needed = abs(p - price)
            prob = touch_probability(sessions, bar_index, needed, direction,
                                     cur_atr, weight_fn)
            if prob < min_prob:
                break
            rungs.append({"price": round(p, 2), "prob": prob,
                          "above": direction == "up", "tags": []})
            p += step if direction == "up" else -step
        return rungs

    rungs = scan("up") + scan("down")

    # snap named levels onto the nearest rung (within half a step)
    for lvl_price, label in named:
        nearest = min(rungs, key=lambda r: abs(r["price"] - lvl_price), default=None)
        if nearest and abs(nearest["price"] - lvl_price) <= step / 2:
            nearest["tags"].append(f"{label} {lvl_price:g}")

    rungs.sort(key=lambda r: r["price"], reverse=True)
    return rungs
