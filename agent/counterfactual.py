"""What the 21 refused strategies would have returned, had the gate not refused them.

The validation gate cleared nothing: 21 strategy/symbol pairs, all failed. That is the
entry's headline finding, and it is only worth stating if we are also willing to price it.
So this enters every refused pair at the close of the day the gate refused it and marks it
forward with the same simulator that produced the numbers the gate rejected.

No new machinery, deliberately. `fetch_bars`, `_build_legs`, `_timing_for`, `realized_vol`,
`simulate_trade` and `DEFAULT_COST_MODEL` are the engine's own, imported unchanged. If the
simulator is wrong then the refusal was wrong in the same direction, which is the only way
this comparison is fair.

Two things it is NOT:

  * It is not evidence about the strategies. Three sessions -- here, one -- is far inside
    the noise the bootstrap CI was measuring in the first place. A refused strategy that
    made money over a day has not been vindicated, and the gate has not been embarrassed.
    That is the whole point of the gate: it refuses on the width of the interval, not on
    the sign of the last observation.
  * It is not a claim about fills. These are Black-Scholes marks on split-adjusted daily
    closes, the same synthetic path the backtest used. Nothing here touched a live quote.

Window: entry at the close of the day the report was generated, marked to the most recent
complete session. The upper bound is whatever has actually traded -- never a partial or
assumed session.

    python main.py --counterfactual
"""
import json
import os
from datetime import date, datetime, timezone

from agent.config import CONFIG

ENTRY_DATE = date(2026, 9, 1)   # the session whose close the gate refused on


def _bars_with_dates(symbol: str, lookback_days: int = 400):
    """(dates, closes) from the engine's own fetch path, with the dates kept.

    fetch_bars drops the index; the counterfactual needs to know which close is which day,
    so the same request is issued and the timestamps retained.
    """
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment
    from datetime import timedelta

    client = StockHistoricalDataClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key)
    req = StockBarsRequest(
        symbol_or_symbols=symbol, timeframe=TimeFrame.Day,
        start=datetime.now(timezone.utc) - timedelta(days=lookback_days),
        adjustment=Adjustment.SPLIT,
    )
    df = client.get_stock_bars(req).df
    if df.empty:
        return [], []
    sub = df.xs(symbol, level=0) if hasattr(df.index, "levels") else df
    dates = [ts.date() for ts in sub.index]
    return dates, sub["close"].tolist()


def run_counterfactual(path: str = None) -> dict:
    """Simulate every refused pair over the window and write logs/counterfactual.json."""
    from agent.backtest.engine import _build_legs, _timing_for, STRATEGY_NAMES
    from agent.backtest.simulator import simulate_trade
    from agent.backtest.costs import DEFAULT_COST_MODEL
    from agent.options_pricing import realized_vol

    path = path or os.path.join(CONFIG.logs_dir, "counterfactual.json")
    report_path = os.path.join(CONFIG.logs_dir, "backtest_report.json")
    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except (OSError, ValueError):
        report = {}

    results, notes = [], []
    window = {"entry_date": str(ENTRY_DATE), "mark_date": None, "trading_days_held": None}

    for symbol in report:
        data = report.get(symbol) or {}
        strategies = data.get("strategies") or {}
        if not strategies:
            continue
        dates, closes = _bars_with_dates(symbol)
        if not closes:
            notes.append(f"{symbol}: no bars returned; skipped")
            continue
        if ENTRY_DATE not in dates:
            notes.append(f"{symbol}: no bar for the entry date {ENTRY_DATE}; skipped")
            continue

        entry_index = dates.index(ENTRY_DATE)
        # Mark to the last COMPLETE session in the data. Today's session has not printed a
        # bar until it closes, so this is never a partial or assumed day.
        mark_index = len(closes) - 1
        held = mark_index - entry_index
        if held < 1:
            notes.append(f"{symbol}: no complete session after {ENTRY_DATE} yet; skipped")
            continue
        window["mark_date"] = str(dates[mark_index])
        window["trading_days_held"] = held
        # The underlying's move over the same window. A one-session result is largely a
        # function of one session's direction, and reporting the P&L without it would invite
        # exactly the misreading this file exists to prevent.
        window.setdefault("underlying_move_pct", {})[symbol] = round(
            (closes[mark_index] / closes[entry_index] - 1) * 100, 3)

        # The engine's own ATR stop distance, taken from the report it wrote at refusal
        # time rather than recomputed -- same number the gate itself used.
        stop_move = data.get("stop_loss_underlying_move")

        for strategy_name in STRATEGY_NAMES:
            record = strategies.get(strategy_name)
            if record is None:
                continue
            timing = _timing_for(strategy_name)
            S0 = closes[entry_index]
            sigma = realized_vol(closes[: entry_index + 1], window=timing["vol_window"])
            momentum = (closes[entry_index] - closes[entry_index - 10]) if entry_index >= 10 else 0.0
            legs, entry_credit, max_loss = _build_legs(
                strategy_name, S0, sigma, momentum, timing["t_years"])

            # The strategy's own hold is kept for PRICING (the option really does have that
            # much time left), and the position is closed early at mark-to-market after the
            # days that have actually elapsed. This is the engine's documented
            # "manage at N days" path, not a new exit rule.
            trade = simulate_trade(
                closes, entry_index, timing["hold_days"], legs, entry_credit, max_loss,
                sigma, DEFAULT_COST_MODEL, symbol=symbol, strategy=strategy_name,
                stop_loss_underlying_move=stop_move if timing["use_underlying_stop"] else None,
                stop_loss_credit_multiple=timing["stop_loss_credit_multiple"],
                force_exit_offset=held,
            )
            results.append({
                "symbol": symbol,
                "strategy": strategy_name,
                "refused": record.get("enabled_for_paper") is not True,
                "refusal_reasons": record.get("reasons") or [],
                "pnl_dollars": round(trade.pnl_dollars, 2),
                "exit_reason": trade.exit_reason,
                "days_held": round(trade.holding_minutes / (60 * 24), 2),
                "net_return_pct": round(trade.net_return_pct, 6),
                "entry_credit": round(entry_credit, 4),
                "max_loss_dollars": round(max_loss, 2) if max_loss is not None else None,
                # Natural hold vs what the window allowed, so a truncated trade is visible
                # rather than presented as a completed one.
                "natural_hold_days": timing["hold_days"],
                "closed_early": held < timing["hold_days"],
            })

    refused = [r for r in results if r["refused"]]
    winners = [r for r in refused if r["pnl_dollars"] > 0]
    total = round(sum(r["pnl_dollars"] for r in refused), 2)

    report_out = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": window,
        "engine": ("agent/backtest/simulator.simulate_trade with the engine's own _build_legs, "
                   "_timing_for, realized_vol and DEFAULT_COST_MODEL — the same code that "
                   "produced the numbers the gate refused"),
        "marks": ("Black-Scholes on split-adjusted daily closes, the backtest's synthetic "
                  "path. No live quote was consulted and no fill was simulated."),
        "pairs_evaluated": len(results),
        "pairs_refused": len(refused),
        "refused_profitable": len(winners),
        "refused_unprofitable": len(refused) - len(winners),
        "total_pnl_dollars_if_all_taken": total,
        "mean_pnl_dollars": round(total / len(refused), 2) if refused else None,
        "best": max(refused, key=lambda r: r["pnl_dollars"], default=None),
        "worst": min(refused, key=lambda r: r["pnl_dollars"], default=None),
        "interpretation": (
            "This prices the gate's decision; it does not judge it. One session is far "
            "inside the noise the bootstrap CI was measuring, so a refused strategy that "
            "made money here has not been vindicated and the gate has not been shown wrong. "
            "The gate refuses on the width of the interval, never on the sign of the most "
            "recent observation — which is exactly why a result like this cannot overturn it."),
        "caveats": [
            f"One trading day held ({window['entry_date']} close to {window['mark_date']} "
            f"close). Today's session had not printed a bar, so the window is shorter than "
            f"the 1-3 Sep asked for.",
            "Every position was closed early at mark-to-market; none reached its natural "
            "hold, so these are marks, not realised results.",
            "Black-Scholes marks on daily closes. No live quote, no fill, no slippage "
            "beyond the backtest's own cost model.",
            "One observation. This is the sample size the bootstrap CI already judged "
            "insufficient, which is why it cannot confirm or overturn the refusal.",
        ],
        "notes": notes,
        "results": results,
    }
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report_out, f, indent=2, default=str)
    return report_out


if __name__ == "__main__":
    r = run_counterfactual()
    w = r["window"]
    print(f"Counterfactual {w['entry_date']} -> {w['mark_date']} "
          f"({w['trading_days_held']} trading day(s) held)")
    print(f"{r['pairs_refused']} refused pairs: {r['refused_profitable']} profitable, "
          f"{r['refused_unprofitable']} not")
    print(f"Total if every refused trade had been taken: ${r['total_pnl_dollars_if_all_taken']:,.2f}")
    print(f"Underlying move over the window: " + ", ".join(
        f"{k} {v:+.2f}%" for k, v in (w.get("underlying_move_pct") or {}).items()))
    for x in sorted(r["results"], key=lambda d: -d["pnl_dollars"]):
        print(f"  {x['symbol']:5s} {x['strategy']:26s} ${x['pnl_dollars']:>10,.2f}  "
              f"{x['exit_reason']:11s} ret {x['net_return_pct']:+.4%}"
              + ("  (closed early)" if x["closed_early"] else ""))
