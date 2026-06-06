"""Terminal report with red/green highlighting.

Color convention (kept dead simple, per request):
  GREEN = upside / buy-side context, RED = downside / sell-side context.
The headline BUY/SELL lean comes from the first-break directional bias; the
per-level coloring comes from whether the level sits above (green) or below
(red) current price. A short legend prints so the colors aren't mistaken for
a guaranteed signal.
"""
import os

_USE_COLOR = os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"
G = "\033[92m" if _USE_COLOR else ""
R = "\033[91m" if _USE_COLOR else ""
Y = "\033[93m" if _USE_COLOR else ""
DIM = "\033[2m" if _USE_COLOR else ""
B = "\033[1m" if _USE_COLOR else ""
X = "\033[0m" if _USE_COLOR else ""


def _pct(p: float) -> str:
    return f"{p * 100:5.1f}%"


def _prob_color(p: float, above: bool) -> str:
    base = G if above else R
    return f"{B}{base}" if p >= 0.80 else base


def _bar(prob: float, width: int = 10) -> str:
    filled = int(round(prob * width))
    return "█" * filled + "░" * (width - filled)


def render(symbol: str, n_sessions: int, synthetic: bool, price: float,
           time_label: str, bar_index: int, bars_per_rth: int, cur_atr: float,
           bias: dict, ladder: list, order_blocks: list) -> str:
    """ladder: rungs {price, prob, above, tags} sorted high->low (auto-scan).
    order_blocks: list of dicts {kind, low, high, prob, mid}."""
    L = []
    src = "synthetic" if synthetic else "real"
    L.append(f"{B}LEVELPROBS — {symbol}{X}  {DIM}({src}, {n_sessions} sessions){X}")
    remaining = 100 * (bars_per_rth - bar_index) / bars_per_rth
    L.append(f"  price {B}{price:.2f}{X}   time {time_label} ET "
             f"(bar {bar_index}/{bars_per_rth}, {remaining:.0f}% of session left)"
             f"   14d ATR {cur_atr:.1f} pts")
    L.append("")

    # ---- directional bias ----
    bh, bl = bias["broke_high"], bias["broke_low"]
    lean_buy = bh >= bl
    lean_col, lean_word = (G, "BUY / LONG") if lean_buy else (R, "SELL / SHORT")
    edge = abs(bh - bl) * 100
    strength = "strong" if edge >= 12 else "slight" if edge >= 4 else "coin-flip"
    L.append(f"{B}DIRECTIONAL BIAS{X} {DIM}(last {bias['n']} sessions, recency-weighted){X}")
    L.append(f"  {G}Broke High First {_pct(bh)}{X}     {R}Broke Low First {_pct(bl)}{X}"
             f"     {DIM}Neither {_pct(bias['neither'])}{X}")
    L.append(f"  avg up {G}{bias['avg_up']:.1f}{X} / avg dn {R}{bias['avg_dn']:.1f}{X} pts"
             f"     >> lean {B}{lean_col}{lean_word}{X} ({strength})")
    L.append("")

    # ---- auto-scan ladder: P(touch) for every number ----
    L.append(f"{B}PRICE LADDER{X} {DIM}(auto-scan: P(touch) for every number before close){X}")
    inserted = False
    for r in ladder:
        # drop the current-price marker once we cross from above to below
        if not inserted and not r["above"]:
            L.append(f"  {B}{Y}>>>> {price:>9.2f}  ── CURRENT ── {time_label} ET{X}")
            inserted = True
        col = _prob_color(r["prob"], r["above"])
        dist = r["price"] - price
        sign = "+" if dist >= 0 else "-"
        tags = f"  {DIM}{', '.join(r['tags'])}{X}" if r["tags"] else ""
        L.append(f"  {col}{r['price']:>9.2f}  {_bar(r['prob'])} {_pct(r['prob'])}{X}"
                 f"  {DIM}{sign}{abs(dist):.0f}p{X}{tags}")
    if not inserted:   # price below the entire ladder
        L.append(f"  {B}{Y}>>>> {price:>9.2f}  ── CURRENT ── {time_label} ET{X}")
    L.append("")

    # ---- order blocks ----
    if order_blocks:
        L.append(f"{B}ORDER BLOCKS{X} {DIM}(unmitigated; price tends to return){X}")
        for ob in order_blocks:
            col = G if ob["kind"] == "bull" else R
            tag = "Bull OB (support)" if ob["kind"] == "bull" else "Bear OB (resist)"
            L.append(f"  {col}{tag:<18}{X} {ob['low']:.2f}–{ob['high']:.2f}"
                     f"   mid {ob['mid']:.2f}   P(return) {col}{_pct(ob['prob'])}{X}")
        L.append("")

    L.append(f"{DIM}legend: {G}green = upside / buy-side{X}{DIM}, "
             f"{R}red = downside / sell-side{X}{DIM}. bold = P>=80%. "
             f"estimates are historical frequencies, not guarantees.{X}")
    return "\n".join(L)
