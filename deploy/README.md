# deploy/

`levelprobs.service` is the canonical copy of the systemd **user** service that
runs the live SPX alert loop (Yahoo Finance `^GSPC` -> desktop notifications).

The active copy lives at `~/.config/systemd/user/levelprobs.service`. This repo
copy is for version control / reinstalling on a new machine.

## Install / update

```bash
cp deploy/levelprobs.service ~/.config/systemd/user/levelprobs.service
systemctl --user daemon-reload
systemctl --user enable --now levelprobs.service
```

## Manage

```bash
systemctl --user status levelprobs        # is it running?
journalctl --user -u levelprobs -f         # live logs
systemctl --user restart levelprobs        # after editing the unit
systemctl --user disable --now levelprobs  # stop + remove from login
```

## Current state (2026-06-07)

- Enabled and running; auto-starts on login.
- Feed: **Yahoo Finance `^GSPC`** (`--feed yahoo`, polls every 20s). No account,
  no API key, no inbound tunnel; history is pulled from Yahoo automatically.
- Alerts are **suppressed while the market is closed** (logs `market closed`
  off-hours) and start firing at the RTH open. No CSV or placeholder needed.

## Notes / optional

- **Pine level overlay** is *not* used by the alert daemon (alerts run off the
  auto-scan ladder). To see Pine levels on the live dashboard, re-export the
  TradingView CSV daily and run `--demo --history-csv <today's export>`.
- **Webhook path is retired** here in favor of Yahoo (it needed a paid
  TradingView plan + an ngrok tunnel that was never set up). The `webhook` feed
  still exists in code if you ever want it: see the README "Plugging in real
  data" section.
