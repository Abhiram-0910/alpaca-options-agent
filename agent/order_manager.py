"""Order & position management — the part of the pipeline that runs *after*
entries have been opened. Every trading path in this project (live_agent,
multi_agent, deterministic_agent) only ever opens positions; nothing else
tracks what's already open, cancels stale unfilled orders, or closes
positions that have hit a profit target, a stop-loss, or expiration risk.
A strategy that only knows how to enter isn't a complete trading system —
this is what actually closes the loop.

v1 scope, disclosed honestly: these are universal, strategy-agnostic rules
(DTE force-close, %-based stop-loss/profit-take on Alpaca's own reported
unrealized P&L), not each strategy's own backtested exit rule (e.g.
iron_condor_vrp_45_21's specific 21-DTE-managed exit + 2x-credit stop from
agent/backtest/engine.py). A strategy-aware version would cross-reference
logs/trade_log.jsonl to recover which strategy opened each position and
apply its exact rule — noted as a next step, not attempted here, rather than
shipping a fragile partial version of it.

Closing positions is deliberately NOT gated by the kill switch: a kill switch
exists to stop new risk-taking, not to freeze risk-reduction — if something
is wrong enough to hit the kill switch, the user still wants open positions
manageable, not frozen. New order cancellation, on the other hand, is a
housekeeping action independent of that judgment call and always runs.
"""
import json
from datetime import date, datetime, timezone

from agent.config import CONFIG, assert_paper_trading
from agent.mcp.client import AlpacaMCPClient
from agent.risk.gates import parse_occ_symbol
from agent.trade_log import log_event
from agent.alerts import alert


def _close_order_args(symbol: str, side: str, qty: float, current_price: float) -> dict:
    """Alpaca rejects market orders on thinly-quoted options ("no available quote for
    symbol, please reenter with a limit") — verified live. Always uses a marketable limit
    instead: aggressively through the last-known price so it's very likely to fill without
    literally crossing at $0, which some venues reject outright.
    """
    qty_str = str(int(qty)) if float(qty).is_integer() else str(qty)
    is_sell = side == "long"
    base = current_price if current_price and current_price > 0 else 0.02
    limit_price = round(max(base * 0.5, 0.01), 2) if is_sell else round(max(base * 1.5, 0.02), 2)
    return {
        "symbol": symbol,
        "side": "sell" if is_sell else "buy",
        "qty": qty_str,
        "type": "limit",
        "limit_price": str(limit_price),
        "position_intent": "sell_to_close" if is_sell else "buy_to_close",
        "client_order_id": f"close-{symbol}-{date.today().isoformat()}",
    }


async def _manage_positions(mcp) -> list:
    positions_raw = await mcp.call_tool("get_all_positions", {})
    positions = json.loads(positions_raw).get("data", {}).get("result", [])
    if not isinstance(positions, list):
        positions = []

    closed = []
    for pos in positions:
        symbol = pos.get("symbol", "")
        parsed = parse_occ_symbol(symbol)
        if not parsed:
            continue  # not an option leg (e.g. a covered-call's underlying shares) — leave alone

        dte = (parsed["expiration"] - date.today()).days
        qty = abs(float(pos.get("qty", 0) or 0))
        side = pos.get("side", "long")
        plpc = float(pos.get("unrealized_plpc", 0) or 0)
        current_price = float(pos.get("current_price", 0) or 0)

        reason = None
        if CONFIG.force_close_dte > 0 and dte <= CONFIG.force_close_dte:
            reason = f"within {CONFIG.force_close_dte} DTE of expiration (dte={dte})"
        elif CONFIG.position_stop_loss_pct > 0 and plpc <= -CONFIG.position_stop_loss_pct:
            reason = f"stop-loss: unrealized {plpc:.0%} <= -{CONFIG.position_stop_loss_pct:.0%}"
        elif CONFIG.position_profit_take_pct > 0 and plpc >= CONFIG.position_profit_take_pct:
            reason = f"profit-take: unrealized {plpc:.0%} >= {CONFIG.position_profit_take_pct:.0%}"

        if reason is None or qty <= 0:
            continue

        order_args = _close_order_args(symbol, side, qty, current_price)
        result_text = await mcp.call_tool("place_option_order", order_args)
        log_event("position_closed", symbol=symbol, reason=reason, dte=dte, plpc=plpc,
                   result=result_text[:1000])
        alert("position_closed", symbol=symbol, reason=reason, plpc=round(plpc, 4))
        closed.append({"symbol": symbol, "reason": reason, "plpc": round(plpc, 4)})

    return closed


async def _cancel_stale_orders(mcp) -> list:
    if CONFIG.stale_order_minutes <= 0:
        return []
    orders_raw = await mcp.call_tool("get_orders", {"status": "open"})
    orders = json.loads(orders_raw).get("data", {}).get("result", [])
    if not isinstance(orders, list):
        orders = []

    now = datetime.now(timezone.utc)
    canceled = []
    for order in orders:
        submitted_at = order.get("submitted_at")
        order_id = order.get("id")
        if not submitted_at or not order_id:
            continue
        try:
            submitted = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        age_minutes = (now - submitted).total_seconds() / 60
        if age_minutes < CONFIG.stale_order_minutes:
            continue

        result_text = await mcp.call_tool("cancel_order_by_id", {"order_id": order_id})
        log_event("order_canceled_stale", order_id=order_id, symbol=order.get("symbol"),
                   age_minutes=round(age_minutes, 1), result=result_text[:500])
        canceled.append({"order_id": order_id, "symbol": order.get("symbol"), "age_minutes": round(age_minutes, 1)})

    return canceled


async def manage_cycle() -> dict:
    assert_paper_trading()  # closing/canceling still only ever runs against paper, same as everything else

    async with AlpacaMCPClient() as mcp:
        # Cancel stale orders FIRST: an existing open order against a symbol ties up its
        # qty_available, so attempting a new close order before freeing that up can fail with
        # nothing available to sell/buy — verified against a live account with a stale
        # sell-to-close order still open on a position that also qualified for our stop-loss.
        orders_canceled = await _cancel_stale_orders(mcp)
        positions_closed = await _manage_positions(mcp)

    result = {"positions_closed": positions_closed, "orders_canceled": orders_canceled}
    log_event("order_management_cycle_complete", **result)
    return result
