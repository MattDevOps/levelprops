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

### Plugging into TradingView (the real thing)

TradingView has no free public data API, so there are two honest paths:

**A. TradingView alert -> webhook -> local Python** (most literal "plug in")
Requires a paid TradingView plan (webhooks are Pro+) and a public URL to reach
your machine (e.g. `ngrok http 8731`).

1. Run the receiver:
   ```bash
   python3 -m levelprobs SPX --watch --feed webhook --port 8731 --poll 10
   ```
2. In TradingView, create an alert on SPX (condition: "once per bar close"),
   enable **Webhook URL** = your ngrok URL, and set the message to:
   ```json
   {"price": {{close}}}
   ```
   TradingView POSTs the price on every bar close; the loop recomputes and
   notifies you. (Historical bars still come from the synthetic tape until you
   wire a real history source via `loaders.load_sessions_from_csv` -- see below.)

**B. Independent data feed (IBKR / Databento / Polygon)**
Python pulls live + historical SPX/ES bars itself and you keep TradingView open
as your chart. Add a feed class in `feeds.py` with a `snapshot()` returning
`(history, today, bar_index, price)` -- the IBKR sketch (`ib_insync`
`reqHistoricalData` + live ticks) is noted in that file. This is the most robust
path if you have a brokerage data subscription.

> Until a real history source is wired, the **probabilities are synthetic**
> (the alert *mechanism* is real, the numbers are not). Wire `history`/`today`
> from real bars to make them meaningful.

### Full setup: TradingView Pro+ webhook + auto-start (the configured path)

1. **Export history** from TradingView (SPX, 5-min) and save it to
   `data/spx_history.csv`. See `data/README.md` for the format. Verify:
   ```bash
   python3 -c "from levelprobs.loaders import load_sessions_from_csv as L; print(len(L('data/spx_history.csv')),'sessions')"
   ```
2. **Run the receiver** (foreground, to test):
   ```bash
   python3 -m levelprobs SPX --watch --feed webhook \
       --history-csv data/spx_history.csv --port 8731 --poll 10
   ```
3. **Expose it** so TradingView can reach your machine:
   ```bash
   ngrok http 8731      # copy the https URL it prints
   ```
4. **Create the TradingView alert** on SPX: condition "once per bar close",
   enable **Webhook URL** = `https://<your-ngrok>.ngrok-free.app`, message:
   ```json
   {"price": {{close}}}
   ```
   Now every bar close pushes the price; the loop recomputes and pops a desktop
   alert when P(touch) >= 80% with a >= 15-pt capturable move.

5. **Auto-start on login** (systemd user service, already installed at
   `~/.config/systemd/user/levelprobs.service`):
   ```bash
   # edit the --history-csv path in the unit if needed, then:
   systemctl --user daemon-reload
   systemctl --user enable --now levelprobs.service
   systemctl --user status levelprobs.service     # check it's running
   journalctl --user -u levelprobs.service -f      # live logs
   ```
   (The service is installed but **disabled** until you drop in the CSV --
   enabling it without history would crash-loop. ngrok still needs to run
   separately, or add a second user service for it.)

Live price drives "today" (bars built from the stream); the CSV is the
historical base the probabilities are computed against.

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
  feeds.py         live feeds: synthetic replay + TradingView webhook
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
