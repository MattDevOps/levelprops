"""Reference level construction.

Builds the set of price levels we want hit-probabilities for: prior-day
High/Low/Close, the overnight range, and nearby round numbers. Order-block
levels are added separately (see orderblocks.py) so this stays pure/simple.
"""
from dataclasses import dataclass

from .instruments import Instrument
from .model import Session


@dataclass
class Level:
    name: str
    price: float
    kind: str   # 'pdh','pdl','pdc','onh','onl','round','ob'


def round_levels(inst: Instrument, price: float, span: int = 2) -> list:
    """Round-number levels within +/- span*spacing of price."""
    s = inst.round_spacing
    base = round(price / s) * s
    out = []
    for k in range(-span, span + 1):
        p = base + k * s
        if p > 0:
            out.append(Level(f"Round {int(p)}", round(p, 2), "round"))
    return out


def reference_levels(inst: Instrument, prior: Session, current_overnight_high: float,
                     current_overnight_low: float, price: float) -> list:
    """The classic intraday reference levels for 'today'."""
    levels = [
        Level("Prior Day High", prior.rth_high, "pdh"),
        Level("Prior Day Low", prior.rth_low, "pdl"),
        Level("Prior Day Close", prior.rth_close, "pdc"),
        Level("Overnight High", current_overnight_high, "onh"),
        Level("Overnight Low", current_overnight_low, "onl"),
    ]
    levels.extend(round_levels(inst, price))
    # de-dupe by (rounded price, kind-priority): keep first occurrence
    seen, deduped = set(), []
    for lv in levels:
        key = round(lv.price, 1)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(lv)
    return deduped
