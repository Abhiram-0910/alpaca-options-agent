"""A zero-LLM-cost paper-trading executor.

Runs the exact same strategy functions the backtest validated
(agent/strategies + agent/backtest/iron_condor.py), against live prices and a
real option chain snapshot pulled through Alpaca's MCP server, and places
orders through the same MCP server — with no Anthropic API call anywhere in
the path. Only symbol/strategy combinations that passed the statistical
validation gate in logs/backtest_report.json are ever considered, and every
order still passes through the same RiskGate as the Claude-driven agent.

This exists to let you test the trading mechanics (data fetch -> real-chain
strike matching -> risk gates -> order placement) for free before spending
anything on the LLM-driven agent in agent/live_agent.py.
"""
import json
import os
from datetime import date

from agent.config import CONFIG, assert_paper_trading
from agent.mcp.client import AlpacaMCPClient
from agent.risk.gates import RiskGate, parse_occ_symbol
from agent.trade_log import log_event
from agent.kill_switch import assert_not_killed
from agent.alerts import alert
from agent.options_pricing import realized_vol, bs_delta, RISK_FREE_RATE
from agent.strategies import cash_secured_put, covered_call, long_directional, vertical_credit_spread
from agent.backtest.iron_condor import price_iron_condor
from agent.mcp_parsers import parse_latest_trade_price, parse_bars_closes, parse_order_error
from agent.live_chain import fetch_target_expiry_chain

TARGET_DTE = 2          # aim at the middle of the 1-4 DTE window the judged sessions offer
PROVISIONAL_T = 3 / 365  # only used to size the strike search band before the real expiry is known


def _load_cleared_strategies() -> dict:
    path = os.path.join(CONFIG.logs_dir, "backtest_report.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        report = json.load(f)
    picks = {}
    for symbol, data in report.items():
        cleared = data.get("cleared_for_paper") or []
        if not cleared:
            continue
        best = max(cleared, key=lambda name: data["strategies"][name]["metrics"].get("sharpe", float("-inf")))
        picks[symbol] = {"strategy": best, "metrics": data["strategies"][best]["metrics"]}
    return picks


def _match_leg_to_real_chain(leg, chain: list, S: float, T: float, sigma: float):
    """Finds the real listed contract closest in delta to a theoretical leg.
    Prefers Alpaca's own reported greek over a re-derived Black-Scholes delta."""
    target_delta = bs_delta(S, leg.strike, T, sigma, leg.option_type, RISK_FREE_RATE)
    candidates = [c for c in chain if c.option_type == leg.option_type]
    if not candidates:
        return None

    def delta_of(c):
        return c.delta if c.delta is not None else bs_delta(S, c.strike, T, sigma, c.option_type, RISK_FREE_RATE)

    return min(candidates, key=lambda c: abs(delta_of(c) - target_delta))


def _call_leg_is_hedged(leg, all_legs: list) -> bool:
    """True if `leg` is a short call with a further-OTM long call among `all_legs` of the same
    strategy plan -- i.e. it's the short leg of a defined-risk spread (iron_condor's short_call,
    hedged by its own long_call), not a naked call that needs 100 shares owned as cover. Without
    this, RiskGate's naked-call check has no way to tell the two apart and rejects both alike."""
    if leg.side != "sell" or leg.option_type != "call":
        return False
    return any(other.side == "buy" and other.option_type == "call" and other.strike > leg.strike
               for other in all_legs)


def _legs_properly_ordered(theoretical_legs: list, matched: list) -> bool:
    """Guards against a real-chain match silently collapsing a spread's protection: a "buy" leg
    must land strictly further OTM than any "sell" leg of the same option_type it's meant to
    hedge. price_iron_condor_real_quotes() (agent/backtest/iron_condor.py) enforces this by
    construction when matching real quotes; _match_leg_to_real_chain below matches each leg
    independently by nearest delta with no such constraint, so on a sparse/coarse real chain the
    "protective" leg could end up at, or on the wrong side of, its paired short leg's strike."""
    for leg, real in zip(theoretical_legs, matched):
        if leg.side != "buy":
            continue
        for other_leg, other_real in zip(theoretical_legs, matched):
            if other_leg.side != "sell" or other_leg.option_type != leg.option_type:
                continue
            if leg.option_type == "put" and real.strike >= other_real.strike:
                return False
            if leg.option_type == "call" and real.strike <= other_real.strike:
                return False
    return True


def _build_theoretical_legs(strategy: str, S: float, sigma: float, momentum: float, t_years: float):
    if strategy == "cash_secured_put":
        return cash_secured_put(S, t_years, sigma).legs
    if strategy == "covered_call":
        return covered_call(S, t_years, sigma).legs
    if strategy == "long_directional":
        return long_directional(S, t_years, sigma, momentum).legs
    if strategy == "vertical_credit_spread":
        return vertical_credit_spread(S, t_years, sigma).legs
    if strategy == "iron_condor":
        return price_iron_condor(S, t_years, sigma).legs
    raise ValueError(f"unknown strategy {strategy}")


async def run_cycle() -> dict:
    assert_paper_trading()
    assert_not_killed()
    picks = _load_cleared_strategies()
    result = {"considered": list(picks.keys()), "orders_placed": [], "skipped": [], "rejections": []}
    if not picks:
        result["skipped"].append("no symbol/strategy combination has cleared backtest validation — "
                                  "run run_backtest.py first")
        log_event("deterministic_cycle_complete", **result)
        return result

    risk_gate = RiskGate()

    async with AlpacaMCPClient() as mcp:
        account_raw = await mcp.call_tool("get_account_info", {})
        positions_raw = await mcp.call_tool("get_all_positions", {})
        # Every Alpaca MCP tool result is wrapped {"_alpaca_mcp_security": ..., "data": ...} —
        # get_account_info's `data` is the account dict directly; get_all_positions' `data` is
        # {"result": [...]}, one level deeper. Verified against a live account: getting this
        # wrong silently zeroes out equity and positions, which trips RiskGate's "no account
        # snapshot" guard and auto-rejects every order.
        try:
            account_info = json.loads(account_raw).get("data", {})
            positions = json.loads(positions_raw).get("data", {}).get("result", [])
            if not isinstance(positions, list):
                positions = []
        except (json.JSONDecodeError, AttributeError):
            # Matches the guard agent/live_agent.py and agent/live_agent_openai.py already have
            # around this identical parse -- fails to an empty snapshot rather than crashing the
            # whole cycle; RiskGate's own equity<=0 guard then refuses to trade blind on it.
            account_info, positions = {}, []
        risk_gate.refresh(account_info, positions)

        def _root_of(pos_symbol: str) -> str:
            parsed = parse_occ_symbol(pos_symbol)
            return parsed["root"] if parsed else pos_symbol  # plain equity position: symbol is the root

        held_roots = {_root_of(p.get("symbol", "")) for p in positions}

        for symbol, pick in picks.items():
            strategy_name = pick["strategy"]
            if symbol in held_roots:
                result["skipped"].append(f"{symbol}: already holds a position, skipping to avoid piling in")
                continue

            price_raw = await mcp.call_tool("get_stock_latest_trade", {"symbols": symbol})
            bars_raw = await mcp.call_tool("get_stock_bars", {"symbols": symbol, "timeframe": "1Day", "days": 40})
            try:
                S = parse_latest_trade_price(price_raw)
                closes = parse_bars_closes(bars_raw, symbol)
            except (ValueError, KeyError, TypeError) as exc:
                result["skipped"].append(f"{symbol}: could not parse live price/bars ({exc})")
                continue
            if len(closes) < 20:
                result["skipped"].append(f"{symbol}: not enough recent bars for a vol estimate")
                continue

            sigma = realized_vol(closes, window=20)
            momentum = closes[-1] - closes[-10] if len(closes) >= 10 else 0.0
            theoretical_legs = _build_theoretical_legs(strategy_name, S, sigma, momentum, PROVISIONAL_T)
            # covered_call's plan includes a "stock" leg (the covering shares this agent never
            # buys/sells itself -- see agent/strategies/__init__.py) so the *backtest* simulator
            # scores its real P&L. It isn't a real OCC contract to look up on the chain, check
            # against RiskGate, or submit an order for, so it's excluded here, before any of that.
            theoretical_legs = [leg for leg in theoretical_legs if leg.option_type != "stock"]

            # Bound strike_price_gte/lte around the strikes the theoretical legs actually need,
            # with a wide margin, so the fetch can't miss them.
            leg_strikes = [leg.strike for leg in theoretical_legs]
            strike_lo = round(min(leg_strikes) * 0.7, 2)
            strike_hi = round(max(leg_strikes) * 1.3, 2)

            target_expiry, same_expiry_chain = await fetch_target_expiry_chain(
                mcp, symbol, S, TARGET_DTE, CONFIG.min_days_to_expiration, CONFIG.max_days_to_expiration,
                strike_lo, strike_hi,
            )
            if not same_expiry_chain:
                result["skipped"].append(
                    f"{symbol}: no listed contracts in the {CONFIG.min_days_to_expiration}-"
                    f"{CONFIG.max_days_to_expiration} DTE window within strike range "
                    f"{strike_lo}-{strike_hi}")
                continue

            # Rebuild the legs against the expiry the chain actually returned. Strike selection
            # runs through strike_for_delta, which is extremely sensitive to T: a "30-delta"
            # put is far OTM at 30 days and nearly at the money at 2. Building legs at a
            # hardcoded 30/365 and matching them against a 2-DTE chain picks strikes for a
            # trade we are not placing.
            t_years = max((target_expiry - date.today()).days, 1) / 365
            theoretical_legs = _build_theoretical_legs(strategy_name, S, sigma, momentum, t_years)
            theoretical_legs = [leg for leg in theoretical_legs if leg.option_type != "stock"]

            matched = [_match_leg_to_real_chain(leg, same_expiry_chain, S, t_years, sigma)
                       for leg in theoretical_legs]
            if any(m is None for m in matched):
                result["skipped"].append(f"{symbol}: chain didn't have a real contract for every leg of "
                                          f"{strategy_name}")
                continue
            if not _legs_properly_ordered(theoretical_legs, matched):
                result["skipped"].append(f"{symbol}: real chain match produced an improperly-ordered "
                                          f"{strategy_name} spread (a protective leg wasn't further OTM "
                                          f"than its short leg) — skipping rather than submitting a broken hedge")
                continue

            leg_orders = []
            batch_committed = 0.0
            for leg, real in zip(theoretical_legs, matched):
                decision = risk_gate.check("place_option_order", {
                    "symbol": real.symbol, "side": leg.side, "qty": 1, "limit_price": real.price,
                }, covered_by_paired_long=_call_leg_is_hedged(leg, theoretical_legs))
                if not decision.get("approved"):
                    reason = decision.get("reason") or ""
                    result["rejections"].append(f"{symbol}/{strategy_name}: {real.symbol} rejected — {reason}")
                    if "circuit breaker" in reason or "Kill switch" in reason:
                        alert("order_blocked_critical", agent="deterministic_agent",
                              symbol=symbol, strategy=strategy_name, reason=reason)
                    # Roll back capital already committed by this batch's earlier legs -- e.g. an
                    # iron condor's short_put/long_put pass before short_call is rejected -- so the
                    # abandoned legs don't permanently eat into this cycle's real budget.
                    risk_gate.release_commitment(batch_committed)
                    leg_orders = None
                    break
                batch_committed += decision.get("estimated_capital_at_risk") or 0.0
                leg_orders.append((leg, real))

            if not leg_orders:
                continue

            # Submit buy (protective) legs before sell legs. Legs aren't atomic — if only one
            # side fills before the other, a buy-first ordering leaves a long option exposed
            # (defined risk: max loss is the premium already paid) rather than a naked short
            # (undefined/much larger risk) if the strategy's own leg list happened to put the
            # sell leg first, which vertical_credit_spread and iron_condor both do.
            leg_orders.sort(key=lambda pair: 0 if pair[0].side == "buy" else 1)

            placed = []
            for leg, real in leg_orders:
                position_intent = "sell_to_open" if leg.side == "sell" else "buy_to_open"
                order_args = {
                    "symbol": real.symbol,
                    "side": leg.side,
                    "qty": "1",
                    "type": "limit",
                    "limit_price": str(real.price),
                    "position_intent": position_intent,
                    "client_order_id": f"det-{symbol}-{strategy_name}-{real.symbol}",
                }
                order_result = await mcp.call_tool("place_option_order", order_args)
                # Alpaca rejecting an order comes back as a normal (non-error) MCP result, not an
                # exception -- see parse_order_error's docstring. Without this check, a rejected
                # leg was logged/alerted/recorded as placed just like a successful one, and for a
                # multi-leg strategy the loop would keep submitting the *following* legs as if
                # this one had gone through, risking exactly the naked exposure the buy-before-sell
                # ordering above exists to prevent.
                order_error = parse_order_error(order_result)
                log_event("deterministic_order", symbol=symbol, strategy=strategy_name,
                          strategy_metrics=pick["metrics"], leg=real.symbol, side=leg.side,
                          delta_target=leg.option_type, limit_price=real.price, result=order_result[:1500],
                          error=order_error)
                if order_error:
                    alert("order_rejected", agent="deterministic_agent", symbol=symbol, strategy=strategy_name,
                          contract=real.symbol, side=leg.side, limit_price=real.price, reason=order_error)
                    result["rejections"].append(
                        f"{symbol}/{strategy_name}: {real.symbol} rejected by Alpaca — {order_error} "
                        f"(legs already placed this batch: {', '.join(p['contract'] for p in placed) or 'none'})"
                    )
                    break
                alert("order_placed", agent="deterministic_agent", symbol=symbol, strategy=strategy_name,
                      contract=real.symbol, side=leg.side, limit_price=real.price)
                placed.append({"contract": real.symbol, "side": leg.side, "limit_price": real.price})

            if placed:
                result["orders_placed"].append({"symbol": symbol, "strategy": strategy_name, "legs": placed})

    log_event("deterministic_cycle_complete", **result)
    return result
