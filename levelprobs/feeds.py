"""Data feeds for the live watch loop.

A feed just answers one question on demand: `snapshot()` ->
`(history, today, bar_index, price)`, or `None` when the session is over.
The watch loop is feed-agnostic, so swapping data sources never touches the
engine.

Included:
  * SyntheticReplayFeed   -- replays a synthetic day bar-by-bar (demo / no data)
  * TradingViewWebhookFeed -- real: a local HTTP server fed by TradingView alerts

Documented swap-ins (add as needed):
  * CSV/poll feed   -- re-read a file your platform appends bars to
  * IBKR feed       -- ib_insync reqHistoricalData + live ticks (TWS/Gateway)
"""
import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from .api import synthetic_tape
from .model import Bar, Session, bar_index_for, RTH_OPEN, BARS_PER_RTH


class SyntheticReplayFeed:
    """Replays one synthetic RTH session, advancing one 5-min bar per snapshot.
    Useful to see probabilities evolve and alerts fire with no live data."""

    def __init__(self, symbol: str, start_bar: int = 0, end_bar: int = None,
                 sessions: int = 1280, seed: int = 7):
        self.symbol = symbol
        self.history, self.today = synthetic_tape(symbol, sessions, seed)
        self.cursor = start_bar
        self.end_bar = BARS_PER_RTH - 1 if end_bar is None else end_bar

    def snapshot(self):
        if self.cursor > self.end_bar:
            return None
        bi = self.cursor
        price = self.today.bars[bi].c
        self.cursor += 1
        return self.history, self.today, bi, price


class CsvReplayFeed:
    """Replays a REAL TradingView CSV export one RTH bar per snapshot, so the
    live dashboard ticks with actual SPX prices (time-compressed). history =
    all prior sessions; today = the most recent session, revealed bar-by-bar."""

    def __init__(self, path: str, start_bar: int = 0, end_bar: int = None):
        from .loaders import load_sessions_from_csv
        sess = load_sessions_from_csv(path, warn=False)
        if len(sess) < 2:
            raise ValueError("need >= 2 sessions in the CSV to replay")
        self.symbol = "SPX"
        self.history, self.today = sess[:-1], sess[-1]
        self.cursor = max(0, start_bar)
        self.end_bar = (len(self.today.bars) - 1) if end_bar is None else end_bar

    def snapshot(self):
        if self.cursor > self.end_bar:
            return None
        bi = self.cursor
        price = self.today.bars[bi].c
        self.cursor += 1
        return self.history, self.today, bi, price


class _LiveToday:
    """Accumulates the current session's bars + overnight high/low from a price
    stream, so 'today' is built live instead of taken from a fixed tape."""

    def __init__(self, prior_close: float, start_price: float):
        self.prior_close = prior_close
        self.on_hi = self.on_lo = start_price
        self.bars = {}   # bar_index -> [o, h, l, c]
        self.last_price = start_price
        self.got_tick = False   # True once a real price has arrived

    def update(self, t, price: float) -> None:
        self.last_price = price
        self.got_tick = True
        if t < RTH_OPEN:                      # overnight tick
            self.on_hi = max(self.on_hi, price)
            self.on_lo = min(self.on_lo, price)
            return
        bi = bar_index_for(t)
        if bi not in self.bars:
            self.bars[bi] = [price, price, price, price]
        else:
            o, h, l, _ = self.bars[bi]
            self.bars[bi] = [o, max(h, price), min(l, price), price]

    def session(self, day=None) -> Session:
        """Build a Session with a contiguous bar list up to the latest bar
        (gaps forward-filled flat at the prior price)."""
        top = max(self.bars) if self.bars else 0
        bars, last = [], self.prior_close
        for i in range(top + 1):
            if i in self.bars:
                o, h, l, c = self.bars[i]
                last = c
            else:
                o = h = l = c = last
            bars.append(Bar(o, h, l, c))
        if not bars:
            bars = [Bar(self.last_price, self.last_price,
                        self.last_price, self.last_price)]
        return Session(day=day or datetime.now().date(), bars=bars,
                       overnight_high=self.on_hi, overnight_low=self.on_lo,
                       prior_close=self.prior_close)


class TradingViewWebhookFeed:
    """Real integration: TradingView alert -> webhook -> this local server.

    Set a TradingView alert (fires on bar close) with webhook URL pointing here
    and message body:  {"price": {{close}}}

    `history` should be real completed sessions (e.g. from
    loaders.load_sessions_from_csv of a TradingView export); 'today' is built
    live from the incoming price stream. Falls back to a synthetic tape if no
    history is supplied.
    """

    def __init__(self, symbol: str, host: str = "0.0.0.0", port: int = 8731,
                 history=None, sessions: int = 1280, seed: int = 7,
                 tz: str = "America/New_York"):
        self.symbol = symbol
        if history is None:
            history, _ = synthetic_tape(symbol, sessions, seed)
        self.history = history
        start = history[-1].rth_close
        self._live = _LiveToday(prior_close=start, start_price=start)
        self._lock = threading.Lock()
        self._tz = tz
        feed = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(n).decode("utf-8", "replace")
                try:
                    px = float(json.loads(raw).get("price"))
                except (ValueError, TypeError, json.JSONDecodeError):
                    px = None
                if px is not None:
                    with feed._lock:
                        feed._live.update(feed._now_et(), px)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *a):
                pass  # quiet

        self._server = HTTPServer((host, port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        print(f"[webhook] listening on http://{host}:{port}  "
              f"(POST JSON {{\"price\": <number>}})")

    @property
    def ready(self) -> bool:
        return self._live.got_tick

    def _now_et(self):
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(self._tz)).time()
        except Exception:
            return datetime.now().time()

    def snapshot(self):
        t = self._now_et()
        with self._lock:
            today = self._live.session()
            price = self._live.last_price
        return self.history, today, bar_index_for(t), price
