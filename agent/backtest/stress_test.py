"""Stress tests for a strategy that already passed the standard validation gate:
does the edge survive parameter perturbation, a chronological sub-period split,
and higher transaction costs — or is it concentrated in a lucky sample or a
specific parameter choice that happened to look good? A strategy that only
passes at exactly the parameters someone tuned it at is a strong overfitting
signal, distinct from (and a useful complement to) the extended-history retest
and sub-period stability check already run by run_backtest.py.

Works for any of the delta-targeted strategies (cash_secured_put, covered_call,
long_directional, vertical_credit_spread) — iron condors aren't included since
they're delta-targeted on two independent legs, not one `target_delta`.
"""
import json
import os

from alpaca.data.historical import StockHistoricalDataClient

from agent.config import CONFIG
from agent.options_pricing import realized_vol
from agent.strategies import cash_secured_put, covered_call, long_directional, vertical_credit_spread
from agent.backtest.costs import CostModel, DEFAULT_COST_MODEL
from agent.backtest.simulator import simulate_trade
from agent.backtest.metrics import validate_strategy_result
from agent.backtest.atr import derive_risk_parameters
from agent.backtest.engine import fetch_bars, HOLD_DAYS, STEP_DAYS, T_YEARS, EXTENDED_LOOKBACK_DAYS

# Each strategy's own default target_delta, used as the sensitivity sweep's center point.
_DEFAULT_DELTA = {
    "cash_secured_put": -0.30,
    "covered_call": 0.30,
    "long_directional": 0.40,
    "vertical_credit_spread": -0.30,
}


def _build_plan(strategy_name, S0, sigma, momentum, target_delta):
    if strategy_name == "cash_secured_put":
        return cash_secured_put(S0, T_YEARS, sigma, target_delta=target_delta)
    if strategy_name == "covered_call":
        return covered_call(S0, T_YEARS, sigma, target_delta=target_delta)
    if strategy_name == "long_directional":
        return long_directional(S0, T_YEARS, sigma, momentum, target_delta=target_delta)
    if strategy_name == "vertical_credit_spread":
        return vertical_credit_spread(S0, T_YEARS, sigma, short_delta=target_delta)
    raise ValueError(f"stress_test doesn't support {strategy_name}")


def _simulate(closes, symbol, strategy_name, target_delta, vol_window, cost_model, stop_loss_underlying_move):
    trades = []
    n = len(closes)
    i = vol_window
    while i + HOLD_DAYS < n:
        S0 = closes[i]
        sigma = realized_vol(closes[: i + 1], window=vol_window)
        momentum = closes[i] - closes[i - 10] if i >= 10 else 0.0
        plan = _build_plan(strategy_name, S0, sigma, momentum, target_delta)
        trade = simulate_trade(
            closes, i, HOLD_DAYS, plan.legs, plan.net_credit, plan.max_loss_per_contract,
            sigma, cost_model, symbol=symbol, strategy=f"{strategy_name}_stress",
            stop_loss_underlying_move=stop_loss_underlying_move,
        )
        trades.append(trade)
        i += STEP_DAYS
    return trades


def _worst_case(trades) -> dict:
    pnls = [t.pnl_dollars for t in trades]
    if not pnls:
        return {"max_consecutive_losses": 0, "max_single_trade_loss": 0, "max_drawdown_dollars": 0, "trades": 0}
    streak = max_streak = 0
    for p in pnls:
        streak = streak + 1 if p < 0 else 0
        max_streak = max(max_streak, streak)
    cum = peak = max_dd = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)
    return {
        "max_consecutive_losses": max_streak,
        "max_single_trade_loss": round(min(pnls), 2),
        "max_drawdown_dollars": round(max_dd, 2),
        "trades": len(pnls),
    }


def _summarize(validation) -> dict:
    return {
        "passed": validation.passed,
        "trades": validation.metrics["trades"],
        "sharpe": validation.metrics["sharpe"],
        "mean_return_pct": validation.metrics["mean_return_pct"],
        "win_rate": validation.metrics["win_rate"],
        "reasons": validation.reasons,
    }


def run(symbol: str, strategy_name: str) -> dict:
    base_delta = _DEFAULT_DELTA[strategy_name]
    client = StockHistoricalDataClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key)
    closes, atr_bars = fetch_bars(client, symbol, EXTENDED_LOOKBACK_DAYS)
    risk_params = derive_risk_parameters(atr_bars, 100_000, 0.02, 14, 1.5)
    stop_move = risk_params.stop_loss_price_move

    report = {"symbol": symbol, "strategy": strategy_name, "lookback_days": EXTENDED_LOOKBACK_DAYS,
              "base_delta": base_delta}

    baseline_trades = _simulate(closes, symbol, strategy_name, base_delta, 20, DEFAULT_COST_MODEL, stop_move)
    report["baseline"] = _summarize(validate_strategy_result(baseline_trades, min_trades=30))
    report["worst_case"] = _worst_case(baseline_trades)

    mid = len(baseline_trades) // 2
    report["first_half"] = _summarize(validate_strategy_result(baseline_trades[:mid], min_trades=15))
    report["second_half"] = _summarize(validate_strategy_result(baseline_trades[mid:], min_trades=15))

    report["delta_sensitivity"] = {}
    sign = 1 if base_delta > 0 else -1
    for offset in (-0.10, -0.05, 0.05, 0.10):
        td = round(base_delta + sign * offset, 2)
        trades = _simulate(closes, symbol, strategy_name, td, 20, DEFAULT_COST_MODEL, stop_move)
        report["delta_sensitivity"][str(td)] = _summarize(validate_strategy_result(trades, min_trades=30))

    report["vol_window_sensitivity"] = {}
    for vw in (10, 15, 30, 40):
        trades = _simulate(closes, symbol, strategy_name, base_delta, vw, DEFAULT_COST_MODEL, stop_move)
        report["vol_window_sensitivity"][str(vw)] = _summarize(validate_strategy_result(trades, min_trades=30))

    report["cost_stress"] = {}
    for mult in (2, 3):
        stressed = CostModel(half_spread_bps=DEFAULT_COST_MODEL.half_spread_bps * mult,
                              flat_hurdle_pct=DEFAULT_COST_MODEL.flat_hurdle_pct * mult)
        trades = _simulate(closes, symbol, strategy_name, base_delta, 20, stressed, stop_move)
        report["cost_stress"][f"{mult}x"] = _summarize(validate_strategy_result(trades, min_trades=30))

    return report


def save_report(report: dict, path: str = None):
    path = path or os.path.join(
        CONFIG.logs_dir, f"stress_test_{report['symbol']}_{report['strategy']}.json")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return path


def _print_report(result: dict):
    b = result["baseline"]
    print(f"BASELINE ({result['symbol']}, {result['strategy']}, delta={result['base_delta']}, vol_window=20): "
          f"{'PASS' if b['passed'] else 'FAIL'} — trades={b['trades']} sharpe={b['sharpe']} "
          f"mean_return={b['mean_return_pct']:.2%} win_rate={b['win_rate']:.0%}")
    wc = result["worst_case"]
    print(f"  worst case: max consecutive losses={wc['max_consecutive_losses']}, "
          f"max single-trade loss=${wc['max_single_trade_loss']:.0f}, "
          f"max drawdown=${wc['max_drawdown_dollars']:.0f}")

    print("\nSUB-PERIOD SPLIT:")
    for half in ("first_half", "second_half"):
        h = result[half]
        print(f"  {half}: {'PASS' if h['passed'] else 'FAIL'} trades={h['trades']} sharpe={h['sharpe']} "
              f"mean_return={h['mean_return_pct']:.2%}")

    print(f"\nDELTA SENSITIVITY (baseline={result['base_delta']}):")
    for td, s in result["delta_sensitivity"].items():
        print(f"  delta={td}: {'PASS' if s['passed'] else 'FAIL'} sharpe={s['sharpe']} "
              f"mean_return={s['mean_return_pct']:.2%}")

    print("\nVOL-WINDOW SENSITIVITY (baseline=20):")
    for vw, s in result["vol_window_sensitivity"].items():
        print(f"  window={vw}: {'PASS' if s['passed'] else 'FAIL'} sharpe={s['sharpe']} "
              f"mean_return={s['mean_return_pct']:.2%}")

    print("\nCOST STRESS:")
    for mult, s in result["cost_stress"].items():
        print(f"  {mult} friction: {'PASS' if s['passed'] else 'FAIL'} sharpe={s['sharpe']} "
              f"mean_return={s['mean_return_pct']:.2%}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    symbol = sys.argv[1] if len(sys.argv) > 1 else "GOOGL"
    strategy = sys.argv[2] if len(sys.argv) > 2 else "cash_secured_put"
    result = run(symbol, strategy)
    path = save_report(result)
    _print_report(result)
    print(f"\nSaved to {path}")
