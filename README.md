# levelprobs

Recency-weighted **intraday level-hit probabilities** for ES / NQ / SPX — a
Python rebuild of the "probability a number gets hit" indicator (the kind that
prints *"91% that 7530 gets hit"* and a *Broke High First / Broke Low First*
metrics box).

Pure standard library. No numpy, no pandas, no install. Runs on synthetic data
out of the box; drop in real bars when you have them.

```
python3 -m levelprobs ES --time 10:25
```

No target needed — it **auto-scans every number** and reports the likelihood of
each getting hit. (`--target` exists only to spotlight a specific number.)

## What it computes

**1. Directional bias** (the metrics box from the screenshot)
Over the last ~252 sessions, how often price broke the *prior day's high*
before the *prior day's low* (and vice versa), plus the average up/down move.
This drives the headline **BUY/SELL lean** — green = buy-side, red = sell-side.

```
DIRECTIONAL BIAS (last 252 sessions, recency-weighted)
  Broke High First  43.8%     Broke Low First  44.5%     Neither  11.8%
  avg up 80.1 / avg dn 78.9 pts     >> lean SELL / SHORT (coin-flip)
```

**2. Auto-scan price ladder** (the "91% that 7530 hits" number, for *every* number)
It sweeps the whole price column outward from current price on a fixed step,
scoring P(touch before RTH close) for each rung, until the probability fizzles
below ~3% on each side. No target input — it reports whatever it finds, with
named levels (prior-day H/L/C, overnight range, order blocks) tagged inline.
Each rung is **conditioned on the current time of day** (a level 60 pts away is
far likelier at 10:00 than at 15:30) and **current volatility** (14-day ATR).

```
PRICE LADDER (auto-scan: P(touch) for every number before close)
   7565.00  ████████░░  79.2%  +19p
   7560.00  ████████░░  83.3%  +14p
   7555.00  █████████░  87.3%   +9p
   7550.00  █████████░  93.1%   +4p
>>>>   7545.66  ── CURRENT ── 13:00 ET
   7545.00  ██████████  96.4%   -1p
   7530.00  ████████░░  83.2%  -16p
   7505.00  ██████░░░░  61.4%  -41p
   7500.00  ██████░░░░  57.6%  -46p  ONH 7502.45
   ...
```

Green = above current price (buy-side), red = below (sell-side); bold at P≥80%.
The 3% cutoff and ladder step are tunable in `levelprobs/ladder.py` /
`instruments.py`.

**3. Order blocks** — unmitigated ICT order blocks (last opposing candle before
an impulsive move) with the probability price returns to them.

## How the probability is estimated

Empirical, not a closed-form model:

1. Split history into sessions of 5-minute RTH bars (09:30–16:00 ET).
2. For the **current time-of-day bar**, look at every historical session and
   measure how far price travelled up and down from that bar to the close
   (the *remaining-session excursion*), normalized by that session's range.
3. `P(touch)` = the **recency-weighted fraction** of sessions whose excursion
   was at least the distance to your level, where the level distance is
   normalized by *current* 14-day ATR (so it adapts to today's volatility).

**Recency weighting** is the key detail you asked for: each session's weight is
`0.5 ** (sessions_ago / halflife)` with `halflife = 252`. A session one year
ago counts half as much as today's; five years ago, ~1/32. So the **last 252
sessions dominate** while older history still nudges the estimate. Tune with
`--halflife` (smaller = more reactive, larger = smoother).

## Usage

```bash
python3 -m levelprobs ES                      # auto-scan ladder, default 10:25 ET
python3 -m levelprobs NQ --time 13:00          # evaluate later in the session
python3 -m levelprobs ES --halflife 120        # weight recent history harder
python3 -m levelprobs ES --price 7400          # override the 'current' price
python3 -m levelprobs SPX --target 7450        # also spotlight a specific number
```

As a library:

```python
from levelprobs import analyze
print(analyze("ES", at_time="11:00", targets=[7450]))
```

## Plugging in real data (replace the synthetic tape)

The engine only needs `list[Session]` (oldest first). A CSV loader is included:

```python
from levelprobs.loaders import load_sessions_from_csv
from levelprobs.api import analyze

sessions = load_sessions_from_csv("ES_5min.csv")   # timestamp,open,high,low,close
print(analyze("ES", history=sessions[:-1], today=sessions[-1]))
```

CSV = one 5-minute bar per row, US/Eastern timestamps. Bars before 09:30 feed
that day's overnight high/low; 09:30–15:55 are the RTH bars. See
`levelprobs/loaders.py` for the exact contract and how to adapt other formats
(Databento, Polygon, IBKR, TradingView export).

## Live dashboard (`--demo`)

A full-screen, self-refreshing view of the whole report -- directional bias +
the price ladder -- redrawn on every tick so you can watch `P(touch)` move as
price walks. The default source is **real, live data**:

```bash
# REAL & LIVE (default) -- polls Yahoo Finance for the ^GSPC cash index
# (5-min bars). No account, no API key, no tunnel. History is pulled from
# Yahoo automatically. During RTH this tracks the actual SPX in real time;
# off-hours it shows the last session, banner-flagged [MARKET CLOSED].
python3 -m levelprobs SPX --demo
#   --refresh 15    redraw / re-poll interval (seconds)

# REPLAY -- stream a recorded TradingView export bar-by-bar (real SPX prices,
# time-compressed; good for a screen recording). Not live:
python3 -m levelprobs SPX --demo --feed replay --history-csv data/spx_history.csv --repeat

# WEBHOOK -- truly live via a TradingView alert (needs a paid plan + tunnel;
# see "Plugging into TradingView" below). Yahoo is simpler and needs neither.
python3 -m levelprobs SPX --demo --feed webhook --history-csv data/spx_history.csv
```

### Pine level overlay (optional)

The named Pine levels (Buy Above / Sell Below, Major R-S, targets, ON/IB,
prior-week, VWAP) are computed by a proprietary TradingView indicator and live
**only** in its CSV export -- no live feed (Yahoo or webhook) can fetch them.
Pass `--history-csv` in `yahoo` mode to overlay them onto the live ladder:

```bash
python3 -m levelprobs SPX --demo --history-csv data/spx_history.csv
```

These tags are only current if that export is **today's**. With a stale export
(e.g. Friday's), the daily levels (R1-R5 etc.) are last session's and will be
wrong -- re-export each morning, or omit `--history-csv` to run the pure
auto-scan ladder (round numbers + `P(touch)`), which needs no TradingView at all.

## Live alerts (auto-run + desktop notifications)

Watch mode polls a feed, recomputes the ladder, and fires a **desktop
notification** (libnotify / `notify-send`) when there's a tradeable setup:
`P(touch) >= --min-prob` (default 80%) **and** the capturable move is
`>= --min-points` (default 15). The alert reports the *farthest* level still
above the probability bar -- that distance is what you can actually capture --
and whether it agrees with the day's directional bias.

**Alerts are SPX-only by design** (set in `watch.py:ALERT_SYMBOL`). ES/NQ still
work for one-shot reports, but `--watch` always evaluates SPX.

```bash
# demo on synthetic data (replays a day, fires popups so you can see it work):
python3 -m levelprobs SPX --watch --time 09:30 --poll 0 --min-points 20
```

### Plugging in real data

**A. Yahoo Finance (default, recommended).** Python polls Yahoo's public chart
API for the `^GSPC` cash index -- real 5-min OHLC bars, no account, no API key,
no inbound tunnel. Both *history* (the model base) and *today* (built live from
real bars) come from Yahoo, so the probabilities are real, not synthetic.

```bash
python3 -m levelprobs SPX --watch --feed yahoo --poll 20
```

Alerts are suppressed while the market is closed (Yahoo would otherwise return
the last session's stale close). The cash index `^GSPC` is used (not ES futures)
so prices line up with the SPX Pine levels rather than the futures basis.

**B. TradingView alert -> webhook -> local Python.** The literal "push from
TradingView" path. Requires a paid plan (webhooks are Pro+) and a public URL to
your machine (e.g. `ngrok http 8731`). More moving parts than Yahoo for the same
price; use it only if you specifically want TradingView as the source.

```bash
python3 -m levelprobs SPX --watch --feed webhook \
    --history-csv data/spx_history.csv --port 8731 --poll 10
# then: ngrok http 8731, and a TradingView "once per bar close" alert whose
# Webhook URL is the ngrok URL and whose message body is:  {"price": {{close}}}
```

**C. Independent data feed (IBKR / Databento / Polygon).** For a brokerage data
subscription: add a feed class in `feeds.py` with a `snapshot()` returning
`(history, today, bar_index, price)` -- the IBKR sketch (`ib_insync`
`reqHistoricalData` + live ticks) is noted in that file.

### Auto-start on login (systemd user service)

Installed and running at `~/.config/systemd/user/levelprobs.service`, configured
for the **Yahoo** feed -- no CSV, no tunnel, fully self-contained:

```bash
cp deploy/levelprobs.service ~/.config/systemd/user/levelprobs.service
systemctl --user daemon-reload
systemctl --user enable --now levelprobs.service
systemctl --user status levelprobs.service     # check it's running
journalctl --user -u levelprobs.service -f      # live logs (shows "market closed" off-hours)
```

## A note on timeframe

The screenshot used 5/15-min charts; this runs on a **5-minute RTH grid**
(78 bars/session), which the time-of-day conditioning depends on. A 15-minute
mode is a one-line change (`BAR_MINUTES`) if you want it.

## Layout

```
levelprobs/
  instruments.py   per-symbol tick size, round-number spacing, synth seeds
  model.py         Bar / Session, the RTH 5-min grid
  synth.py         mean-reverting synthetic tape (swap-out point)
  loaders.py       real CSV -> Session (swap-in point)
  levels.py        prior-day H/L/C, overnight range, round numbers
  orderblocks.py   ICT order-block detection
  ladder.py        auto-scan: P(touch) for every rung of the price column
  engine.py        recency-weighted first-break + touch probability  <- core
  report.py        red/green terminal report
  api.py           orchestration (compute() data + analyze() text)
  alerts.py        tradeable-setup condition (>= prob AND >= points)
  notify.py        desktop notifications (notify-send) + de-dup
  feeds.py         live feeds: Yahoo poll (default), CSV/synthetic replay, webhook
  watch.py         live loop (SPX-only alerts)
tests/test_engine.py   property tests (monotonicity, time-decay, weighting)
data/              real SPX history CSV + format docs
deploy/            systemd user service + install/manage notes
docs/              reference screenshot of the original indicator
```

## Caveats

These are **historical frequencies, not guarantees**. Synthetic data is for
wiring/demo only — its numbers are made up. The probabilities are only as good
as the real bars you feed it, and intraday markets are non-stationary (news,
sessions, regime shifts). Use as one input, not a signal to trade blindly.
# levelprops
