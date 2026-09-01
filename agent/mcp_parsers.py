"""Parsers for Alpaca MCP server tool responses, shared across the
deterministic executor, the live chain fetcher, and the skew observer.

Every Alpaca MCP tool result is wrapped as {"_alpaca_mcp_security": ...,
"data": ...} — these functions unwrap that envelope and pull out the shape
each specific tool actually returns underneath it (verified against a live
account for every tool used here; the exact nesting differs per tool, see
each function's docstring).
"""
import json

from agent.risk.gates import parse_occ_symbol
from agent.backtest.iron_condor import ChainQuote


def parse_latest_trade_price(raw: str) -> float:
    """get_stock_latest_trade: data.trades.<SYMBOL>.p"""
    data = json.loads(raw)
    inner = data.get("data", data)
    trades = inner.get("trades") or inner
    for _, t in (trades.items() if isinstance(trades, dict) else []):
        return float(t.get("p") or t.get("price"))
    raise ValueError(f"could not parse latest trade price from: {raw[:300]}")


def parse_bars_closes(raw: str, symbol: str) -> list:
    """get_stock_bars: data.bars.<SYMBOL> = [{"c": close, ...}, ...]"""
    data = json.loads(raw)
    inner = data.get("data", data)
    bars = inner.get("bars", inner)
    series = bars.get(symbol, []) if isinstance(bars, dict) else bars
    return [float(b["c"]) for b in series if "c" in b]


def parse_option_chain_snapshot(raw: str) -> list:
    """get_option_chain: data.snapshots = {OCC_SYMBOL: {...snapshot...}, ...}.
    Flattens into ChainQuote objects, preferring the live bid/ask mid over the
    daily bar close, and carrying Alpaca's own reported delta when present."""
    data = json.loads(raw)
    inner = data.get("data", data)
    snapshots = inner.get("snapshots", {})
    quotes = []
    for occ_symbol, snap in snapshots.items():
        parsed = parse_occ_symbol(occ_symbol)
        if not parsed:
            continue
        quote = snap.get("latestQuote") or {}
        bid, ask = quote.get("bp"), quote.get("ap")
        if bid and ask and bid > 0 and ask > 0:
            price = (bid + ask) / 2
        else:
            daily = snap.get("dailyBar") or {}
            price = daily.get("c")
        if not price or price <= 0:
            continue
        greeks = snap.get("greeks") or {}
        quotes.append(ChainQuote(
            strike=parsed["strike"], option_type=parsed["option_type"], price=round(float(price), 4),
            expiry=parsed["expiration"], bid=bid, ask=ask, symbol=occ_symbol, delta=greeks.get("delta"),
            implied_vol=snap.get("impliedVolatility"),
        ))
    return quotes
