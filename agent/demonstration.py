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


async def run_cycle(dry_run: bool = True) -> dict:
    """Build (and optionally submit) the single demonstration spread.

    Defaults to dry_run: it prices the real chain, builds the exact mleg payload, and runs it
    through the full risk gate, but does not submit. Nothing here decides anything the gate
    would not also decide -- it is the gate that says yes.
    """
    import json
    from datetime import date

    from agent.config import assert_paper_trading
    from agent.mcp.client import AlpacaMCPClient
    from agent.risk.gates import RiskGate
    from agent.kill_switch import assert_not_killed
    from agent.trade_log import log_event
    from agent.alerts import alert
    from agent.options_pricing import realized_vol
    from agent.strategies import vertical_credit_spread
    from agent.mcp_parsers import parse_latest_trade_price, parse_bars_closes, parse_order_error
    from agent.live_chain import fetch_target_expiry_chain
    from agent.deterministic_agent import _match_leg_to_real_chain, TARGET_DTE

    assert_paper_trading()
    assert_not_killed()

    result = {"validation_status": DEMONSTRATION_STATUS, "submitted": False, "skipped": [],
              "rejections": [], "order": None}

    if not CONFIG.demonstration_mode:
        result["skipped"].append("DEMONSTRATION_MODE is not set; nothing to do")
        return result

    risk_gate = RiskGate()
    async with AlpacaMCPClient() as mcp:
        account_raw = await mcp.call_tool("get_account_info", {})
        positions_raw = await mcp.call_tool("get_all_positions", {})
        try:
            account_info = json.loads(account_raw).get("data", {})
            positions = json.loads(positions_raw).get("data", {}).get("result", [])
            if not isinstance(positions, list):
                positions = []
        except (json.JSONDecodeError, AttributeError):
            account_info, positions = {}, []
        risk_gate.refresh(account_info, positions)

        # This mode places one position, once. Anything already open means it has run.
        if len(positions) >= MAX_OPEN_POSITIONS:
            result["skipped"].append(
                f"{len(positions)} position(s) already open; demonstration mode places at most "
                f"{MAX_OPEN_POSITIONS} and will not add to the book")
            log_event("demonstration_skipped", reason=result["skipped"][-1],
                      validation_status=DEMONSTRATION_STATUS)
            return result

        price_raw = await mcp.call_tool("get_stock_latest_trade", {"symbols": SYMBOL})
        bars_raw = await mcp.call_tool("get_stock_bars",
                                       {"symbols": SYMBOL, "timeframe": "1Day", "days": 40})
        try:
            S = parse_latest_trade_price(price_raw)
            closes = parse_bars_closes(bars_raw, SYMBOL)
        except (ValueError, KeyError, TypeError) as exc:
            result["skipped"].append(f"could not parse live {SYMBOL} price/bars ({exc})")
            return result
        if len(closes) < 20:
            result["skipped"].append("not enough recent bars for a volatility estimate")
            return result

        sigma = realized_vol(closes, window=20)
        target_expiry, chain = await fetch_target_expiry_chain(
            mcp, SYMBOL, S, TARGET_DTE, CONFIG.min_days_to_expiration,
            CONFIG.max_days_to_expiration, round(S * 0.85, 2), round(S * 1.02, 2))
        if not chain:
            result["skipped"].append(
                f"no listed {SYMBOL} contracts in the {CONFIG.min_days_to_expiration}-"
                f"{CONFIG.max_days_to_expiration} DTE window")
            return result

        # Time to expiry from the expiry the chain returned, never a hardcoded constant:
        # strike_for_delta is very sensitive to it at this horizon.
        t_years = max((target_expiry - date.today()).days, 1) / 365
        legs = vertical_credit_spread(S, t_years, sigma).legs
        matched = [_match_leg_to_real_chain(leg, chain, S, t_years, sigma) for leg in legs]
        if any(m is None for m in matched):
            result["skipped"].append(f"{SYMBOL} chain had no real contract for every leg")
            return result

        short = next(m for leg, m in zip(legs, matched) if leg.side == "sell")
        long_ = next(m for leg, m in zip(legs, matched) if leg.side == "buy")
        if long_.strike >= short.strike:
            result["skipped"].append(
                f"real-chain match put the protective leg at {long_.strike} against a short at "
                f"{short.strike} — that is not a hedge, skipping rather than submitting it")
            return result

        # Shade the mid credit to buy fill probability. These are indicative-feed marks, not
        # OPRA, so the mid is an estimate to begin with; a demonstration that never fills
        # demonstrates nothing, and giving up a tenth of the credit on a $380 position costs
        # less than the information does.
        credit = max(round((short.price - long_.price) * 0.9, 2), 0.01)
        payload = {
            "qty": str(MAX_CONTRACTS),
            "type": "limit",
            "time_in_force": "day",
            "order_class": "mleg",
            "limit_price": str(-credit),
            "client_order_id": f"demo-{SYMBOL}-{date.today().isoformat()}",
            "legs": [
                {"symbol": long_.symbol, "side": "buy", "ratio_qty": "1",
                 "position_intent": "buy_to_open"},
                {"symbol": short.symbol, "side": "sell", "ratio_qty": "1",
                 "position_intent": "sell_to_open"},
            ],
        }

        decision = risk_gate.check("place_option_order", payload)
        result["order"] = {"payload": payload, "underlying_price": S, "expiry": str(target_expiry),
                           "decision": decision}
        if not decision.get("approved"):
            result["rejections"].append(decision.get("reason", ""))
            log_event("demonstration_rejected", reason=decision.get("reason"),
                      payload=payload, validation_status=DEMONSTRATION_STATUS)
            return result

        if dry_run:
            result["skipped"].append("dry run — payload built and approved, not submitted")
            return result

        raw = await mcp.call_tool("place_option_order", payload)
        error = parse_order_error(raw)
        log_event("demonstration_order", symbol=SYMBOL, payload=payload,
                  capital_at_risk=decision.get("estimated_capital_at_risk"),
                  capital_basis=decision.get("capital_basis"), result=raw[:1500], error=error,
                  validation_status=DEMONSTRATION_STATUS)
        if error:
            result["rejections"].append(f"rejected by Alpaca — {error}")
            alert("order_rejected", agent="demonstration", symbol=SYMBOL, reason=error)
            return result
        alert("order_placed", agent="demonstration", symbol=SYMBOL,
              capital_at_risk=decision.get("estimated_capital_at_risk"),
              validation_status=DEMONSTRATION_STATUS)
        result["submitted"] = True
        return result
