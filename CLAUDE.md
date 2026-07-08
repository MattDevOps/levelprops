# levelprobs — standing brief

WHAT THIS IS: Pure-stdlib Python CLI that reproduces a friend's TradingView "probability a level gets hit" indicator for ES/NQ/SPX: recency-weighted intraday level-hit probabilities plus a broke-high-first / broke-low-first directional bias, printed as a red/green terminal report. Auto-scans a price ladder outward (no target needed); `--target` is an optional spotlight.

STATE: Built and working, committed on `main` (HEAD e2baa94, tree clean). Live source is Yahoo `^GSPC` 5-min polling (the whole TradingView webhook/ngrok/CSV saga is RETIRED). systemd user unit `deploy/levelprobs.service` runs `--watch --feed yahoo`. Interview-prep + friend-tool project, not a shipped product. Resume points: none blocking; historic open item was coarse probs, resolved by Yahoo auto-history (60d ~59 sessions).

STACK: Python 3.14, pure stdlib — no numpy/pandas/pytest/requests (verified; Yahoo feed uses urllib). Built on a 5-min bar grid; 15-min is a one-line `BAR_MINUTES` change.

HOW TO WORK HERE:
- Run (one-shot report, synthetic tape): `python3 -m levelprobs ES --time 10:25` (add `--target 7530` to spotlight). Entry point is `levelprobs/__main__.py`.
- Run (live dashboard, real Yahoo data): `python3 -m levelprobs SPX --demo`
- Run (live alert loop): `python3 -m levelprobs SPX --watch` (fires notify-send desktop alerts)
- Test: `python3 -m unittest discover -s tests` (10 tests; verified pass)
- Model: empirical remaining-session excursion distribution, recency-weighted by `0.5 ** (sessions_ago / halflife)`, halflife=252 sessions. Core engine `engine.py`; public API `api.py` (`compute`/`analyze`).
- Real data / Pine levels: `--history-csv data/spx_history.csv` overlays the friend's Pine-exported named levels (`pine.py` maps columns to ladder tags; Python TRUSTS Pine's levels, does not recompute). Loader needs 5-min RTH bars, US/Eastern (`loaders.load_sessions_from_csv`, format in `data/README.md`).

NEVER:
- Do not treat synthetic-tape numbers as real. One-shot `--time` report uses SYNTHETIC data by design (`--feed` is ignored there); only `--demo`/`--watch` use real Yahoo bars.
- Alerts are SPX-only by design (`watch.py` ALERT_SYMBOL="SPX"); do not wire ES/NQ into `--watch`.
- Do not re-add the TradingView webhook / ngrok / cloudflared / manual-CSV-export live path — it was deliberately retired for the outbound Yahoo poll.
- Do not re-derive levels in Python when a Pine `--history-csv` is supplied (that duplication was intentionally removed).

DONE = one-shot report and live Yahoo dashboard/watch run clean, 10 tests pass, tree committed on main.
