"""ICT-style order block detection.

An *order block* is the last opposing candle before an impulsive (displacement)
move that breaks structure:

  * Bullish OB = last down-close bar before a strong up-move. Acts as support.
  * Bearish OB = last up-close bar before a strong down-move. Acts as resistance.

Price often returns ("mitigates") to these zones, which is exactly the kind of
level we want a touch-probability for. We keep only *unmitigated* blocks (price
has not yet traded back through the zone) since those are the open targets.
"""
from dataclasses import dataclass

from .model import Bar


@dataclass
class OrderBlock:
    kind: str       # 'bull' | 'bear'
    low: float
    high: float
    index: int      # bar index where the OB candle sits

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def proximal(self) -> float:
        """Edge price reacts to first: top for a bull OB, bottom for a bear OB."""
        return self.high if self.kind == "bull" else self.low


def _atr_bar(bars: list) -> float:
    return sum(b.h - b.l for b in bars) / max(1, len(bars))


def detect_order_blocks(bars: list, lookahead: int = 3, disp_mult: float = 1.35,
                        max_blocks: int = 4) -> list:
    """Return up to `max_blocks` recent unmitigated order blocks.

    `disp_mult` * average-bar-range is the displacement threshold over
    `lookahead` bars that qualifies a move as impulsive.
    """
    if len(bars) <= lookahead + 1:
        return []
    atr = _atr_bar(bars)
    threshold = disp_mult * atr * lookahead
    candidates = []
    for i in range(len(bars) - lookahead):
        net = bars[i + lookahead].c - bars[i].c
        bar = bars[i]
        bullish_bar = bar.c >= bar.o
        if net >= threshold and not bullish_bar:
            candidates.append(OrderBlock("bull", bar.l, bar.h, i))
        elif net <= -threshold and bullish_bar:
            candidates.append(OrderBlock("bear", bar.l, bar.h, i))

    # keep only unmitigated blocks (price hasn't traded back through the zone)
    last_close = bars[-1].c
    unmitigated = []
    for ob in candidates:
        after = bars[ob.index + 1:]
        touched = any(b.l <= ob.high and b.h >= ob.low for b in after[lookahead:])
        # a fresh block: not revisited after the impulse, and not already passed
        if not touched and (ob.low <= last_close <= ob.high or
                            (ob.kind == "bull" and last_close > ob.high) or
                            (ob.kind == "bear" and last_close < ob.low)):
            unmitigated.append(ob)

    # most-recent first, de-overlap, cap
    unmitigated.sort(key=lambda o: o.index, reverse=True)
    out = []
    for ob in unmitigated:
        if any(abs(ob.mid - k.mid) < (ob.high - ob.low) for k in out):
            continue
        out.append(ob)
        if len(out) >= max_blocks:
            break
    return out
