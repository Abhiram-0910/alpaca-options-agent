"""Parsers for Alpaca MCP server tool responses, shared across the
deterministic executor, the live chain fetcher, and the skew observer.

Every Alpaca MCP tool result is wrapped as {"_alpaca_mcp_security": ...,
"data": ...} — these functions unwrap that envelope and pull out the shape
each specific tool actually returns underneath it (verified against a live
account for every tool used here; the exact nesting differs per tool, see
each function's docstring).
"""
import json
from typing import Optional

from agent.risk.gates import parse_occ_symbol
from agent.backtest.iron_condor import ChainQuote


def parse_latest_trade_price(raw: str) -> float:
    """get_stock_latest_trade: data.trades.<SYMBOL>.p"""
    data = json.loads(raw)
    inner = data.get("data", data)
    trades = inner.get("trades") or inner
    # `trades` degrades to `inner` itself on an error-shaped response (e.g.
    # {"error": "..."}), so its values aren't guaranteed to be dicts -- unlike
    # parse_bars_closes/parse_option_chain_snapshot, which already guard this and
    # degrade to []/{}, an unguarded `t.get(...)` here used to raise a bare
    # AttributeError that callers' `except (ValueError, KeyError, TypeError)` never
    # catches, crashing the whole cycle/run instead of just skipping this one symbol.
    if isinstance(trades, dict):
        for _, t in trades.items():
            if isinstance(t, dict):
                price = t.get("p") or t.get("price")
                if price is not None:
                    return float(price)
    raise ValueError(f"could not parse latest trade price from: {raw[:300]}")


def parse_order_error(raw: str) -> Optional[str]:
    """place_option_order (or any other order-placing tool): Alpaca rejecting an order is NOT
    surfaced as an MCP-level error/exception -- the installed alpaca-mcp-server catches the
    API error itself and returns a normal, non-throwing result shaped
    {"error": {"message": ..., "http_status": ..., "detail": ...}} (confirmed against the
    installed package's overrides.py: _post_order() returns that dict on a non-2xx response
    instead of raising). Every order-placing call site in this codebase used to log/alert/
    record a rejected order exactly like a successfully placed one because nothing ever
    checked for this -- for a multi-leg strategy submitted as sequential single-leg orders,
    that meant a rejected protective "buy" leg didn't stop the following "sell" leg from
    still being submitted, silently creating the naked exposure the buy-first ordering exists
    to prevent. Returns the rejection message, or None if `raw` doesn't look like a rejection.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    inner = data.get("data", data)
    err = (inner.get("error") if isinstance(inner, dict) else None) or data.get("error")
    if isinstance(err, dict):
        return err.get("message") or json.dumps(err)[:300]
    if isinstance(err, str):
        return err
    return None


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
