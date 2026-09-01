"""Iron condor pricing: two paths feeding the same downstream shape.

- price_iron_condor(): purely synthetic, delta-targeted via Black-Scholes. Use when
  you have a vol input (quoted IV or a realized-vol proxy) but not a real chain snapshot
  for every strike — this is what the historical backtest uses, since full historical
  options chains aren't reliably available for a broad watchlist.
- price_iron_condor_real_quotes(): looks up each leg's actual quoted price from a real
  option-chain snapshot (source-agnostic — a live Alpaca chain, a cached historical
  snapshot, anything shaped like a list of ChainQuote). Falls back to synthetic
  per-leg only when a matching real quote is missing, so partial chain data still
  produces a usable price instead of discarding the whole condor.

Both paths return an IronCondorLegs so downstream backtest/metrics code never needs to
know which one produced a given trade.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from agent.options_pricing import bs_price, bs_delta, strike_for_delta, RISK_FREE_RATE


@dataclass
class OptionLegPrice:
    option_type: str          # "call" | "put"
    strike: float
    side: str                 # "sell" | "buy"
    price: float
    is_real_quote: bool       # True if sourced from a real chain snapshot, False if BSM-theoretical
    delta: Optional[float] = None


@dataclass
class IronCondorLegs:
    short_put: OptionLegPrice
    long_put: OptionLegPrice
    short_call: OptionLegPrice
    long_call: OptionLegPrice
    net_credit: float          # $ per share (multiply by 100 for $/contract)
    max_loss: float            # $ per contract (already x100)
    real_quoted_legs: int      # 0-4, how many legs actually came from real quotes
    expiry: Optional[date] = None

    @property
    def legs(self) -> list:
        return [self.short_put, self.long_put, self.short_call, self.long_call]


def _bounded_max_loss(K_short_put, K_long_put, K_short_call, K_long_call, net_credit) -> float:
    put_width = K_short_put - K_long_put
    call_width = K_long_call - K_short_call
    return max(max(put_width, call_width) - net_credit, 0.0) * 100


def price_iron_condor(
    S: float,
    T: float,
    sigma: float,
    r: float = RISK_FREE_RATE,
    short_delta_target: float = 0.16,
    long_delta_target: float = 0.08,
    long_put_delta_target: Optional[float] = None,
    long_call_delta_target: Optional[float] = None,
    expiry: Optional[date] = None,
) -> IronCondorLegs:
    """Delta-targeted iron condor, priced purely from Black-Scholes."""
    lp_target = long_put_delta_target if long_put_delta_target is not None else long_delta_target
    lc_target = long_call_delta_target if long_call_delta_target is not None else long_delta_target

    K_short_put = strike_for_delta(S, T, sigma, "put", -short_delta_target, r)
    K_long_put = strike_for_delta(S, T, sigma, "put", -lp_target, r)
    K_short_call = strike_for_delta(S, T, sigma, "call", short_delta_target, r)
    K_long_call = strike_for_delta(S, T, sigma, "call", lc_target, r)

    # Guarantee well-ordered, non-degenerate strikes (long legs strictly further OTM).
    K_long_put = min(K_long_put, K_short_put - 0.5)
    K_long_call = max(K_long_call, K_short_call + 0.5)

    def leg(option_type, K, side):
        price = bs_price(S, K, T, sigma, option_type, r)
        delta = bs_delta(S, K, T, sigma, option_type, r)
        return OptionLegPrice(option_type, round(K, 2), side, round(price, 4), is_real_quote=False, delta=delta)

    short_put = leg("put", K_short_put, "sell")
    long_put = leg("put", K_long_put, "buy")
    short_call = leg("call", K_short_call, "sell")
    long_call = leg("call", K_long_call, "buy")

    net_credit = (short_put.price - long_put.price) + (short_call.price - long_call.price)
    max_loss = _bounded_max_loss(K_short_put, K_long_put, K_short_call, K_long_call, net_credit)

    return IronCondorLegs(short_put, long_put, short_call, long_call, net_credit, max_loss, 0, expiry)


@dataclass
class ChainQuote:
    strike: float
    option_type: str   # "call" | "put"
    price: float        # mid price
    expiry: Optional[date] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    symbol: Optional[str] = None       # real OCC symbol, needed to actually place an order
    delta: Optional[float] = None      # Alpaca-reported greek, when available — preferred over a BSM estimate
    implied_vol: Optional[float] = None  # Alpaca-reported IV, when available


def nearest_expiry(available_expiries: list, target_dte: int, today: Optional[date] = None) -> Optional[date]:
    """Pick the available expiry whose DTE is closest to `target_dte`."""
    if not available_expiries:
        return None
    today = today or date.today()
    return min(available_expiries, key=lambda e: abs((e - today).days - target_dte))


def match_strike_by_delta(strikes: list, option_type: str, S: float, T: float, sigma: float,
                           target_delta: float, r: float = RISK_FREE_RATE) -> Optional[float]:
    """Among a list of *real, actually-listed* strikes, pick the one whose theoretical
    BSM delta is closest to `target_delta` — real quotes don't come with a delta
    attached, so we compute it off the same vol input used everywhere else."""
    if not strikes:
        return None
    return min(strikes, key=lambda K: abs(bs_delta(S, K, T, sigma, option_type, r) - target_delta))


def price_iron_condor_real_quotes(
    chain: list,   # list[ChainQuote], all for a single expiry
    S: float,
    T: float,
    sigma: float,
    r: float = RISK_FREE_RATE,
    short_delta_target: float = 0.16,
    long_delta_target: float = 0.08,
    long_put_delta_target: Optional[float] = None,
    long_call_delta_target: Optional[float] = None,
    expiry: Optional[date] = None,
) -> IronCondorLegs:
    """Prices the same delta-targeted structure as price_iron_condor(), but using each
    leg's real quoted price wherever the chain snapshot has one, falling back to a
    synthetic BSM price only for legs the snapshot is missing."""
    lp_target = long_put_delta_target if long_put_delta_target is not None else long_delta_target
    lc_target = long_call_delta_target if long_call_delta_target is not None else long_delta_target

    puts = sorted({c.strike for c in chain if c.option_type == "put"})
    calls = sorted({c.strike for c in chain if c.option_type == "call"})

    def quote_at(option_type, K):
        for c in chain:
            if c.option_type == option_type and c.strike == K:
                return c
        return None

    def build_leg(option_type, candidate_strikes, target_delta, side):
        K = match_strike_by_delta(candidate_strikes, option_type, S, T, sigma, target_delta, r)
        q = quote_at(option_type, K) if K is not None else None
        if q is not None and q.price > 0:
            delta = bs_delta(S, K, T, sigma, option_type, r)
            return OptionLegPrice(option_type, round(K, 2), side, round(q.price, 4), True, delta)
        # fall back to a synthetic price for this leg only. `target_delta` arrives here
        # already correctly signed (negative for puts, positive for calls) by the call
        # sites below, so it's passed straight through — no re-negation.
        K_fallback = K if K is not None else strike_for_delta(S, T, sigma, option_type, target_delta, r)
        price = bs_price(S, K_fallback, T, sigma, option_type, r)
        delta = bs_delta(S, K_fallback, T, sigma, option_type, r)
        return OptionLegPrice(option_type, round(K_fallback, 2), side, round(price, 4), False, delta)

    short_put = build_leg("put", puts, -short_delta_target, "sell")
    # long legs must be strictly further OTM than the short strike; if the real chain
    # doesn't extend that far, fall through to a synthetic price rather than reusing a
    # candidate that collides with (or sits on the wrong side of) the short strike.
    long_put = build_leg("put", [k for k in puts if k < short_put.strike], -lp_target, "buy")
    short_call = build_leg("call", calls, short_delta_target, "sell")
    long_call = build_leg("call", [k for k in calls if k > short_call.strike], lc_target, "buy")

    # Final safety clamp: even a synthetic fallback strike must be strictly further OTM
    # than its own short leg (mirrors the clamp in price_iron_condor()).
    if long_put.strike >= short_put.strike:
        K = min(long_put.strike, short_put.strike - 0.5)
        long_put = OptionLegPrice("put", round(K, 2), "buy",
                                   round(bs_price(S, K, T, sigma, "put", r), 4), False,
                                   bs_delta(S, K, T, sigma, "put", r))
    if long_call.strike <= short_call.strike:
        K = max(long_call.strike, short_call.strike + 0.5)
        long_call = OptionLegPrice("call", round(K, 2), "buy",
                                    round(bs_price(S, K, T, sigma, "call", r), 4), False,
                                    bs_delta(S, K, T, sigma, "call", r))

    net_credit = (short_put.price - long_put.price) + (short_call.price - long_call.price)
    max_loss = _bounded_max_loss(short_put.strike, long_put.strike, short_call.strike, long_call.strike, net_credit)
    real_quoted_legs = sum(leg.is_real_quote for leg in (short_put, long_put, short_call, long_call))

    return IronCondorLegs(short_put, long_put, short_call, long_call, net_credit, max_loss,
                           real_quoted_legs, expiry)
