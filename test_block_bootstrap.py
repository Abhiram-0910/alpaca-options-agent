"""Does the moving-block bootstrap actually fix the overlapping-window false-positive rate?

The validation gate's whole claim is that a PASS means something. That claim rests on the
bootstrap CI, and the i.i.d. resample it used is invalid for this engine's trades: holding
21 days and re-entering every 7 makes consecutive trades share two thirds of one price
path. This measures the damage and the repair on a strategy with, by construction, exactly
zero edge -- a pure random walk. Every PASS here is a false positive.

    python test_block_bootstrap.py
"""
import random
import statistics

from agent.backtest.metrics import TradeRecord, validate_strategy_result

HOLD_DAYS = 21          # matches agent/backtest/engine.py
STEP_DAYS = 7
BLOCK = 3               # ceil(HOLD_DAYS / STEP_DAYS): trades this close together overlap
REPLICATIONS = 120
N_BOOT = 300
NOMINAL = 0.025         # one-sided 95% CI -> 2.5% of zero-edge samples should pass by luck


def _zero_edge_trades(rng: random.Random, n_days: int = 900) -> list:
    """Overlapping hold-window returns drawn from a driftless random walk.

    Reproduces the engine's own trade construction: daily log returns with zero mean, summed
    over a HOLD_DAYS window, with the entry sliding forward STEP_DAYS at a time. Any edge
    found here is an artefact of the statistics, not of the strategy.
    """
    daily = [rng.gauss(0.0, 0.01) for _ in range(n_days)]
    trades = []
    i = 20
    while i + HOLD_DAYS < n_days:
        r = sum(daily[i:i + HOLD_DAYS])
        trades.append(TradeRecord(net_return_pct=r, pnl_dollars=r * 1000,
                                   exit_reason="expiration", holding_minutes=HOLD_DAYS * 1440,
                                   entry_index=i))
        i += STEP_DAYS
    return trades


def _pass_rate(block_size: int) -> float:
    passes = 0
    for rep in range(REPLICATIONS):
        trades = _zero_edge_trades(random.Random(1000 + rep))
        result = validate_strategy_result(trades, min_trades=30, n_boot=N_BOOT,
                                          seed=7, block_size=block_size)
        passes += result.passed
    return passes / REPLICATIONS


def demo() -> None:
    # The overlap is real and worth stating rather than assuming.
    overlap = (HOLD_DAYS - STEP_DAYS) / HOLD_DAYS
    assert overlap > 0.6, overlap
    print(f"consecutive trades share {overlap:.0%} of their holding window")

    iid = _pass_rate(block_size=1)
    block = _pass_rate(block_size=BLOCK)
    print(f"zero-edge PASS rate, i.i.d. bootstrap : {iid:.1%}  (nominal {NOMINAL:.1%})")
    print(f"zero-edge PASS rate, block bootstrap  : {block:.1%}  (block length {BLOCK})")

    assert iid > NOMINAL * 2, (
        f"i.i.d. bootstrap passed only {iid:.1%} of zero-edge samples; the bias this test "
        f"exists to demonstrate did not reproduce")
    assert block < iid, (
        f"block bootstrap ({block:.1%}) did not reduce the false-positive rate below i.i.d. "
        f"({iid:.1%})")
    assert block <= 0.10, (
        f"block bootstrap still passes {block:.1%} of zero-edge samples; too high to call the "
        f"gate meaningful")

    # block_size=1 must be byte-identical to the old behaviour, or every previously recorded
    # number in the graveyard becomes unreproducible.
    trades = _zero_edge_trades(random.Random(1))
    a = validate_strategy_result(trades, n_boot=200, seed=42)
    b = validate_strategy_result(trades, n_boot=200, seed=42, block_size=1)
    assert a.mean_return_ci == b.mean_return_ci and a.sharpe_ci == b.sharpe_ci, \
        "block_size=1 must reproduce the original i.i.d. path exactly"

    print("block bootstrap: all checks pass")


if __name__ == "__main__":
    demo()
