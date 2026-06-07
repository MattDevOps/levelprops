"""CLI:
  python -m levelprobs ES --time 10:25                 # one-shot report
  python -m levelprobs ES --watch                       # live alerts (synthetic demo)
  python -m levelprobs ES --watch --feed webhook        # live alerts from TradingView
"""
import argparse

from .api import analyze
from .model import bar_index_for
from datetime import time as _time


def run_demo(args):
    """Live full-report dashboard. Sources (--feed):
      yahoo   (default): REAL & LIVE -- polls Yahoo Finance for ^GSPC 5-min bars
      replay           : stream a recorded TradingView CSV export bar-by-bar
      webhook          : truly live, fed by TradingView alerts (needs a tunnel)"""
    from .dashboard import run_dashboard
    sym = "SPX" if args.symbol.upper() == "ES" else args.symbol.upper()

    if args.feed == "yahoo":
        from .feeds import YahooPollFeed
        history = None
        if args.history_csv:
            from .loaders import load_sessions_from_csv
            history = load_sessions_from_csv(args.history_csv)
            print(f"[demo] yahoo: live price from ^GSPC; Pine level overlay read "
                  f"from {args.history_csv}\n"
                  f"       (levels are only current if that export is today's; "
                  f"otherwise they are stale).")
        feed = YahooPollFeed(sym, history=history)
        run_dashboard(feed, sym, csv_path=args.history_csv, halflife=args.halflife,
                      refresh_seconds=args.refresh or 15.0, min_prob=args.min_prob,
                      min_points=args.min_points, mode="YAHOO ^GSPC LIVE",
                      synthetic=False)
        return

    if args.feed == "webhook":
        from .feeds import TradingViewWebhookFeed
        history = None
        if args.history_csv:
            from .loaders import load_sessions_from_csv
            history = load_sessions_from_csv(args.history_csv)
        feed = TradingViewWebhookFeed(sym, port=args.port, history=history,
                                      sessions=args.sessions, seed=args.seed)
        run_dashboard(feed, sym, csv_path=args.history_csv, halflife=args.halflife,
                      refresh_seconds=args.refresh or 5.0, min_prob=args.min_prob,
                      min_points=args.min_points, mode="WEBHOOK LIVE",
                      synthetic=history is None)
        return

    # replay mode -- needs a recorded CSV to replay
    if not args.history_csv:
        print("[demo] replay needs --history-csv (recorded data to replay).\n"
              "       e.g. python -m levelprobs SPX --demo --feed replay "
              "--history-csv data/spx_history.csv\n"
              "       or just run live (default): python -m levelprobs SPX --demo")
        return
    from .feeds import CsvReplayFeed
    refresh = args.refresh if args.refresh is not None else 0.6
    while True:
        feed = CsvReplayFeed(args.history_csv, start_bar=0)
        run_dashboard(feed, sym, csv_path=args.history_csv, halflife=args.halflife,
                      refresh_seconds=refresh, min_prob=args.min_prob,
                      min_points=args.min_points, mode="CSV REPLAY", synthetic=False)
        if not args.repeat:
            break


def main():
    ap = argparse.ArgumentParser(
        prog="levelprobs",
        description="Recency-weighted intraday level-hit probabilities (ES/NQ/SPX).")
    ap.add_argument("symbol", nargs="?", default="ES", help="ES, NQ, or SPX")
    ap.add_argument("--sessions", type=int, default=1280,
                    help="synthetic sessions to generate (~1280 = 5 yrs)")
    ap.add_argument("--time", default="10:25", help="RTH time to evaluate (HH:MM)")
    ap.add_argument("--halflife", type=int, default=252,
                    help="recency half-life in sessions (default 252 = 1 yr)")
    ap.add_argument("--price", type=float, default=None, help="override current price")
    ap.add_argument("--target", type=float, action="append", default=None,
                    help="also spotlight a specific price level (repeatable)")
    ap.add_argument("--seed", type=int, default=7, help="synthetic RNG seed")
    # --- live dashboard / watch mode ---
    ap.add_argument("--demo", action="store_true",
                    help="live full-report dashboard (default feed: real Yahoo data)")
    ap.add_argument("--refresh", type=float, default=None,
                    help="dashboard redraw interval secs (default 15 yahoo / 0.6 replay)")
    ap.add_argument("--repeat", action="store_true",
                    help="loop the replay demo forever (Ctrl-C to stop)")
    ap.add_argument("--watch", action="store_true", help="run the live alert loop")
    ap.add_argument("--feed", choices=["yahoo", "synthetic", "replay", "webhook"],
                    default="yahoo",
                    help="data source for --demo / --watch (default: yahoo = real live)")
    ap.add_argument("--min-prob", type=float, default=0.80,
                    help="alert threshold probability (default 0.80)")
    ap.add_argument("--min-points", type=float, default=15.0,
                    help="min capturable move in points to bother alerting")
    ap.add_argument("--poll", type=float, default=15.0,
                    help="seconds between polls in --watch (0 = no wait)")
    ap.add_argument("--port", type=int, default=8731, help="webhook port")
    ap.add_argument("--history-csv", default=None,
                    help="real RTH 5-min CSV for the historical base (else synthetic)")
    args = ap.parse_args()

    if args.demo:
        run_demo(args)
        return

    if not args.watch:
        if args.history_csv:
            # Real-data path: load bars + TRUST Pine's exported level columns,
            # aligned to the bar being analyzed (not end-of-day).
            from .loaders import load_sessions_from_csv
            from .pine import levels_at
            sess = load_sessions_from_csv(args.history_csv)
            named = levels_at(args.history_csv, sess[-1].day,
                              _time.fromisoformat(args.time))
            print(analyze(args.symbol, at_time=args.time, halflife=args.halflife,
                          price=args.price, targets=args.target,
                          history=sess[:-1], today=sess[-1], named_override=named))
            return
        print(analyze(args.symbol, sessions=args.sessions, at_time=args.time,
                      halflife=args.halflife, price=args.price, targets=args.target,
                      seed=args.seed))
        return

    from .watch import watch, ALERT_SYMBOL
    if args.symbol.upper() != ALERT_SYMBOL:
        print(f"[note] alerts are {ALERT_SYMBOL}-only; ignoring symbol "
              f"{args.symbol!r} for --watch")
    sym = ALERT_SYMBOL
    history = None
    if args.history_csv:
        from .loaders import load_sessions_from_csv
        history = load_sessions_from_csv(args.history_csv)
        print(f"[history] loaded {len(history)} real sessions from {args.history_csv}")
    if args.feed == "yahoo":
        from .feeds import YahooPollFeed
        feed = YahooPollFeed(sym, history=history)
    elif args.feed == "webhook":
        from .feeds import TradingViewWebhookFeed
        feed = TradingViewWebhookFeed(sym, port=args.port, history=history,
                                      sessions=args.sessions, seed=args.seed)
    else:
        from .feeds import SyntheticReplayFeed
        start = bar_index_for(_time.fromisoformat(args.time))
        feed = SyntheticReplayFeed(sym, start_bar=start,
                                   sessions=args.sessions, seed=args.seed)
    watch(feed, sym, min_prob=args.min_prob, min_points=args.min_points,
          halflife=args.halflife, poll_seconds=args.poll)


if __name__ == "__main__":
    main()
