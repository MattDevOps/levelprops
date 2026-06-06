"""CLI:
  python -m levelprobs ES --time 10:25                 # one-shot report
  python -m levelprobs ES --watch                       # live alerts (synthetic demo)
  python -m levelprobs ES --watch --feed webhook        # live alerts from TradingView
"""
import argparse

from .api import analyze
from .model import bar_index_for
from datetime import time as _time


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
    # --- live watch mode ---
    ap.add_argument("--watch", action="store_true", help="run the live alert loop")
    ap.add_argument("--feed", choices=["synthetic", "webhook"], default="synthetic",
                    help="data source for --watch")
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

    if not args.watch:
        if args.history_csv:
            # Real-data path: load bars + TRUST Pine's exported level columns.
            from .loaders import load_sessions_from_csv
            from .pine import levels_from_csv
            sess = load_sessions_from_csv(args.history_csv)
            named = levels_from_csv(args.history_csv)
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
    if args.feed == "webhook":
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
