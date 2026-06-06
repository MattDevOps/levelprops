"""Alert condition: a tradeable setup worth a desktop notification.

A level being 95% likely to be hit but 2 points away is useless. The value is
the *farthest* level that still clears the probability bar -- that distance is
the move you can actually capture. So for each side we take the most distant
ladder rung with P(touch) >= min_prob, and only alert if that distance is at
least `min_points` (your "big enough move to capture serious points" floor).

The directional bias (broke-high-first vs broke-low-first) is attached so the
notification can say whether the setup aligns with the day's lean.
"""
from dataclasses import dataclass


@dataclass
class Setup:
    direction: str    # 'up' | 'down'
    target: float     # the farthest level still >= min_prob
    prob: float       # its touch probability
    points: float     # distance from current price (the capturable move)
    aligned: bool     # does it agree with the first-break bias?

    @property
    def side_word(self) -> str:
        return "LONG" if self.direction == "up" else "SHORT"


def find_setups(result: dict, min_prob: float = 0.80,
                min_points: float = 15.0) -> list:
    """Return tradeable Setups (0, 1, or 2) from a compute() result dict."""
    price = result["price"]
    rungs = result["rungs"]
    bh = result["bias"]["broke_high"]
    bl = result["bias"]["broke_low"]
    bias_up = bh >= bl

    setups = []
    for direction, above in (("up", True), ("down", False)):
        side = [r for r in rungs if r["above"] == above and r["prob"] >= min_prob]
        if not side:
            continue
        far = max(side, key=lambda r: abs(r["price"] - price))
        points = abs(far["price"] - price)
        if points < min_points:
            continue
        setups.append(Setup(direction, far["price"], far["prob"], points,
                            aligned=(bias_up == (direction == "up"))))
    # strongest (most points) first
    setups.sort(key=lambda s: s.points, reverse=True)
    return setups
