"""Live full-report dashboard.

Re-renders the whole report (directional bias + Pine-levels price ladder) in
place on every tick, so you can watch P(touch) move with the market. It is
feed-agnostic -- give it any feed whose snapshot() returns
(history, today, bar_index, price):

  * CsvReplayFeed          -- replays your real TradingView export bar-by-bar
                              (instant demo; real SPX prices, time-compressed)
  * TradingViewWebhookFeed -- truly live: TradingView alert -> webhook -> here

Levels are TRUSTED from the Pine export (api.compute named_override), re-read
from the CSV each tick so re-pulling the export updates the board live.
"""
import time as _time
from datetime import datetime, time as dtime

from .api import compute
from .alerts import find_setups
from .report import render, G, R, DIM, B, X, _pct
from .model import label_for_bar

CLEAR = "\033[2J\033[3J\033[H"   # clear screen + scrollback, cursor home


def _wall_clock():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
    except Exception:
        return datetime.now().strftime("%H:%M:%S")


def _header(symbol, tick, mode, setups, refresh):
    alert = ""
    if setups:
        s = setups[0]
        col = G if s.direction == "up" else R
        alert = (f"   {col}{B}>> ALERT {s.side_word} {s.target:g} "
                 f"({_pct(s.prob)}, {s.points:.0f}p){X}")
    return (f"{G}{B}* LIVE{X} {B}LEVELPROBS{X} {DIM}-- {symbol} -- {mode} -- "
            f"tick {tick} -- {_wall_clock()} ET -- refresh {refresh:g}s{X}{alert}")


def run_dashboard(feed, symbol, csv_path=None, halflife=252,
                  refresh_seconds=1.0, min_prob=0.80, min_points=15.0,
                  mode="live", synthetic=False, max_ticks=None, clear=True):
    """Render the report on a loop until the feed is exhausted / max_ticks."""
    iters = 0
    while True:
        if max_ticks and iters >= max_ticks:
            break
        iters += 1
        snap = feed.snapshot()
        if snap is None:
            print(f"{DIM}feed exhausted -- session over{X}")
            return "exhausted"
        if not getattr(feed, "ready", True):
            msg = f"{DIM}waiting for first live SPX tick from TradingView...{X}"
            print((CLEAR if clear else "") + _header(symbol, iters, mode, [],
                                                      refresh_seconds) + "\n\n" + msg)
            if refresh_seconds:
                _time.sleep(refresh_seconds)
            continue

        history, today, bar_index, price = snap
        named = None
        if csv_path:
            try:
                from .pine import levels_at
                named = levels_at(csv_path, today.day,
                                  dtime.fromisoformat(label_for_bar(bar_index)))
            except Exception:
                named = None

        res = compute(symbol, history, today, bar_index, price=price,
                      halflife=halflife, named_override=named)
        setups = find_setups(res, min_prob, min_points)
        body = render(res["symbol"], res["n_sessions"], synthetic, res["price"],
                      res["time_label"], res["bar_index"], res["bars_per_rth"],
                      res["cur_atr"], res["bias"], res["rungs"], res["order_blocks"])
        head = _header(symbol, iters, mode, setups, refresh_seconds)
        print((CLEAR if clear else "") + head + "\n" + body, flush=True)

        if refresh_seconds:
            _time.sleep(refresh_seconds)
    return "done"
