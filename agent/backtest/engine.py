"""Orchestrates the full backtest: real historical underlying prices (Alpaca
Market Data API) -> ATR-derived risk parameters (fixed before any strategy
runs) -> day-by-day simulation of all five strategies via the generic
simulator -> the statistical validation gate -> lifecycle promotion and a
graveyard write-up for every result, pass or fail.

Anything that PASSes the initial backtest is automatically retested on a
much longer lookback window before it's trusted at all — a result that only
survives on a short window is exactly the overfitting pattern this gate
exists to catch.
"""
import json
import math
import os
from datetime import datetime, timedelta

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import Adjustment

from agent.config import CONFIG
from agent.options_pricing import realized_vol
from agent.strategies import cash_secured_put, covered_call, long_directional, vertical_credit_spread
from agent.strategies.lifecycle import StrategyAdapter, StrategyRegistry
from agent.backtest.iron_condor import price_iron_condor
from agent.backtest.atr import Bar, derive_risk_parameters
from agent.backtest.costs import DEFAULT_COST_MODEL
from agent.backtest.simulator import simulate_trade
from agent.backtest.metrics import validate_strategy_result, validate_sub_period_stability
from agent.backtest.graveyard import record_result, record_note

HOLD_DAYS = 21          # ~30 calendar days, one monthly options cycle, in trading days
STEP_DAYS = 7           # slide the window forward this many trading days between simulated trades
T_YEARS = 30 / 365
LOOKBACK_DAYS = 900     # initial backtest window (~3y of trading days)
EXTENDED_LOOKBACK_DAYS = 2200  # retest window for anything that passes on the initial window (~6y)
MIN_TRADES = 30
ATR_WINDOW = 14
STOP_LOSS_ATR_MULTIPLE = 1.5
BACKTEST_ASSUMED_EQUITY = 100_000  # matches the required fresh-account starting balance
RISK_PCT_PER_TRADE = 0.02

STRATEGY_NAMES = (
    "cash_secured_put", "covered_call", "long_directional", "vertical_credit_spread", "iron_condor",
    "iron_condor_vrp_45_21", "vertical_credit_spread_2d",
)

# Per-strategy entry/exit timing. hold_days/t_years default to the module-level HOLD_DAYS/T_YEARS
# (one ~30-day cycle, held to expiration). `iron_condor_vrp_45_21` is the "enter 45 DTE, manage/
# exit at 21 DTE" variant: priced with a full 45-day time value at entry, force-closed at
# mark-to-market after 24 days (45-21) rather than held to expiration, so decay is captured while
# gamma/tail risk in the last 3 weeks is avoided — the classic volatility-selling risk premium
# structure, distinct from just running the same iron_condor logic on a longer clock. It also
# uses a credit-multiple stop instead of the ATR-underlying-distance stop every other strategy
# gets: that stop is tuned for directional/single-leg structures and is far too tight for a
# longer-dated, higher-vega credit structure (verified — it forced ~93% of trades to stop out
# regardless of whether the position was actually threatened). `vol_window` is the trailing
# realized-vol estimation window used to price the position — matched to the 45-day hold (not
# the default 20 days used elsewhere) so the vol input has a fighting chance of covering what
# actually materializes over the life of the trade, rather than a stale 20-day snapshot going
# stale partway through a 45-day hold.
# `vertical_credit_spread_2d` is the structure this run actually intends to trade: a
# defined-risk bull put spread entered 2-3 days from expiry, which is the only horizon that
# both closes inside the judged window and matches the 1-4 DTE contracts the chain offers.
# Every other profile here validates a hold the live agent cannot perform before the
# deadline, which makes their numbers evidence about methodology rather than about this week.
#
# Its step_days (7) exceeds its hold_days (2), so consecutive trades share no part of any
# price path and the trade sample really is independent -- the overlap that forced the
# moving-block bootstrap elsewhere is absent here by construction, not by correction, so
# block_size stays 1 and the CI needs no widening. That is a property of the schedule, and
# worth keeping if the profile is ever retuned.
#
# It uses the credit-multiple stop rather than the ATR underlying-distance stop for the same
# reason iron_condor_vrp_45_21 does, but more acutely: 1.5x ATR on a broad-market ETF is a
# ~2% move, which a 2-day hold essentially never reaches, so the ATR stop would be inert
# rather than protective and it would be dishonest to describe the position as stopped.
STRATEGY_TIMING = {
    "vertical_credit_spread_2d": {
        "hold_days": 2, "t_years": 3 / 365, "step_days": 7, "force_exit_offset": None,
        "use_underlying_stop": False, "stop_loss_credit_multiple": 2.0, "vol_window": 20,
    },
    "iron_condor_vrp_45_21": {
        "hold_days": 45, "t_years": 45 / 365, "step_days": STEP_DAYS, "force_exit_offset": 45 - 21,
        "use_underlying_stop": False, "stop_loss_credit_multiple": 2.0, "vol_window": 45,
    },
}


def _timing_for(strategy_name: str) -> dict:
    return STRATEGY_TIMING.get(strategy_name, {
        "hold_days": HOLD_DAYS, "t_years": T_YEARS, "step_days": STEP_DAYS, "force_exit_offset": None,
        "use_underlying_stop": True, "stop_loss_credit_multiple": None, "vol_window": 20,
    })


def _block_size_for(strategy_name: str) -> int:
    """Bootstrap block length: how many consecutive trades share a holding window.

    hold/step rounded up. When the entry step is at least as long as the hold there is no
    overlap and this is 1, which is the plain i.i.d. bootstrap.
    """
    timing = _timing_for(strategy_name)
    return max(1, math.ceil(timing["hold_days"] / timing["step_days"]))


def _build_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    for name in STRATEGY_NAMES:
        registry.register(StrategyAdapter(name=name, build_legs_fn=None))
    return registry


def fetch_bars(client: StockHistoricalDataClient, symbol: str, lookback_days: int):
    """Returns (closes, atr_bars) — closes for pricing/vol, full OHLC Bars for ATR.

    Requests split-adjusted prices explicitly: raw (unadjusted) prices contain a
    discontinuity on every stock-split date (e.g. NVDA's 10-for-1 split in June 2024
    shows up as a fake ~90% single-day crash), which would corrupt every simulated
    trade window straddling that date with a bogus settlement price. Dividend
    adjustment is deliberately left off — it retroactively alters historical closes
    in a way that doesn't match what was actually quoted at the time; splits are the
    one adjustment that's about price *continuity*, not economics.
    """
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=datetime.utcnow() - timedelta(days=lookback_days),
        adjustment=Adjustment.SPLIT,
    )
    df = client.get_stock_bars(req).df
    if df.empty:
        return [], []
    sub = df.xs(symbol, level=0) if hasattr(df.index, "levels") else df
    closes = sub["close"].tolist()
    atr_bars = [Bar(h, l, c) for h, l, c in zip(sub["high"].tolist(), sub["low"].tolist(), closes)]
    return closes, atr_bars


def _build_legs(strategy_name: str, S0: float, sigma: float, momentum: float, t_years: float):
    """Returns (legs, entry_credit, max_loss_dollars) for one strategy at one entry point."""
    if strategy_name == "cash_secured_put":
        plan = cash_secured_put(S0, t_years, sigma)
        return plan.legs, plan.net_credit, plan.max_loss_per_contract
    if strategy_name == "covered_call":
        plan = covered_call(S0, t_years, sigma)
        return plan.legs, plan.net_credit, plan.max_loss_per_contract
    if strategy_name == "long_directional":
        plan = long_directional(S0, t_years, sigma, momentum)
        return plan.legs, plan.net_credit, plan.max_loss_per_contract
    if strategy_name in ("vertical_credit_spread", "vertical_credit_spread_2d"):
        plan = vertical_credit_spread(S0, t_years, sigma)
        return plan.legs, plan.net_credit, plan.max_loss_per_contract
    if strategy_name in ("iron_condor", "iron_condor_vrp_45_21"):
        ic = price_iron_condor(S0, t_years, sigma)
        return ic.legs, ic.net_credit, ic.max_loss
    raise ValueError(f"unknown strategy {strategy_name}")


def simulate_strategy(strategy_name: str, closes: list, symbol: str, stop_loss_underlying_move: float,
                       cost_model=DEFAULT_COST_MODEL) -> list:
    timing = _timing_for(strategy_name)
    hold_days, t_years, force_exit_offset = timing["hold_days"], timing["t_years"], timing["force_exit_offset"]
    vol_window, step_days = timing["vol_window"], timing["step_days"]
    trades = []
    n = len(closes)
    i = vol_window  # need at least vol_window days of trailing history for the vol estimate
    while i + hold_days < n:
        S0 = closes[i]
        sigma = realized_vol(closes[: i + 1], window=vol_window)
        momentum = closes[i] - closes[i - 10] if i >= 10 else 0.0

        legs, entry_credit, max_loss = _build_legs(strategy_name, S0, sigma, momentum, t_years)
        trade = simulate_trade(
            closes, i, hold_days, legs, entry_credit, max_loss, sigma, cost_model,
            symbol=symbol, strategy=strategy_name,
            stop_loss_underlying_move=stop_loss_underlying_move if timing["use_underlying_stop"] else None,
            stop_loss_credit_multiple=timing["stop_loss_credit_multiple"],
            force_exit_offset=force_exit_offset,
        )
        trades.append(trade)
        i += step_days

    return trades


def _validate_symbol_strategy(strategy_name: str, closes: list, symbol: str, stop_move: float) -> dict:
    trades = simulate_strategy(strategy_name, closes, symbol, stop_move)
    validation = validate_strategy_result(trades, min_trades=MIN_TRADES,
                                          block_size=_block_size_for(strategy_name))
    return {"validation": validation, "trades": len(trades), "trade_list": trades}


def run_backtest(symbols=None) -> dict:
    symbols = symbols or list(CONFIG.watchlist)
    client = StockHistoricalDataClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key)
    report = {}

    record_note(
        "Bootstrap changed from i.i.d. resampling to a circular moving-block bootstrap, block "
        "length ceil(hold_days / step_days) per strategy. Measured on a zero-edge random walk, "
        "the i.i.d. gate passed 10.8% of samples against a 2.5% nominal rate; the block gate "
        "passes 2.5% (test_block_bootstrap.py).\n\n"
        "**Every entry above this line was computed with the i.i.d. bootstrap and is superseded.** "
        "They are kept because a superseded result is still a record of what was tried, but no "
        "PASS above this line may be quoted as validated.\n\n"
        f"Block length this run: {', '.join(f'{n}={_block_size_for(n)}' for n in STRATEGY_NAMES)}.\n\n"
        "Note that vertical_credit_spread_2d has block length 1 legitimately: its entry step (7 "
        "days) exceeds its hold (2 days), so its trades share no price path and are genuinely "
        "independent. That is a property of the schedule, not an exemption."
    )

    for symbol in symbols:
        try:
            closes, atr_bars = fetch_bars(client, symbol, LOOKBACK_DAYS)
            if len(closes) < 40:
                report[symbol] = {"error": "insufficient history"}
                continue

            risk_params = derive_risk_parameters(
                atr_bars, BACKTEST_ASSUMED_EQUITY, RISK_PCT_PER_TRADE, ATR_WINDOW, STOP_LOSS_ATR_MULTIPLE
            )

            registry = _build_registry()
            symbol_report = {"atr": risk_params.atr_value, "stop_loss_underlying_move": risk_params.stop_loss_price_move,
                              "strategies": {}}

            for strategy_name in STRATEGY_NAMES:
                initial = _validate_symbol_strategy(strategy_name, closes, symbol, risk_params.stop_loss_price_move)
                validation = initial["validation"]
                adapter = registry.get(strategy_name)
                adapter.promote_to_paper(validation)
                record_result(strategy_name, symbol, validation)

                extended_summary = None
                if validation.passed:
                    ext_closes, _ = fetch_bars(client, symbol, EXTENDED_LOOKBACK_DAYS)
                    if len(ext_closes) < 60:
                        # "Anything that PASSes the initial backtest is automatically retested on
                        # a much longer lookback window before it's trusted at all" (module
                        # docstring) -- but adapter.promote_to_paper() above already set
                        # enabled_for_paper=True from the initial window alone, and skipping this
                        # block used to leave it there un-demoted, silently promoting a strategy
                        # that was never actually retested (only reachable for a symbol with too
                        # little extended history, e.g. a very recent IPO -- not any current
                        # watchlist member, but a real gap for whatever the watchlist grows into).
                        adapter.demote(
                            f"passed on {LOOKBACK_DAYS}d window but extended history has only "
                            f"{len(ext_closes)} bars (<60) — cannot run the required "
                            f"{EXTENDED_LOOKBACK_DAYS}d retest, so this pass is not trusted without it"
                        )
                    if len(ext_closes) >= 60:
                        ext_result = _validate_symbol_strategy(
                            strategy_name, ext_closes, symbol, risk_params.stop_loss_price_move
                        )
                        ext_validation = ext_result["validation"]
                        record_result(f"{strategy_name} (extended history)", symbol, ext_validation)
                        if not ext_validation.passed:
                            adapter.demote(
                                f"passed on {LOOKBACK_DAYS}d window but failed the "
                                f"{EXTENDED_LOOKBACK_DAYS}d retest — likely overfit to the short window"
                            )

                        sub_period = None
                        if ext_validation.passed:
                            # Require BOTH halves of the extended window to individually clear
                            # validation — a combined-sample pass that's actually carried by one
                            # half of history is exactly the instability stress testing found in
                            # AMD long_directional (first half alone: Sharpe 0.99, doesn't clear).
                            sub_period = validate_sub_period_stability(
                                ext_result["trade_list"], min_trades_per_half=15,
                                block_size=_block_size_for(strategy_name))
                            record_result(f"{strategy_name} (sub-period stability)", symbol, sub_period.first_half,
                                          extra_notes=f"second half: passed={sub_period.second_half.passed}, "
                                                      f"sharpe={sub_period.second_half.metrics.get('sharpe')}")
                            if not sub_period.passed:
                                adapter.demote(
                                    f"passed the {EXTENDED_LOOKBACK_DAYS}d retest but failed sub-period "
                                    f"stability: {'; '.join(sub_period.reasons)}"
                                )

                        extended_summary = {
                            "passed": ext_validation.passed and (sub_period is None or sub_period.passed),
                            "trades": ext_result["trades"],
                            "metrics": ext_validation.metrics,
                            "reasons": ext_validation.reasons,
                            "sub_period_stability": None if sub_period is None else {
                                "passed": sub_period.passed,
                                "first_half": {"passed": sub_period.first_half.passed,
                                               "sharpe": sub_period.first_half.metrics.get("sharpe"),
                                               "mean_return_pct": sub_period.first_half.metrics.get("mean_return_pct")},
                                "second_half": {"passed": sub_period.second_half.passed,
                                                "sharpe": sub_period.second_half.metrics.get("sharpe"),
                                                "mean_return_pct": sub_period.second_half.metrics.get("mean_return_pct")},
                                "reasons": sub_period.reasons,
                            },
                        }

                symbol_report["strategies"][strategy_name] = {
                    "passed_backtest": validation.passed,
                    "passed_extended_retest": None if extended_summary is None else extended_summary["passed"],
                    "enabled_for_paper": adapter.stage.enabled_for_paper,
                    "trades": initial["trades"],
                    "metrics": validation.metrics,
                    "mean_return_ci": validation.mean_return_ci,
                    "sharpe_ci": validation.sharpe_ci,
                    "reasons": validation.reasons,
                    "extended_retest": extended_summary,
                }

            passed_strategies = [
                name for name, data in symbol_report["strategies"].items() if data["enabled_for_paper"]
            ]
            symbol_report["cleared_for_paper"] = passed_strategies
            best = max(
                symbol_report["strategies"].items(),
                key=lambda kv: kv[1]["metrics"].get("sharpe", float("-inf")),
            )
            symbol_report["best_by_sharpe"] = best[0]
            report[symbol] = symbol_report
        except Exception as exc:  # keep the run going even if one symbol fails
            report[symbol] = {"error": str(exc)}

    return report


def save_report(report: dict, path: str = None):
    path = path or os.path.join(CONFIG.logs_dir, "backtest_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)


if __name__ == "__main__":
    result = run_backtest()
    save_report(result)
    for sym, data in result.items():
        if "error" in data:
            print(f"{sym}: {data['error']}")
            continue
        print(f"\n{sym} -- cleared for paper: {data['cleared_for_paper'] or 'none'}")
        for name, s in data["strategies"].items():
            m = s["metrics"]
            status = "PASS" if s["enabled_for_paper"] else "FAIL"
            print(f"  [{status}] {name:24s} trades={s['trades']:3d}  win_rate={m.get('win_rate', 0):.0%}  "
                  f"sharpe={m.get('sharpe', 0):6.2f}  total_pnl=${m.get('total_pnl_dollars', 0):.0f}")
            if s["reasons"]:
                print(f"           reasons: {'; '.join(s['reasons'])}")
    print("\nSaved to logs/backtest_report.json; full pass/fail write-up in docs/strategy_graveyard.md")
