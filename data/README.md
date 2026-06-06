# data/

Put your real **SPX 5-minute RTH history** here as `spx_history.csv` (that's the
path the systemd service expects).

## Exporting from TradingView

1. Open an **SPX** (or ES) chart on the **5-minute** timeframe.
2. Scroll back to load as much history as you want (aim for ~1 year / 252
   sessions; more is fine).
3. Export: right-side menu or **TradingView → Export chart data** (Pro+ feature)
   → downloads a CSV.
4. Save/rename it to `spx_history.csv` in this folder.

## Expected format

One row per 5-minute bar, header row required (column names case-insensitive):

```
timestamp,open,high,low,close
2026-05-01T09:30:00,7510.25,7512.00,7508.50,7511.75
2026-05-01T09:35:00,7511.75,7514.25,7510.00,7513.50
...
```

- `timestamp` ISO-8601, **US/Eastern** wall-clock.
- Bars before 09:30 ET feed that day's overnight high/low; 09:30-15:55 are RTH.
- A TradingView export may use a different header (e.g. `time`); rename the
  column to `timestamp` or adjust `levelprobs/loaders.py:_parse_row`.

Sanity-check the file loads:

```bash
python3 -c "from levelprobs.loaders import load_sessions_from_csv as L; \
print(len(L('data/spx_history.csv')), 'sessions loaded')"
```
