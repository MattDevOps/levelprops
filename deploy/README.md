# deploy/

`levelprobs.service` is the canonical copy of the systemd **user** service that
runs the live SPX alert loop (TradingView webhook -> desktop notifications).

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
systemctl --user restart levelprobs        # after replacing data/spx_history.csv
systemctl --user disable --now levelprobs  # stop + remove from login
```

## Current state (2026-06-05)

- Enabled and running; listening on port 8731; auto-starts on login.
- Loads `data/spx_history.csv` as the historical base.
- Waits for the first live price before alerting (won't fire on a placeholder).

## Still TODO (later, not done yet)

- **ngrok tunnel** to expose port 8731 to TradingView (deferred per user).
  Planned as a second user service (`ngrok.service`) once an authtoken is set.
- **TradingView alert**: SPX, "once per bar close", Webhook URL = the ngrok URL,
  message body `{"price": {{close}}}`.
- **More history**: re-export 5-min SPX with more bars loaded; replace
  `data/spx_history.csv` and `systemctl --user restart levelprobs`.
