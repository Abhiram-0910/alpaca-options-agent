"""Black-Scholes pricing/greeks used to simulate option payoffs for backtesting.

Real historical options chains (bid/ask across thousands of strikes/expirations,
years back) are expensive to pull and not reliably available for every symbol.
For strategy *comparison* purposes we instead price theoretical contracts off
real historical underlying prices (from Alpaca) and realized volatility, which
is a standard, defensible approximation for ranking strategy families before
committing a live agent to one of them.
"""
import math
from dataclasses import dataclass

RISK_FREE_RATE = 0.045  # approx short-term T-bill yield, used as the discount rate


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float):
    sigma = max(sigma, 1e-4)
    T = max(T, 1e-6)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def bs_price(S: float, K: float, T: float, sigma: float, option_type: str, r: float = RISK_FREE_RATE) -> float:
    """Theoretical Black-Scholes price of a European call/put."""
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    if option_type == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_delta(S: float, K: float, T: float, sigma: float, option_type: str, r: float = RISK_FREE_RATE) -> float:
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return _norm_cdf(d1) if option_type == "call" else _norm_cdf(d1) - 1.0


def strike_for_delta(S: float, T: float, sigma: float, option_type: str, target_delta: float,
                      r: float = RISK_FREE_RATE) -> float:
    """Bisection search for the strike whose BS delta matches target_delta.

    target_delta should be positive for calls (e.g. 0.30) and negative for
    puts (e.g. -0.30), matching how traders quote "delta" for short strikes.
    """
    lo, hi = S * 0.4, S * 2.5
    for _ in range(60):
        mid = (lo + hi) / 2.0
        d = bs_delta(S, mid, T, sigma, option_type, r)
        if option_type == "call":
            # delta decreases monotonically as strike increases
            if d > target_delta:
                lo = mid
            else:
                hi = mid
        else:
            # put delta decreases (becomes more negative) as strike increases
            if d < target_delta:
                hi = mid
            else:
                lo = mid
    return round((lo + hi) / 2.0, 2)


def realized_vol(closes: list, window: int = 20) -> float:
    """Annualized realized volatility from the trailing `window` daily closes."""
    if len(closes) < window + 1:
        window = max(len(closes) - 1, 1)
    tail = closes[-(window + 1):]
    rets = [math.log(tail[i] / tail[i - 1]) for i in range(1, len(tail)) if tail[i - 1] > 0]
    if len(rets) < 2:
        return 0.25  # fallback: broad-market-ish default
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return max(math.sqrt(var) * math.sqrt(252), 0.05)


@dataclass
class ContractQuote:
    strike: float
    option_type: str
    price: float
    delta: float
