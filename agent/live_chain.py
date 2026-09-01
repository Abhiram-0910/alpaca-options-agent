"""Fetches a real option-chain snapshot for one target expiry via Alpaca's MCP
server, shared by the deterministic executor and the skew observer.

get_option_chain's `limit` caps total snapshots returned, and dense names
(SPY/QQQ, with many weekly expiries) can blow through that cap before ever
reaching the expiry you actually want — verified against a live account: an
unbounded SPY query returned only expiries within ~10 days, even with a
narrow strike range, because SPY alone has that many listed contracts per
expiry. The fix is two passes: first discover which expiries exist at all
using a narrow near-the-money strike band (cheap — few contracts per expiry),
then fetch the one chosen expiry's full desired strike range on its own
(also cheap — one expiry's worth of contracts, not the whole window's).
"""
import json
from datetime import date, timedelta
from typing import Optional

from agent.backtest.iron_condor import nearest_expiry
from agent.mcp_parsers import parse_option_chain_snapshot


async def fetch_target_expiry_chain(
    mcp, symbol: str, S: float, target_dte: int, min_dte: int, max_dte: int,
    strike_lo: float, strike_hi: float,
) -> tuple:
    """Returns (target_expiry: date | None, chain: list[ChainQuote]). Empty chain,
    None expiry if nothing was found in the window."""
    expiry_lo = (date.today() + timedelta(days=min_dte)).isoformat()
    expiry_hi = (date.today() + timedelta(days=max_dte)).isoformat()

    # Pass 1: discover available expiries with a narrow near-the-money band, so a
    # dense name's many expirations don't blow through the row cap before we ever
    # see the later ones.
    discover_raw = await mcp.call_tool("get_option_chain", {
        "underlying_symbol": symbol,
        "expiration_date_gte": expiry_lo,
        "expiration_date_lte": expiry_hi,
        "strike_price_gte": round(S * 0.95, 2),
        "strike_price_lte": round(S * 1.05, 2),
        "limit": 1000,
    })
    try:
        discover_chain = parse_option_chain_snapshot(discover_raw)
    except (json.JSONDecodeError, TypeError):
        return None, []
    available_expiries = sorted({c.expiry for c in discover_chain})
    target_expiry = nearest_expiry(available_expiries, target_dte)
    if target_expiry is None:
        return None, []

    # Pass 2: fetch the desired (usually wider) strike range for that one expiry only.
    target_raw = await mcp.call_tool("get_option_chain", {
        "underlying_symbol": symbol,
        "expiration_date": target_expiry.isoformat(),
        "strike_price_gte": round(strike_lo, 2),
        "strike_price_lte": round(strike_hi, 2),
        "limit": 1000,
    })
    try:
        chain = parse_option_chain_snapshot(target_raw)
    except (json.JSONDecodeError, TypeError):
        return target_expiry, []
    return target_expiry, chain
