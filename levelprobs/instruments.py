"""Per-instrument parameters.

Synthetic seeds (start_price / annual_vol / daily_drift) are only used by the
sample-data generator. When you swap in real bars they are ignored.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    name: str
    tick_size: float          # smallest price increment
    point_value: float        # $ per 1.0 point per contract (index = 0 / NA)
    round_spacing: float      # spacing of "round number" psychological levels
    ladder_step: float        # spacing of the auto-scan price ladder
    # --- synthetic-generator seeds (ignored for real data) ---
    anchor_price: float       # price the mean-reverting tape hovers around
    annual_vol: float         # annualized vol used to scale the random walk


INSTRUMENTS = {
    "ES": Instrument(
        name="ES", tick_size=0.25, point_value=50.0, round_spacing=25.0,
        ladder_step=5.0, anchor_price=7530.0, annual_vol=0.18,
    ),
    "SPX": Instrument(
        name="SPX", tick_size=0.01, point_value=0.0, round_spacing=25.0,
        ladder_step=5.0, anchor_price=7530.0, annual_vol=0.17,
    ),
    "NQ": Instrument(
        name="NQ", tick_size=0.25, point_value=20.0, round_spacing=100.0,
        ladder_step=25.0, anchor_price=22100.0, annual_vol=0.24,
    ),
}


def get_instrument(symbol: str) -> Instrument:
    key = symbol.upper()
    if key not in INSTRUMENTS:
        raise KeyError(f"unknown instrument {symbol!r}; known: {list(INSTRUMENTS)}")
    return INSTRUMENTS[key]
