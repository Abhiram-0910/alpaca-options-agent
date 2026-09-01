"""Trade-level metrics, bootstrap confidence intervals, and the pass/fail
validation gate a strategy must clear before it is trusted with paper or
live capital.

Nothing here tunes itself to the data it's evaluating — `validate_strategy_result`
is a fixed bar (minimum sample size + bootstrap CI excluding zero on the
upside for both mean return and Sharpe) applied identically to every
strategy/symbol combination.
"""
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TradeRecord:
    net_return_pct: float      # pnl / capital-at-risk for this trade, as a fraction
    pnl_dollars: float
    exit_reason: str           # "expiration" | "stop_loss" | "profit_target"
    holding_minutes: float
    symbol: Optional[str] = None
    strategy: Optional[str] = None
    entry_index: Optional[int] = None


def compute_metrics(trades: list) -> dict:
    if not trades:
        return {"trades": 0, "win_rate": 0.0, "profit_factor": None, "sharpe": 0.0,
                "mean_return_pct": 0.0, "total_net_return_pct": 0.0, "total_pnl_dollars": 0.0,
                "max_drawdown_dollars": 0.0, "exit_reason_breakdown": {}}

    returns = [t.net_return_pct for t in trades]
    pnls = [t.pnl_dollars for t in trades]
    wins = [r for r in returns if r > 0]

    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = None  # undefined: no losing trades to divide by

    mean_r = statistics.mean(returns)
    stdev_r = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    sharpe = (mean_r / stdev_r) * math.sqrt(len(returns)) if stdev_r > 1e-9 else 0.0

    cum, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    exit_reasons = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades), 4),
        "profit_factor": round(profit_factor, 3) if profit_factor is not None else None,
        "sharpe": round(sharpe, 3),
        "mean_return_pct": round(mean_r, 5),
        "total_net_return_pct": round(sum(returns), 4),
        "total_pnl_dollars": round(sum(pnls), 2),
        "max_drawdown_dollars": round(max_dd, 2),
        "exit_reason_breakdown": exit_reasons,
    }


def _sharpe_of(sample: list) -> float:
    if len(sample) < 2:
        return 0.0
    mean = statistics.mean(sample)
    stdev = statistics.pstdev(sample)
    if stdev < 1e-9:
        return 0.0
    return (mean / stdev) * math.sqrt(len(sample))


def _bootstrap(values: list, stat_fn, n_boot: int, ci: float, seed: int, block_size: int = 1) -> tuple:
    """Percentile bootstrap. `block_size` > 1 selects a *circular moving-block* bootstrap.

    The i.i.d. resample below is only valid if the trades are independent draws, and in this
    engine they are not: a strategy held for `hold_days` and re-entered every `step_days`
    produces consecutive trades whose windows overlap and which therefore share the same
    stretch of one price path. Resampling those as independent understates the variance and
    inflates the pass rate -- measured at roughly 14% against a 2.5% nominal on a zero-edge
    synthetic (see test_block_bootstrap.py).

    Blocks are drawn circularly (wrapping past the end) rather than from starts in
    [0, n-L]: with linear blocks the first and last few observations appear in fewer blocks
    than the middle ones, which biases the resample toward the centre of the sample.

    block_size=1 reproduces the original i.i.d. path exactly, including the RNG call
    sequence, so previously recorded numbers remain reproducible.
    """
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    length = max(1, min(int(block_size), n))
    n_blocks = math.ceil(n / length)
    boot_stats = []
    for _ in range(n_boot):
        if length == 1:
            sample = [values[rng.randrange(n)] for _ in range(n)]
        else:
            sample = []
            for _ in range(n_blocks):
                start = rng.randrange(n)
                sample.extend(values[(start + k) % n] for k in range(length))
            del sample[n:]
        boot_stats.append(stat_fn(sample))
    boot_stats.sort()
    alpha = (1 - ci) / 2
    lo_idx = max(int(alpha * n_boot), 0)
    hi_idx = min(int((1 - alpha) * n_boot), n_boot - 1)
    return (boot_stats[lo_idx], boot_stats[hi_idx])


def bootstrap_confidence_interval(values: list, n_boot: int = 2000, ci: float = 0.95, seed: int = 42,
                                   block_size: int = 1) -> tuple:
    """Percentile-bootstrap CI on the mean of `values`."""
    return _bootstrap(values, statistics.mean, n_boot, ci, seed, block_size)


def bootstrap_sharpe_ci(values: list, n_boot: int = 2000, ci: float = 0.95, seed: int = 42,
                         block_size: int = 1) -> tuple:
    """Percentile-bootstrap CI on the Sharpe ratio of `values`."""
    return _bootstrap(values, _sharpe_of, n_boot, ci, seed, block_size)


@dataclass
class ValidationResult:
    passed: bool
    reasons: list
    metrics: dict
    mean_return_ci: tuple
    sharpe_ci: tuple


def validate_strategy_result(trades: list, min_trades: int = 30, ci: float = 0.95,
                              n_boot: int = 2000, seed: int = 42, block_size: int = 1) -> ValidationResult:
    """The pass/fail gate. There is no partial credit: a strategy PASSes only if

      1. it has at least `min_trades` trades (guards against small-sample false positives), and
      2. the bootstrap CI on mean return excludes zero *and* is entirely positive, and
      3. the bootstrap CI on Sharpe excludes zero *and* is entirely positive.

    A strategy whose CI sits entirely below zero technically "excludes zero" too, but that
    is a confirmed loser, not a candidate for paper/live — so exclusion is checked on the
    upside specifically (CI lower bound > 0), not just "doesn't straddle zero".
    """
    reasons = []
    metrics = compute_metrics(trades)

    if len(trades) < min_trades:
        reasons.append(f"only {len(trades)} trades, need >= {min_trades} to guard against small-sample noise")

    returns = [t.net_return_pct for t in trades]
    if len(returns) >= 2:
        mean_ci = bootstrap_confidence_interval(returns, n_boot=n_boot, ci=ci, seed=seed,
                                                block_size=block_size)
        sharpe_ci = bootstrap_sharpe_ci(returns, n_boot=n_boot, ci=ci, seed=seed, block_size=block_size)
    else:
        mean_ci = (float("nan"), float("nan"))
        sharpe_ci = (float("nan"), float("nan"))

    if not (mean_ci[0] > 0):
        reasons.append(f"mean-return {ci:.0%} bootstrap CI {tuple(round(x, 5) for x in mean_ci)} "
                        f"does not exclude zero (lower bound must be > 0)")
    if not (sharpe_ci[0] > 0):
        reasons.append(f"Sharpe {ci:.0%} bootstrap CI {tuple(round(x, 3) for x in sharpe_ci)} "
                        f"does not exclude zero (lower bound must be > 0)")

    return ValidationResult(len(reasons) == 0, reasons, metrics, mean_ci, sharpe_ci)


@dataclass
class SubPeriodResult:
    passed: bool
    first_half: ValidationResult
    second_half: ValidationResult
    reasons: list


def validate_sub_period_stability(trades: list, min_trades_per_half: int = 15, ci: float = 0.95,
                                   block_size: int = 1) -> SubPeriodResult:
    """Splits `trades` chronologically in half and requires BOTH halves to individually
    clear validate_strategy_result — not just the combined sample. Catches a strategy
    whose combined-sample pass is actually carried by one half of history while the other
    half fails on its own: verified necessary against real data — agent/backtest/stress_test.py
    found AMD long_directional's apparent edge was concentrated in the second half of its
    6-year window (first half alone: Sharpe 0.99, does not clear the gate). No partial
    credit here either: either both halves pass, or the whole thing fails.
    """
    mid = len(trades) // 2
    first_half = validate_strategy_result(trades[:mid], min_trades=min_trades_per_half, ci=ci,
                                          block_size=block_size)
    second_half = validate_strategy_result(trades[mid:], min_trades=min_trades_per_half, ci=ci,
                                           block_size=block_size)
    reasons = []
    if not first_half.passed:
        reasons.append(f"first half of history fails validation on its own: {'; '.join(first_half.reasons)}")
    if not second_half.passed:
        reasons.append(f"second half of history fails validation on its own: {'; '.join(second_half.reasons)}")
    return SubPeriodResult(
        passed=first_half.passed and second_half.passed,
        first_half=first_half, second_half=second_half, reasons=reasons,
    )
