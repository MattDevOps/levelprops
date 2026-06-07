"""Real-data loader — the swap-in point for live ES/NQ/SPX bars.

The engine never assumes synthetic data; it just needs `list[Session]`
(oldest first) with 5-minute RTH bars. This module builds exactly that from a
CSV of intraday bars so you can replace the synthetic generator with one call:

    from levelprobs.loaders import load_sessions_from_csv
    from levelprobs.api import analyze
    sessions = load_sessions_from_csv("ES_5min.csv")
    print(analyze("ES", history=sessions[:-1], today=sessions[-1]))

Expected CSV columns (header, case-insensitive), one 5-minute bar per row:
    timestamp, open, high, low, close   (volume optional, ignored)
`timestamp` is parsed as ISO-8601. Timestamps are assumed to already be in
US/Eastern wall-clock (the RTH split uses 09:30-16:00 ET). Bars before 09:30
on a given date feed that date's overnight high/low; 09:30-15:55 are the RTH
bars. Days without a full RTH grid are skipped with a warning count.

This is intentionally a best-effort loader for the common export format. If
your feed differs (UTC timestamps, continuous contract stitching, tick data),
adapt `_parse_row` / the bucketing here — the rest of the package is unchanged.
"""
import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .model import (Bar, Session, RTH_OPEN, RTH_CLOSE, BARS_PER_RTH,
                    BAR_MINUTES, label_for_bar)


def _et(dt):
    """Return dt expressed in US/Eastern (exchange time for SPX RTH)."""
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(et)
    except Exception:
        return dt


def row_timestamp(row: dict):
    """Parse a CSV row's timestamp to a US/Eastern datetime (the RTH clock).

    Accepts TradingView's `time`/`timestamp`/`date` column as ISO-8601 or Unix
    epoch seconds. Shared by the bar loader and the Pine level reader so both
    bucket rows onto the same trading day / bar time.
    """
    low = {k.lower().strip(): v for k, v in row.items()}
    raw_ts = (low.get("timestamp") or low.get("time") or low.get("date") or "").strip()
    try:                                  # ISO-8601 (with or without tz offset / Z)
        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except ValueError:                    # Unix epoch seconds (UTC) fallback
        ts = datetime.fromtimestamp(int(float(raw_ts)), tz=timezone.utc)
    return _et(ts)                        # normalize to Eastern before the RTH split


def _parse_row(row: dict) -> tuple:
    low = {k.lower().strip(): v for k, v in row.items()}
    bar = Bar(float(low["open"]), float(low["high"]),
              float(low["low"]), float(low["close"]))
    return row_timestamp(row), bar


def sessions_from_pairs(pairs, warn=True, require_full=True, source="feed") -> list:
    """Build oldest-first `list[Session]` from (ET-datetime, Bar) pairs.

    Shared by the CSV loader and any live feed (e.g. Yahoo) so both bucket bars
    onto the same trading-day / RTH grid. `require_full` skips days without a
    near-complete RTH grid (right for history); pass False to keep a partial
    day (right for a still-forming live session).
    """
    by_day = defaultdict(list)
    for ts, bar in pairs:
        by_day[ts.date()].append((ts, bar))

    sessions, skipped, prior_close = [], 0, None
    for day in sorted(by_day):
        rows = sorted(by_day[day], key=lambda x: x[0])
        on = [b for ts, b in rows if ts.time() < RTH_OPEN]
        rth = [b for ts, b in rows if RTH_OPEN <= ts.time() < RTH_CLOSE]
        if require_full and len(rth) < BARS_PER_RTH * 0.8:
            skipped += 1
            continue
        if not rth:                          # nothing in RTH yet (pre-open)
            skipped += 1
            continue
        rth = rth[:BARS_PER_RTH]
        on_prices = [p for b in on for p in (b.h, b.l)] or [rth[0].o]
        sessions.append(Session(
            day=day, bars=rth,
            overnight_high=max(on_prices), overnight_low=min(on_prices),
            prior_close=prior_close if prior_close is not None else rth[0].o,
        ))
        prior_close = rth[-1].c

    if warn and skipped:
        print(f"[loaders] skipped {skipped} day(s) without a near-complete RTH grid")
    if not sessions:
        raise ValueError(f"no usable sessions parsed from {source!r}")
    return sessions


def load_sessions_from_csv(path: str, warn=True) -> list:
    """Build oldest-first `list[Session]` from a 5-minute intraday CSV."""
    with open(path, newline="") as f:
        pairs = [_parse_row(row) for row in csv.DictReader(f)]
    return sessions_from_pairs(pairs, warn=warn, source=path)


def sessions_to_csv(sessions: list, path: str) -> None:
    """Write sessions back out in the expected CSV format (RTH bars only).

    Handy for (a) seeing the exact format the loader wants, and (b) testing the
    round-trip. Overnight bars are not emitted (synthetic Sessions only store
    the ON high/low summary), so a reloaded file recomputes ON from the RTH open.
    """
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close"])
        for s in sessions:
            for i, b in enumerate(s.bars):
                hh, mm = divmod(9 * 60 + 30 + i * BAR_MINUTES, 60)
                ts = f"{s.day.isoformat()}T{hh:02d}:{mm:02d}:00"
                w.writerow([ts, b.o, b.h, b.l, b.c])
