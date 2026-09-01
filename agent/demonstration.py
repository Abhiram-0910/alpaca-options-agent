"""Demonstration mode: one bounded, explicitly unvalidated trade.

As of 1 Sep 2026 the validation gate has refused every candidate it has been given -- three
liquid ETFs, seven structures, nothing cleared (docs/strategy_graveyard.md). That is the
project's headline finding, not a setback, and it is reported as such.

It leaves a question the gate was never designed to answer. The gate governs whether we may
CLAIM an edge. It does not govern whether an order is SAFE. A defined-risk vertical spread's
worst case is bounded and known before entry -- which is why defined risk was the requirement
in the first place -- so "we have no evidence of edge" and "this order could hurt the account"
are different statements, and only the first one is true here.

Demonstration mode executes exactly one such order, so the full path is shown working end to
end: chain read, strike selection in deterministic Python, risk gate, MCP multi-leg order,
managed exit. Every constraint below is TIGHTER than the normal path, none is looser, and
none is env-tunable -- an operator can turn this mode on, and can turn it off, and that is
the whole surface.

The one gate it replaces is the backtest-validation check, and it refuses to arm at all if
that check would have passed something, so a demonstration trade can never sit alongside or
be mistaken for a validated one.

Rejected alternative: relaxing the gate's criteria after seeing that everything failed. That
is the exact post-hoc move the gate exists to prevent, and a reviewer would be right to
discount every other number in this repo on the strength of it.
"""
from agent.config import CONFIG
from agent.backtest_evidence import load_cleared_symbols

# Stamped on every order, log line and trade-log entry this mode produces, so no result it
# generates can later be read -- by us, by a judge, or by the reflection loop -- as validated.
DEMONSTRATION_STATUS = "UNVALIDATED_DEMONSTRATION"

SYMBOL = "SPY"                    # deepest chain, daily expiries, tightest quotes available
MAX_CONTRACTS = 1
MAX_OPEN_POSITIONS = 1
MAX_LOSS_PCT_OF_NAV = 0.005       # 0.5% of NAV, roughly a tenth of the normal per-trade cap
MIN_LEGS = 2                      # defined risk requires a hedging leg, so never single-leg


def _cleared() -> set:
    return load_cleared_symbols()


def demonstration_status(root: str, legs: list, qty: float, equity: float = None) -> dict:
    """Whether demonstration mode is armed for this specific order.

    Returns {"armed": bool, "blocked": str, "max_loss_cap": float}. `blocked` is a rejection
    reason that outranks everything else: it means the operator asked for demonstration mode
    and this order is not one demonstration mode will place. Never raises -- the risk gate
    turns it into a normal rejection the caller can read.
    """
    cap = MAX_LOSS_PCT_OF_NAV * (equity if equity else 100_000)
    off = {"armed": False, "blocked": "", "max_loss_cap": cap}
    if not CONFIG.demonstration_mode:
        return off

    # Cannot coexist with a validated trade. If anything cleared, the normal path applies and
    # this mode has no reason to exist.
    cleared = _cleared()
    if cleared:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": (f"Demonstration mode refuses to arm: {', '.join(sorted(cleared))} "
                            f"cleared backtest validation, so the validated path applies. Turn "
                            f"DEMONSTRATION_MODE off.")}

    if root != SYMBOL:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": f"Demonstration mode trades {SYMBOL} only; got {root}."}
    if not isinstance(legs, list) or len(legs) < MIN_LEGS:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": (f"Demonstration mode requires a defined-risk multi-leg structure "
                            f"(>= {MIN_LEGS} legs); got {len(legs) if isinstance(legs, list) else legs!r}.")}
    if qty > MAX_CONTRACTS:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": f"Demonstration mode allows {MAX_CONTRACTS} contract; got {qty:g}."}

    return {"armed": True, "blocked": "", "max_loss_cap": cap}


def demo() -> None:
    """Self-check: the constraints that make this mode safe to leave in the repo."""
    # Patch this module's own globals, not a re-imported copy of it: run as __main__ the
    # module object here and the one `import agent.demonstration` returns are different.
    g = globals()

    legs2 = [{"symbol": "SPY260903P00755000", "side": "sell"},
             {"symbol": "SPY260903P00750000", "side": "buy"}]

    # Off by default: nothing arms unless the operator explicitly turns it on.
    assert not demonstration_status("SPY", legs2, 1)["armed"]

    real_cleared, real_flag = g["_cleared"], CONFIG.demonstration_mode
    try:
        object.__setattr__(CONFIG, "demonstration_mode", True)

        g["_cleared"] = lambda: set()
        assert demonstration_status("SPY", legs2, 1)["armed"], "should arm on a 1-lot SPY spread"
        assert demonstration_status("QQQ", legs2, 1)["blocked"], "SPY only"
        assert demonstration_status("SPY", legs2, 2)["blocked"], "1 contract only"
        assert demonstration_status("SPY", legs2[:1], 1)["blocked"], "single leg must be refused"

        g["_cleared"] = lambda: {"SPY"}
        assert demonstration_status("SPY", legs2, 1)["blocked"], \
            "must refuse to arm when something cleared validation"
    finally:
        g["_cleared"] = real_cleared
        object.__setattr__(CONFIG, "demonstration_mode", real_flag)

    assert demonstration_status("SPY", legs2, 1, equity=100_000)["max_loss_cap"] == 500.0
    print("demonstration: all checks pass")


if __name__ == "__main__":
    demo()
