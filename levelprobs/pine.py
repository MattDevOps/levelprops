"""Pine Script export -> named levels (Python TRUSTS Pine's columns).

The friend's pipeline computes all level/order structure in Pine Script
(TradingView) and exports it as the wide CSV in data/. Rather than recomputing
levels (levels.py / orderblocks.py), Python reads the named price levels
straight out of a Pine export row and tags them onto the auto-scan ladder.

Only a curated, high-signal subset of the ~110 exported columns is surfaced
(daily order structure + key intraday references). Distant levels never land on
a rung -- the ladder fizzles out below ~3% probability -- so the whole set can
be listed without cluttering the output; only in-range levels get tagged.
"""
import csv

# Exact Pine column name -> short ladder tag, in priority order (first wins on a
# shared rung). Buy Above / Sell Below are the order-trigger levels and lead.
LEVEL_COLUMNS = [
    ("Buy Above", "Buy>"),
    ("Sell Below", "Sell<"),
    ("Major Resistance1", "R1"),
    ("Major Support1", "S1"),
    ("Major Resistance2", "R2"),
    ("Major Support2", "S2"),
    ("Major Resistance3", "R3"),
    ("Major Support3", "S3"),
    ("Major Resistance4", "R4"),
    ("Major Support4", "S4"),
    ("Major Resistance5", "R5"),
    ("Major Support5", "S5"),
    ("BuyTGT1", "BTGT1"),
    ("Buy TGT2", "BTGT2"),
    ("Buy TGT3", "BTGT3"),
    ("Sell TGT1", "STGT1"),
    ("Sell TGT2", "STGT2"),
    ("Sell TGT3", "STGT3"),
    ("ON High", "ONH"),
    ("ON Low", "ONL"),
    ("IB High", "IBH"),
    ("IB Low", "IBL"),
    ("PW High", "PWH"),
    ("PW Low", "PWL"),
    ("PVI High", "PVIH"),
    ("PVI Low", "PVIL"),
    ("10:30 High", "10:30H"),
    ("10:30 Low", "10:30L"),
    ("VWAP", "VWAP"),
]


def extract_levels(row: dict) -> list:
    """Pull (price, tag) named levels from one Pine export row.

    Skips empty/unparseable cells and de-dupes by rounded price (first tag in
    LEVEL_COLUMNS priority order wins) so a single rung isn't double-tagged.
    """
    out, seen = [], set()
    for col, tag in LEVEL_COLUMNS:
        raw = (row.get(col) or "").strip()
        if not raw:
            continue
        try:
            price = float(raw)
        except ValueError:
            continue
        key = round(price, 1)
        if key in seen:
            continue
        seen.add(key)
        out.append((round(price, 2), tag))
    return out


def levels_from_csv(path: str) -> list:
    """Named levels from the most recent (last) row of a Pine export CSV.

    Daily order structure (Buy Above / Major R-S / targets) is constant through
    the session, so the last row's values are the current day's levels.
    """
    last = None
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            last = row
    return extract_levels(last) if last is not None else []
