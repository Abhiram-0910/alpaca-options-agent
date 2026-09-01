"""The four options strategy families the agent can choose between.

Each strategy is defined once here as pure, deterministic logic so the exact
same rules are used in the backtest engine and are described (not
re-implemented) to Claude in the live agent's system prompt.
"""
from dataclasses import dataclass
from agent.options_pricing import bs_price, bs_delta, strike_for_delta


@dataclass
class TradeLeg:
    option_type: str  # "call" | "put"
    strike: float
    side: str  # "sell" | "buy"
    price: float  # theoretical/quoted price per share at entry (same field name as OptionLegPrice.price
    # so the generic simulator in agent/backtest/simulator.py can treat both leg types uniformly)


@dataclass
class StrategyPlan:
    name: str
    legs: list
    net_credit: float  # positive = credit received, negative = debit paid
    max_loss_per_contract: float
    rationale: str


def cash_secured_put(S: float, T: float, sigma: float, target_delta: float = -0.30) -> StrategyPlan:
    K = strike_for_delta(S, T, sigma, "put", target_delta)
    premium = bs_price(S, K, T, sigma, "put")
    leg = TradeLeg("put", K, "sell", premium)
    return StrategyPlan(
        name="cash_secured_put",
        legs=[leg],
        net_credit=premium,
        max_loss_per_contract=max(K - premium, 0) * 100,
        rationale=f"Sell {K:.2f} put (~{target_delta:.2f} delta) for {premium:.2f} credit; "
                   f"income strategy, bullish/neutral bias, assignment risk if price < {K:.2f}.",
    )


def covered_call(S: float, T: float, sigma: float, target_delta: float = 0.30) -> StrategyPlan:
    K = strike_for_delta(S, T, sigma, "call", target_delta)
    premium = bs_price(S, K, T, sigma, "call")
    call_leg = TradeLeg("call", K, "sell", premium)
    # The covering 100 shares, as their own leg -- NOT a new order (this agent never buys stock
    # outright; the shares must already be held, see agent/risk/gates.py's naked-call check).
    # Included so agent/backtest/simulator.py's generic simulator scores this trade as an
    # actual covered call (P&L bounded by the stock's own move, offset by the call premium) --
    # without it, the simulator only ever saw the short call leg and scored covered_call
    # identically to a naked short call, which can show a large, statistically "significant"
    # profit from an underlying move that would have been a real loss once the stock leg's own
    # loss is counted (verified: a synthetic -17% decline scored +$1,915 by the simulator
    # against a true -$1,151 covered-call P&L for the same path).
    stock_leg = TradeLeg("stock", S, "buy", S)
    return StrategyPlan(
        name="covered_call",
        legs=[call_leg, stock_leg],
        net_credit=premium - S,  # premium received, minus the cost of the shares it's covered by
        max_loss_per_contract=max(S - premium, 0) * 100,  # capped by underlying downside, net of credit
        rationale=f"Sell {K:.2f} call (~{target_delta:.2f} delta) for {premium:.2f} credit against 100 owned "
                   f"shares; income strategy, caps upside above {K:.2f}.",
    )


def long_directional(S: float, T: float, sigma: float, momentum: float, target_delta: float = 0.40) -> StrategyPlan:
    bullish = momentum >= 0
    option_type = "call" if bullish else "put"
    delta = target_delta if bullish else -target_delta
    K = strike_for_delta(S, T, sigma, option_type, delta)
    premium = bs_price(S, K, T, sigma, option_type)
    leg = TradeLeg(option_type, K, "buy", premium)
    return StrategyPlan(
        name="long_directional",
        legs=[leg],
        net_credit=-premium,
        max_loss_per_contract=premium * 100,
        rationale=f"Buy {K:.2f} {option_type} (~{delta:.2f} delta) for {premium:.2f} debit; "
                   f"{'bullish' if bullish else 'bearish'} momentum signal, risk capped at premium paid.",
    )


def vertical_credit_spread(S: float, T: float, sigma: float,
                            short_delta: float = -0.30, long_delta: float = -0.15) -> StrategyPlan:
    """Bull put credit spread: sell a closer put, buy a further OTM put for protection.

    This is executed as two sequential single-leg orders against Alpaca (no
    atomic multi-leg order type is used), which is compatible with every
    account options trading level.
    """
    K_short = strike_for_delta(S, T, sigma, "put", short_delta)
    K_long = strike_for_delta(S, T, sigma, "put", long_delta)
    K_long = min(K_long, K_short - 0.5)  # ensure the protective leg is further OTM
    p_short = bs_price(S, K_short, T, sigma, "put")
    p_long = bs_price(S, K_long, T, sigma, "put")
    credit = p_short - p_long
    width = K_short - K_long
    legs = [
        TradeLeg("put", K_short, "sell", p_short),
        TradeLeg("put", K_long, "buy", p_long),
    ]
    return StrategyPlan(
        name="vertical_credit_spread",
        legs=legs,
        net_credit=credit,
        max_loss_per_contract=max(width - credit, 0) * 100,
        rationale=f"Sell {K_short:.2f}P / buy {K_long:.2f}P for {credit:.2f} net credit; "
                   f"defined-risk volatility play, max loss capped at {max(width - credit, 0) * 100:.0f}.",
    )


STRATEGY_FUNCS = {
    "cash_secured_put": cash_secured_put,
    "covered_call": covered_call,
    "vertical_credit_spread": vertical_credit_spread,
    # long_directional needs a momentum input and is called directly where used
}
