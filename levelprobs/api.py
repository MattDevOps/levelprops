"""High-level orchestration: data -> levels -> probabilities -> report.

`compute()` returns structured results (used by the live watch loop).
`analyze()` wraps it and returns the colorized text report. Both run on
synthetic data by default; pass real Sessions via `history`/`today`.
"""
from datetime import date, time

from .instruments import get_instrument
from .model import bar_index_for, label_for_bar, BARS_PER_RTH
from .synth import generate_sessions
from .levels import reference_levels, Level
from .orderblocks import detect_order_blocks
from .engine import (make_weight_fn, current_atr, first_break_stats,
                     touch_probability)
from .ladder import build_ladder
from .report import render

ANCHOR = date(2026, 6, 5)   # most-recent synthetic session (deterministic)


def synthetic_tape(symbol: str, sessions: int = 1280, seed: int = 7):
    """Generate (history, today) of synthetic sessions for `symbol`."""
    inst = get_instrument(symbol)
    seed_off = {"ES": 0, "SPX": 11, "NQ": 29}.get(inst.name, 0)
    gen = generate_sessions(inst, sessions + 1, ANCHOR, seed=seed + seed_off)
    return gen[:-1], gen[-1]


def compute(symbol, history, today, bar_index, price=None, halflife=252,
            targets=None, named_override=None) -> dict:
    """Run the full analysis at a given bar_index/price; return structured data.

    named_override: optional list of (price, label) levels to tag onto the
    ladder. When supplied (the Pine-export path), Python TRUSTS those levels and
    skips recomputing reference levels / order blocks; pass None to recompute.
    """
    inst = get_instrument(symbol)
    weight_fn = make_weight_fn(halflife)
    prior = history[-1]
    if price is None:
        price = today.bars[bar_index].c
    cur_atr = current_atr(history)

    if named_override is not None:
        # Trust Pine's levels: tag them straight onto the ladder, no recompute.
        named = list(named_override)
        for tp in (targets or []):
            named.append((float(tp), f"TGT {tp:g}"))
        ob_scored = []
    else:
        levels = reference_levels(inst, prior, today.overnight_high,
                                  today.overnight_low, price)
        for tp in (targets or []):
            levels.append(Level(f"Target {tp:g}", float(tp), "user"))

        ob_bars = prior.bars + today.bars[:bar_index + 1]
        obs = detect_order_blocks(ob_bars)
        ob_scored = []
        for ob in obs:
            target = ob.proximal
            above = target >= price
            p = touch_probability(history, bar_index, abs(target - price),
                                  "up" if above else "down", cur_atr, weight_fn)
            ob_scored.append({"kind": ob.kind, "low": ob.low, "high": ob.high,
                              "mid": ob.mid, "prob": p})

        short = {"Prior Day High": "PDH", "Prior Day Low": "PDL",
                 "Prior Day Close": "PDC", "Overnight High": "ONH",
                 "Overnight Low": "ONL"}
        named = [(lv.price, short.get(lv.name, lv.name)) for lv in levels
                 if lv.kind != "round"]
        for ob in obs:
            named.append((ob.proximal, f"{'Bull' if ob.kind == 'bull' else 'Bear'} OB"))

    rungs = build_ladder(history, bar_index, price, cur_atr, inst.ladder_step,
                         weight_fn, named=named)

    bias = first_break_stats(history, window=252, weight_fn=weight_fn)

    return {"symbol": symbol, "price": price, "bar_index": bar_index,
            "time_label": label_for_bar(bar_index), "cur_atr": cur_atr,
            "n_sessions": len(history), "bias": bias, "rungs": rungs,
            "order_blocks": ob_scored, "bars_per_rth": BARS_PER_RTH}


def analyze(symbol: str = "ES", sessions: int = 1280, at_time: str = "10:25",
            halflife: int = 252, price: float = None, targets: list = None,
            seed: int = 7, history=None, today=None, named_override=None) -> str:
    """Return a colorized intraday level-probability report.

    Pass history/today (and named_override = Pine levels) to run on real data;
    omit them to run on synthetic tape.
    """
    synthetic = history is None
    if synthetic:
        history, today = synthetic_tape(symbol, sessions, seed)
    bar_index = bar_index_for(time.fromisoformat(at_time))

    r = compute(symbol, history, today, bar_index, price=price,
                halflife=halflife, targets=targets, named_override=named_override)
    return render(r["symbol"], r["n_sessions"], synthetic, r["price"],
                  r["time_label"], r["bar_index"], r["bars_per_rth"],
                  r["cur_atr"], r["bias"], r["rungs"], r["order_blocks"])
