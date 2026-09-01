"""Writes up every backtest validation result — pass or fail — with real
numbers, so a falsified strategy/symbol combination is documented instead of
silently deleted and doesn't get re-tested from scratch by a future run.
"""
import os
from datetime import datetime, timezone

GRAVEYARD_PATH = os.path.join("docs", "strategy_graveyard.md")


def record_result(strategy_name: str, symbol: str, validation, extra_notes: str = "") -> None:
    os.makedirs(os.path.dirname(GRAVEYARD_PATH), exist_ok=True)
    write_header = not os.path.exists(GRAVEYARD_PATH)
    with open(GRAVEYARD_PATH, "a", encoding="utf-8") as f:
        if write_header:
            f.write(
                "# Strategy Graveyard\n\n"
                "Every backtest validation run for every strategy/symbol combination, "
                "pass or fail, with the real numbers behind the verdict. A FAIL here means "
                "don't re-test this combination on the same data expecting a different "
                "answer -- either the underlying, the strategy, or the market regime changed.\n\n"
            )
        status = "PASS" if validation.passed else "FAIL"
        f.write(f"## {strategy_name} / {symbol} -- {status} "
                f"({datetime.now(timezone.utc).date().isoformat()})\n\n")
        m = validation.metrics
        f.write(f"- trades: {m.get('trades')}\n")
        f.write(f"- win_rate: {m.get('win_rate')}\n")
        f.write(f"- profit_factor: {m.get('profit_factor')}\n")
        f.write(f"- sharpe: {m.get('sharpe')}\n")
        f.write(f"- mean_return_pct: {m.get('mean_return_pct')}\n")
        f.write(f"- total_pnl_dollars: {m.get('total_pnl_dollars')}\n")
        f.write(f"- max_drawdown_dollars: {m.get('max_drawdown_dollars')}\n")
        f.write(f"- exit_reason_breakdown: {m.get('exit_reason_breakdown')}\n")
        f.write(f"- mean-return 95% bootstrap CI: {tuple(round(x, 5) for x in validation.mean_return_ci)}\n")
        f.write(f"- sharpe 95% bootstrap CI: {tuple(round(x, 3) for x in validation.sharpe_ci)}\n")
        if not validation.passed:
            f.write(f"- rejection reasons: {'; '.join(validation.reasons)}\n")
        if extra_notes:
            f.write(f"- notes: {extra_notes}\n")
        f.write("\n")
