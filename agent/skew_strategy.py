"""IV put/call skew mean-reversion — a genuinely different signal from VRP's
volatility-*level* edge (agent/backtest/engine.py's iron_condor variants):
this bets on skew *richening/cheapening* relative to its own recent history,
not on the level of volatility itself.

Unlike VRP, this cannot be backtested offline with what this project has: the
synthetic backtest path prices off realized volatility because full
historical options chains aren't reliably available, but skew is a property
of the *implied* vol surface specifically — there's no realized-vol proxy for
skew the way there is for a vol level. So this module only ever *observes*:
it records real quoted IV (Alpaca's own greeks/impliedVolatility, not a
Black-Scholes estimate) into a persisted history file, and only produces a
signal once that history is long enough to compute a meaningful trailing
mean/stdev. It never places an order and is never wired into the lifecycle
registry's cleared_for_paper list — there is no statistical validation gate
this can pass, because there is no backtest to run it against. Treat any
signal it produces as informational until proven out over real paper-traded
history, not as something to trade automatically.
"""
import json
import os
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from agent.config import CONFIG
from agent.mcp.client import AlpacaMCPClient
from agent.mcp_parsers import parse_latest_trade_price
from agent.live_chain import fetch_target_expiry_chain

HISTORY_PATH = os.path.join(CONFIG.logs_dir, "skew_history.jsonl")
TARGET_DELTA = 0.25
TARGET_DTE = 30
MIN_OBSERVATIONS = 20   # minimum trailing readings before a signal is trusted at all
Z_THRESHOLD = 1.5       # |z-score| beyond which current skew counts as "unusually" rich/cheap


@dataclass
class SkewObservation:
    ts: str
    symbol: str
    expiry: str
    spot: float
    put_iv: float
    call_iv: float
    skew: float   # put_iv - call_iv


def _nearest_by_delta(chain: list, option_type: str, target_delta: float):
    candidates = [c for c in chain if c.option_type == option_type and c.delta is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs(c.delta - target_delta))


async def observe_symbol(mcp: AlpacaMCPClient, symbol: str) -> Optional[SkewObservation]:
    price_raw = await mcp.call_tool("get_stock_latest_trade", {"symbols": symbol})
    try:
        S = parse_latest_trade_price(price_raw)
    except (ValueError, KeyError, TypeError):
        return None

    target_expiry, same_expiry = await fetch_target_expiry_chain(
        mcp, symbol, S, TARGET_DTE, CONFIG.min_days_to_expiration, CONFIG.max_days_to_expiration,
        strike_lo=S * 0.7, strike_hi=S * 1.3,
    )
    if not same_expiry:
        return None

    put = _nearest_by_delta(same_expiry, "put", -TARGET_DELTA)
    call = _nearest_by_delta(same_expiry, "call", TARGET_DELTA)
    if put is None or call is None or put.implied_vol is None or call.implied_vol is None:
        return None

    return SkewObservation(
        ts=datetime.now(timezone.utc).isoformat(), symbol=symbol, expiry=target_expiry.isoformat(),
        spot=S, put_iv=put.implied_vol, call_iv=call.implied_vol,
        skew=round(put.implied_vol - call.implied_vol, 5),
    )


def _append(obs: SkewObservation) -> None:
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    with open(HISTORY_PATH, "a") as f:
        f.write(json.dumps(asdict(obs)) + "\n")


def _load_history(symbol: str) -> list:
    if not os.path.exists(HISTORY_PATH):
        return []
    out = []
    with open(HISTORY_PATH) as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("symbol") == symbol:
                out.append(d["skew"])
    return out


def signal_for(symbol: str, current_skew: float) -> dict:
    """Purely informational — never call this to decide a trade on its own."""
    history = _load_history(symbol)
    if len(history) < MIN_OBSERVATIONS:
        return {"symbol": symbol, "status": "insufficient_history",
                "observations": len(history), "need": MIN_OBSERVATIONS}
    mean = statistics.mean(history)
    stdev = statistics.pstdev(history) if len(history) > 1 else 0.0
    z = (current_skew - mean) / stdev if stdev > 1e-6 else 0.0
    if abs(z) < Z_THRESHOLD:
        return {"symbol": symbol, "status": "no_signal", "z_score": round(z, 3),
                "current_skew": current_skew, "mean_skew": round(mean, 5), "observations": len(history)}
    direction = "rich" if z > 0 else "cheap"
    return {"symbol": symbol, "status": "signal", "direction": direction, "z_score": round(z, 3),
            "current_skew": current_skew, "mean_skew": round(mean, 5), "observations": len(history)}


async def record_all_observations(symbols=None) -> list:
    """Records one real skew observation per symbol. Never places an order."""
    symbols = symbols or list(CONFIG.watchlist)
    results = []
    async with AlpacaMCPClient() as mcp:
        for symbol in symbols:
            obs = await observe_symbol(mcp, symbol)
            if obs is None:
                results.append({"symbol": symbol, "status": "no_data"})
                continue
            _append(obs)
            sig = signal_for(symbol, obs.skew)
            sig["observation"] = asdict(obs)
            results.append(sig)
    return results
