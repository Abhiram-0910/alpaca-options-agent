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
from agent import fill_analysis
from agent.reflection import record_closed_position
from agent.alerts import alert
from agent.mcp_parsers import parse_order_error
from agent.session_window import must_be_flat


def _unwrap_result_list(raw: str, context: str) -> list:
    """Unwraps a get_all_positions/get_orders response's data.result list. On an MCP-level
    failure (agent/mcp/client.py returns {"error": text} when the tool call itself errors,
    e.g. auth/rate-limit/network), this used to be unguarded: `.get(...)` doesn't raise on
    that shape, it just silently resolves to [] since there's no "data" key -- which
    reintroduces the exact stale-close-order race symbols_with_open_orders exists to prevent,
    and can quietly skip a position that needed closing, with nothing logged. Alerts instead of
    raising, so one failed call doesn't abort the *other*, independent housekeeping step in the
    same cycle (order cancellation vs. position management each fetch their own order/position
    list)."""
    data = json.loads(raw)
    if isinstance(data, dict) and isinstance(data.get("error"), (str, dict)):
        alert("mcp_call_failed", context=context, error=data["error"])
        log_event("mcp_call_failed", context=context, error=data["error"])
        return []
    result = data.get("data", {}).get("result", [])
    return result if isinstance(result, list) else []


def _order_symbols(order: dict) -> set:
    """Every OCC symbol an order touches. A single-leg order carries its symbol at the top
    level; an mleg parent carries "" there and the real symbols on order["legs"]."""
    symbols = {order.get("symbol")} if order.get("symbol") else set()
    for leg in order.get("legs") or []:
        if isinstance(leg, dict) and leg.get("symbol"):
            symbols.add(leg["symbol"])
    return symbols


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


async def _pre_close_quote(mcp, symbol: str) -> dict:
    """Indicative bid/ask/mid for one contract, shaped for fill_analysis.compare().

    Returns {} on any failure -- a missing pre-close quote must never stop a close.
    """
    try:
        raw = await mcp.call_tool("get_option_latest_quote", {"symbol_or_symbols": symbol})
        data = json.loads(raw).get("data") or {}
        quotes = data.get("quotes") or data
        q = quotes.get(symbol) if isinstance(quotes, dict) else None
        if not isinstance(q, dict):
            return {}
        bid, ask = q.get("bp"), q.get("ap")
        mid = None
        if bid is not None and ask is not None:
            try:
                mid = round((float(bid) + float(ask)) / 2, 4)
            except (TypeError, ValueError):
                mid = None
        return {symbol: {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "bid": bid, "ask": ask, "mid": mid,
            "feed": "Alpaca Indicative Pricing Feed, not OPRA",
            "on_chain": True,
        }}
    except Exception:
        return {}


def _order_id_from(result_text: str):
    """Alpaca's order id out of an MCP place_option_order response, or None."""
    try:
        return (json.loads(result_text).get("data") or {}).get("id")
    except (ValueError, AttributeError, TypeError):
        return None


async def _manage_positions(mcp) -> list:
    positions_raw = await mcp.call_tool("get_all_positions", {})
    positions = _unwrap_result_list(positions_raw, context="manage_positions.get_all_positions")

    # Symbols with an order still open right now (not yet stale enough for
    # _cancel_stale_orders, which runs before this and only cancels orders older than
    # STALE_ORDER_MINUTES). Without this check, a position whose close order hasn't
    # filled yet gets ANOTHER close order submitted on top of it every single cycle —
    # verified live: on an illiquid contract this resubmitted every ~10 seconds across
    # manual test runs, and on a real --loop interval would do the same every cycle,
    # unnecessarily crossing the spread again each time (the real cost of over-trading,
    # even though Alpaca charges $0 commission on options).
    open_orders_raw = await mcp.call_tool("get_orders", {"status": "open"})
    open_orders = _unwrap_result_list(open_orders_raw, context="manage_positions.get_orders")
    # Guard each element, not just the container: a non-dict entry in open_orders would raise
    # AttributeError on .get() and abort this whole cycle's position management uncaught.
    symbols_with_open_orders = set()
    for o in open_orders:
        if not isinstance(o, dict):
            continue
        # An mleg parent order comes back with symbol "" and side "" -- the real OCC symbols
        # live on its legs (verified against the judged account, probe_mleg.py). Reading only
        # the top level put "" in this set, which matches no position, so the guard below
        # stopped working and every cycle piled another close order onto a spread that had
        # not filled yet.
        symbols_with_open_orders.update(_order_symbols(o))

    closed = []
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        symbol = pos.get("symbol", "")
        parsed = parse_occ_symbol(symbol)
        if not parsed:
            continue  # not an option leg (e.g. a covered-call's underlying shares) — leave alone

        if symbol in symbols_with_open_orders:
            continue  # already has a pending close order this cycle; let it fill or go stale first

        side = pos.get("side")
        if side not in ("long", "short"):
            # Don't guess: _close_order_args's sell/buy direction is derived directly from this,
            # and a wrong guess on a genuinely short position would submit a close order in the
            # wrong direction. Fail safe by skipping this position rather than assuming "long".
            log_event("position_management_skipped", symbol=symbol,
                       reason=f"unrecognized position side {side!r}")
            continue

        dte = (parsed["expiration"] - date.today()).days
        qty = abs(float(pos.get("qty", 0) or 0))
        plpc = float(pos.get("unrealized_plpc", 0) or 0)
        current_price = float(pos.get("current_price", 0) or 0)

        reason = None
        # The dated NFP flat rule outranks every other exit: it is a decision about a
        # scheduled event, not a reaction to this position's P&L. Logged with its own event
        # type so the demo and write-up can point at the agent choosing to stand down rather
        # than at an account that merely happens to be empty.
        flat_reason = must_be_flat()
        if flat_reason:
            reason = f"session window: {flat_reason}"
            log_event("nfp_flat_rule", symbol=symbol, dte=dte, plpc=plpc, reason=flat_reason)
        elif CONFIG.force_close_dte > 0 and dte <= CONFIG.force_close_dte:
            reason = f"within {CONFIG.force_close_dte} DTE of expiration (dte={dte})"
        elif CONFIG.position_stop_loss_pct > 0 and plpc <= -CONFIG.position_stop_loss_pct:
            reason = f"stop-loss: unrealized {plpc:.0%} <= -{CONFIG.position_stop_loss_pct:.0%}"
        elif CONFIG.position_profit_take_pct > 0 and plpc >= CONFIG.position_profit_take_pct:
            reason = f"profit-take: unrealized {plpc:.0%} >= {CONFIG.position_profit_take_pct:.0%}"

        if reason is None or qty <= 0:
            continue

        order_args = _close_order_args(symbol, side, qty, current_price)

        # Indicative quote immediately BEFORE the close, so the exit is measured on the same
        # footing as the entry. Without this the dashboard showed a position that opened and
        # never closed: fill_analysis and trades[] only ever saw the demonstration path, and
        # the realised P&L -- the strongest sequence in the run -- was invisible.
        #
        # One extra read on the close path is affordable in a way it would not be on entry:
        # the exit is already committed by the time we get here, and a quote that fails to
        # arrive degrades to None rather than blocking the close.
        quote_snapshot = await _pre_close_quote(mcp, symbol)

        result_text = await mcp.call_tool("place_option_order", order_args)
        # Alpaca rejecting an order is a normal (non-error) MCP result, not an exception -- see
        # parse_order_error's docstring. Without this check, a rejected close order was still
        # logged as "position_closed" and recorded into the reflection log as a real exit, even
        # though the position is still open and still at risk (it would only be picked back up
        # for management on the *next* cycle's fresh position fetch).
        order_error = parse_order_error(result_text)
        event = "position_close_rejected" if order_error else "position_closed"
        log_event(event, symbol=symbol, reason=reason, dte=dte, plpc=plpc,
                   result=result_text[:1000], error=order_error)
        if order_error:
            alert("position_close_rejected", symbol=symbol, reason=reason, error=order_error)
            continue  # not actually closed -- leave it for the next cycle to retry
        alert("position_closed", symbol=symbol, reason=reason, plpc=round(plpc, 4))
        # Records against the last-seen unrealized P&L at the moment the close was submitted,
        # not a confirmed fill price — close enough for a limit order sized off current_price,
        # and simpler than tracking async fills; disclosed as an approximation, not exact.
        record_closed_position(symbol, exit_reason=reason, plpc=round(plpc, 4))

        # The closing order as a trade row in its own right, carrying the reason it was
        # closed -- for the NFP flatten that reason is the whole point of the record.
        close_order_id = _order_id_from(result_text)
        log_event("position_close_order", symbol=symbol, reason=reason, dte=dte,
                  plpc=round(plpc, 4), side=order_args.get("side"),
                  position_intent=order_args.get("position_intent"),
                  limit_price=order_args.get("limit_price"), qty=order_args.get("qty"),
                  order_id=close_order_id, result=result_text[:800])
        if close_order_id:
            # Never allowed to affect the close: record() swallows its own errors, and this
            # runs after Alpaca has already accepted the order.
            fill_analysis.record(close_order_id, quote_snapshot or {},
                                 context=f"position_close: {reason}")
        closed.append({"symbol": symbol, "reason": reason, "plpc": round(plpc, 4),
                       "order_id": close_order_id})

    return closed


async def _cancel_stale_orders(mcp) -> list:
    if CONFIG.stale_order_minutes <= 0:
        return []
    orders_raw = await mcp.call_tool("get_orders", {"status": "open"})
    orders = _unwrap_result_list(orders_raw, context="cancel_stale_orders.get_orders")

    now = datetime.now(timezone.utc)
    canceled = []
    for order in orders:
        if not isinstance(order, dict):
            continue
        submitted_at = order.get("submitted_at")
        order_id = order.get("id")
        if not submitted_at or not order_id:
            continue
        try:
            submitted = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
            age_minutes = (now - submitted).total_seconds() / 60
        except (ValueError, TypeError):
            # TypeError specifically: fromisoformat succeeding but returning a naive datetime
            # (no "Z"/offset in submitted_at) makes `now - submitted` raise, since `now` is
            # timezone-aware -- that used to be uncaught, aborting stale-order cancellation
            # (and, since it's called first, position management too) for every order this
            # cycle over one malformed timestamp instead of just skipping that one order.
            continue
        if age_minutes < CONFIG.stale_order_minutes:
            continue

        result_text = await mcp.call_tool("cancel_order_by_id", {"order_id": order_id})
        # A rejected cancellation (e.g. the order already filled/canceled between the get_orders
        # snapshot and this call) comes back as a normal non-error MCP result too -- without this
        # check it was unconditionally reported and counted as canceled, when Alpaca may not have
        # actually canceled anything.
        cancel_error = parse_order_error(result_text)
        event = "order_cancel_rejected" if cancel_error else "order_canceled_stale"
        order_symbols = sorted(_order_symbols(order))
        log_event(event, order_id=order_id, symbol=order_symbols,
                   age_minutes=round(age_minutes, 1), result=result_text[:500], error=cancel_error)
        if cancel_error:
            alert("order_cancel_rejected", order_id=order_id, symbol=order_symbols, error=cancel_error)
            continue  # not actually canceled -- still open, and still ties up qty_available
        canceled.append({"order_id": order_id, "symbol": order_symbols, "age_minutes": round(age_minutes, 1)})

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
