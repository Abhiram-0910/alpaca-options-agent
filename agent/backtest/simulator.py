"""Generic day-by-day trade simulator shared by every strategy (single-leg
income/directional plays and the multi-leg iron condor alike).

The uniform trick: for any collection of option legs (each with a strike,
option_type, and side), the dollar value to *close* the position at some
future (S, T_remaining) is the exact same formula used to price it fresh —
sum leg prices with +1 for a sold leg (you'd have to buy it back) and -1 for
a bought leg (you'd sell it back). That lets one simulator mark-to-market,
apply an ATR-derived stop-loss, and settle at expiration for CSPs, covered
calls, long calls/puts, credit spreads, and iron condors without any
strategy-specific branching.
"""
from typing import Callable, Optional

from agent.options_pricing import bs_price
from agent.backtest.metrics import TradeRecord


def _leg_value(leg, price: float) -> float:
    return price if leg.side == "sell" else -price


def _intrinsic(leg, S_exit: float) -> float:
    if leg.option_type == "call":
        return max(S_exit - leg.strike, 0.0)
    return max(leg.strike - S_exit, 0.0)


def simulate_trade(
    closes: list,
    entry_index: int,
    hold_days: int,
    legs: list,
    entry_credit: float,
    max_loss_dollars: float,
    sigma: float,
    cost_model,
    symbol: str = None,
    strategy: str = None,
    stop_loss_underlying_move: Optional[float] = None,
    stop_loss_credit_multiple: Optional[float] = None,
    profit_target_pct: Optional[float] = None,
    force_exit_offset: Optional[int] = None,
    price_fn: Callable = bs_price,
) -> TradeRecord:
    """Opens `legs` at closes[entry_index] for `entry_credit` ($/share, positive=credit
    received, negative=debit paid), marks to market each trading day using `price_fn`
    (Black-Scholes by default — the synthetic path; pass a real-quote lookup to mark
    against actual chain data instead), and exits on whichever comes first: an
    ATR-derived stop-loss, a profit target, a scheduled managed exit, or expiration
    (settled on intrinsic value, not a recomputed theoretical price — real settlement
    mechanics, not a model output).

    `stop_loss_underlying_move` is a *price* distance (typically N x ATR, fixed before
    the backtest runs — see agent/backtest/atr.py) rather than a dollar P&L threshold:
    the trade is stopped out once the underlying has moved against the position by at
    least that much AND the position is currently showing a loss.

    `stop_loss_credit_multiple`, for credit strategies (entry_credit > 0), is the
    conventional way multi-leg premium-selling structures (iron condors, credit spreads)
    are actually risk-managed: exit once the loss reaches N times the credit received
    (e.g. 2.0 = stop once you're down 2x what you collected), independent of how far the
    underlying itself has moved. Distinct from `stop_loss_underlying_move`, which is tuned
    for directional/single-leg structures — an underlying-*price*-distance stop is
    systematically too tight for a longer-dated, higher-vega credit structure (verified:
    applying it to a 45-DTE condor stopped out ~93% of trades regardless of whether the
    position was actually threatened), so don't reuse it for that case.

    `force_exit_offset`, when set, closes the position at mark-to-market (not intrinsic
    settlement — there's real time value left) after that many days regardless of P&L,
    if no stop-loss/profit-target fired first. This is how a "manage at N days" exit rule
    (e.g. a 45-DTE-entry iron condor closed at 21 DTE remaining, rather than held to
    expiration) is expressed: pass the full time-to-expiration as `hold_days` for pricing
    purposes, and the earlier day count you actually want to hold to as `force_exit_offset`.
    """
    n = len(closes)
    S0 = closes[entry_index]

    for offset in range(1, hold_days + 1):
        idx = entry_index + offset
        if idx >= n:
            break
        S_t = closes[idx]
        T_remaining = max((hold_days - offset) / 365, 1 / 365)
        leg_marks = [price_fn(S_t, leg.strike, T_remaining, sigma, leg.option_type) for leg in legs]
        mark_value = sum(_leg_value(leg, p) for leg, p in zip(legs, leg_marks))
        pnl_dollars = (entry_credit - mark_value) * 100

        if (stop_loss_underlying_move is not None and pnl_dollars < 0
                and abs(S_t - S0) >= stop_loss_underlying_move):
            friction = sum(cost_model.round_trip_cost(getattr(leg, "price", 0.0), p)
                            for leg, p in zip(legs, leg_marks))
            return _record(pnl_dollars - friction, max_loss_dollars, "stop_loss", offset, symbol, strategy,
                            entry_index)

        if (stop_loss_credit_multiple is not None and entry_credit > 0
                and pnl_dollars <= -stop_loss_credit_multiple * entry_credit * 100):
            friction = sum(cost_model.round_trip_cost(getattr(leg, "price", 0.0), p)
                            for leg, p in zip(legs, leg_marks))
            return _record(pnl_dollars - friction, max_loss_dollars, "stop_loss", offset, symbol, strategy,
                            entry_index)

        if profit_target_pct is not None and entry_credit > 0:
            target = entry_credit * 100 * profit_target_pct
            if pnl_dollars >= target:
                friction = sum(cost_model.round_trip_cost(getattr(leg, "price", 0.0), p)
                                for leg, p in zip(legs, leg_marks))
                return _record(pnl_dollars - friction, max_loss_dollars, "profit_target", offset, symbol,
                                strategy, entry_index)

        if force_exit_offset is not None and offset >= force_exit_offset:
            friction = sum(cost_model.round_trip_cost(getattr(leg, "price", 0.0), p)
                            for leg, p in zip(legs, leg_marks))
            return _record(pnl_dollars - friction, max_loss_dollars, "time_exit", offset, symbol,
                            strategy, entry_index)

    exit_idx = min(entry_index + hold_days, n - 1)
    S_exit = closes[exit_idx]
    leg_settles = [_intrinsic(leg, S_exit) for leg in legs]
    settle_value = sum(_leg_value(leg, p) for leg, p in zip(legs, leg_settles))
    pnl_dollars = (entry_credit - settle_value) * 100
    friction = sum(cost_model.round_trip_cost(getattr(leg, "price", 0.0), p)
                    for leg, p in zip(legs, leg_settles))
    return _record(pnl_dollars - friction, max_loss_dollars, "expiration", exit_idx - entry_index, symbol,
                    strategy, entry_index)


def _record(pnl_dollars, max_loss_dollars, exit_reason, days_held, symbol, strategy, entry_index) -> TradeRecord:
    capital_at_risk = max(max_loss_dollars, 1.0)
    return TradeRecord(
        net_return_pct=pnl_dollars / capital_at_risk,
        pnl_dollars=pnl_dollars,
        exit_reason=exit_reason,
        holding_minutes=days_held * 24 * 60,
        symbol=symbol,
        strategy=strategy,
        entry_index=entry_index,
    )
