"""Does Alpaca's paper fill engine price against fresher data than the feed we can see?

Open question. The free tier's option quotes come from the Indicative Pricing Feed -- a
derived, deliberately randomised product, not OPRA -- and nothing in the documentation says
whether the paper fill simulator draws on the same thing. If it prices against fresher or
truer data, every backtest and every expected-credit calculation in this project is
systematically off in a direction we could measure but have not.

This instruments the answer rather than arguing it: for every order submitted, the
indicative quote for each leg immediately before submission, the simulated fill price
after, and the signed delta between them.

It is deliberately off the critical path. The pre-trade quote is read from the chain
snapshot the caller *already fetched to build the order* -- no extra round trip, no added
latency, nothing new that can fail between the decision and the submission. The cost is a
timing gap between when that chain was read and when the order went in, so the gap is
measured and recorded (`capture_lag_seconds`) rather than hidden. The fill side is read
after submission, where latency is free.

A delta is only meaningful on a real fill. Nothing here fabricates one: an unfilled or
canceled order yields a record with `filled_price: null` and `delta: null`.
"""
import json
import os
from datetime import datetime, timezone

from agent.config import CONFIG
from agent.trade_log import log_event


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def capture_quotes(chain, symbols) -> dict:
    """Indicative bid/ask/mid per leg, taken from a chain the caller already has.

    Returns {symbol: {...}} with the capture timestamp, so the lag to submission can be
    measured. Symbols absent from the chain are recorded as null rather than skipped -- a
    missing pre-trade quote is itself a finding.
    """
    captured_at = datetime.now(timezone.utc).isoformat()
    by_symbol = {getattr(q, "symbol", None): q for q in (chain or [])
                 if getattr(q, "symbol", None)}
    snapshot = {}
    for sym in symbols:
        q = by_symbol.get(sym)
        snapshot[sym] = {
            "captured_at": captured_at,
            "bid": _num(getattr(q, "bid", None)) if q else None,
            "ask": _num(getattr(q, "ask", None)) if q else None,
            "mid": _num(getattr(q, "price", None)) if q else None,
            "feed": "Alpaca Indicative Pricing Feed, not OPRA",
            "on_chain": q is not None,
        }
    return snapshot


def fetch_order(order_id: str):
    """The submitted order with its legs, read back through the Alpaca CLI. None on failure."""
    from agent import alpaca_cli
    data = alpaca_cli._run("order", "get", "--order-id", order_id, "--nested")
    return data if isinstance(data, dict) else None


def _lag_seconds(captured_at, filled_at):
    if not captured_at or not filled_at:
        return None
    try:
        a = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(filled_at).replace("Z", "+00:00"))
        return round((b - a).total_seconds(), 3)
    except ValueError:
        return None


def compare(snapshot: dict, order: dict) -> list:
    """Per-leg indicative-vs-fill records. One per leg, filled or not."""
    if not isinstance(order, dict):
        return []
    legs = order.get("legs")
    if not isinstance(legs, list) or not legs:
        legs = [order]
    submitted_at = order.get("submitted_at")

    records = []
    for leg in legs:
        if not isinstance(leg, dict):
            continue
        sym = leg.get("symbol")
        quote = snapshot.get(sym) or {}
        mid = quote.get("mid")
        fill = _num(leg.get("filled_avg_price"))
        filled_qty = _num(leg.get("filled_qty")) or 0.0
        # An order can carry a filled_avg_price of 0 while unfilled; require real quantity.
        if filled_qty <= 0:
            fill = None
        delta = None if (fill is None or mid is None) else round(fill - mid, 4)
        records.append({
            "symbol": sym,
            "side": leg.get("side"),
            "position_intent": leg.get("position_intent"),
            "indicative_bid": quote.get("bid"),
            "indicative_ask": quote.get("ask"),
            "indicative_mid": mid,
            "quote_captured_at": quote.get("captured_at"),
            "on_chain": quote.get("on_chain"),
            "filled_price": fill,
            "filled_qty": filled_qty,
            "filled_at": leg.get("filled_at"),
            "status": leg.get("status"),
            "delta": delta,
            # Sign convention stated so it cannot be read backwards: positive means the fill
            # printed ABOVE the indicative mid we could see.
            "delta_sign": None if delta is None else ("above_mid" if delta > 0
                                                       else "below_mid" if delta < 0 else "at_mid"),
            "capture_lag_seconds": _lag_seconds(quote.get("captured_at"),
                                                 leg.get("filled_at") or submitted_at),
        })
    return records


def record(order_id: str, snapshot: dict, context: str = None) -> dict:
    """Read the order back, compare, log and return. Never raises: this is instrumentation,
    and an order that filled must not be reported as failed because a measurement did."""
    try:
        order = fetch_order(order_id)
        legs = compare(snapshot, order) if order else []
        entry = {
            "order_id": order_id,
            "context": context,
            "order_status": (order or {}).get("status"),
            "legs": legs,
            "legs_filled": sum(1 for l in legs if l["filled_price"] is not None),
            "error": None if order else "could not read the order back",
        }
    except Exception as exc:
        entry = {"order_id": order_id, "context": context, "order_status": None, "legs": [],
                 "legs_filled": 0, "error": f"{type(exc).__name__}: {exc}"}
    log_event("fill_analysis", **entry)
    return entry


def realised_pnl(entries: list) -> dict:
    """Realised P&L from the signed cash flow of every filled leg.

    No entry/exit pairing is needed, and deliberately so: a sell brings cash in and a buy
    takes it out, whether the leg is opening or closing, so summing signed cash flows over
    all filled legs gives the realised result directly and cannot mis-pair a spread.

    Only closed round trips are meaningful here. `legs_open` counts opening fills without a
    matching close, and while that is non-zero the total is a running figure, not a result.
    """
    flows, opened, closed = [], 0, 0
    for e in entries:
        for leg in (e.get("legs") or []):
            price, qty = leg.get("filled_price"), leg.get("filled_qty") or 0
            if price is None or not qty:
                continue
            side = (leg.get("side") or "").lower()
            if side not in ("buy", "sell"):
                continue
            sign = 1.0 if side == "sell" else -1.0
            flows.append({
                "symbol": leg.get("symbol"),
                "side": side,
                "position_intent": leg.get("position_intent"),
                "price": price,
                "qty": qty,
                "cash": round(sign * float(price) * 100 * float(qty), 2),
            })
            intent = (leg.get("position_intent") or "").lower()
            if intent.endswith("_open"):
                opened += 1
            elif intent.endswith("_close"):
                closed += 1
    total = round(sum(f["cash"] for f in flows), 2)
    return {
        "legs_counted": len(flows),
        "opening_legs": opened,
        "closing_legs": closed,
        "legs_open": max(opened - closed, 0),
        "round_trip_complete": opened > 0 and opened == closed,
        "realised_pnl_dollars": total if flows else None,
        "method": ("signed cash flow over every filled leg: sell is cash in, buy is cash out. "
                   "Gross of fees -- Alpaca's per-contract fees are not in the fill prices."),
        "cash_flows": flows,
    }


def demo() -> None:
    """Self-check: the arithmetic, the sign convention, and the unfilled case."""
    class Q:
        def __init__(self, symbol, bid, ask, price):
            self.symbol, self.bid, self.ask, self.price = symbol, bid, ask, price

    chain = [Q("SPY260904P00751000", 0.40, 0.50, 0.45),
             Q("SPY260904P00756000", 1.10, 1.20, 1.15)]
    snap = capture_quotes(chain, ["SPY260904P00751000", "SPY260904P00756000", "SPY260904P00999000"])
    assert snap["SPY260904P00751000"]["mid"] == 0.45
    # A leg absent from the chain is recorded as such, not dropped.
    assert snap["SPY260904P00999000"]["on_chain"] is False
    assert snap["SPY260904P00999000"]["mid"] is None

    # captured_at is pinned rather than left as "now": comparing a live timestamp against a
    # hardcoded fill time made this assertion pass only while the wall clock was before
    # 14:00 UTC, and it started failing mid-session for no reason connected to the code.
    for q in snap.values():
        q["captured_at"] = "2026-09-03T14:00:05+00:00"
    order = {"status": "filled", "submitted_at": "2026-09-03T14:00:05+00:00", "legs": [
        {"symbol": "SPY260904P00751000", "side": "buy", "filled_avg_price": "0.52",
         "filled_qty": "1", "filled_at": "2026-09-03T14:00:06+00:00", "status": "filled"},
        {"symbol": "SPY260904P00756000", "side": "sell", "filled_avg_price": "1.09",
         "filled_qty": "1", "filled_at": "2026-09-03T14:00:06+00:00", "status": "filled"},
    ]}
    legs = compare(snap, order)
    assert legs[0]["delta"] == 0.07 and legs[0]["delta_sign"] == "above_mid", legs[0]
    assert legs[1]["delta"] == -0.06 and legs[1]["delta_sign"] == "below_mid", legs[1]
    # Deterministic now: quote captured at 14:00:05, filled at 14:00:06.
    assert legs[0]["capture_lag_seconds"] == 1.0, legs[0]["capture_lag_seconds"]
    print(f"filled legs -> deltas {legs[0]['delta']:+.2f} ({legs[0]['delta_sign']}), "
          f"{legs[1]['delta']:+.2f} ({legs[1]['delta_sign']})")

    # An unfilled leg must yield null, never a fabricated zero delta.
    unfilled = compare(snap, {"status": "canceled", "legs": [
        {"symbol": "SPY260904P00751000", "side": "buy", "filled_avg_price": "0",
         "filled_qty": "0", "status": "canceled"}]})
    assert unfilled[0]["filled_price"] is None and unfilled[0]["delta"] is None, unfilled
    print("unfilled leg -> filled_price null, delta null (no fabricated zero)")

    # Realised P&L: the actual round trip from 3 Sep. Entry sold 1.06 / bought 0.36,
    # exit bought 0.80 / sold 0.19 -> +$9.00 gross.
    round_trip = [
        {"legs": [
            {"symbol": "A", "side": "sell", "position_intent": "sell_to_open",
             "filled_price": 1.06, "filled_qty": 1},
            {"symbol": "B", "side": "buy", "position_intent": "buy_to_open",
             "filled_price": 0.36, "filled_qty": 1}]},
        {"legs": [
            {"symbol": "A", "side": "buy", "position_intent": "buy_to_close",
             "filled_price": 0.80, "filled_qty": 1},
            {"symbol": "B", "side": "sell", "position_intent": "sell_to_close",
             "filled_price": 0.19, "filled_qty": 1}]},
    ]
    r = realised_pnl(round_trip)
    assert r["realised_pnl_dollars"] == 9.0, r
    assert r["round_trip_complete"] is True and r["legs_open"] == 0, r
    # Entry only: still a running figure, not a result.
    half = realised_pnl(round_trip[:1])
    assert half["realised_pnl_dollars"] == 70.0 and half["legs_open"] == 2, half
    assert half["round_trip_complete"] is False, half
    # Nothing filled -> null, never a fabricated zero.
    assert realised_pnl([])["realised_pnl_dollars"] is None
    print(f"realised P&L from signed cash flows: entry +$70.00, exit -$61.00, "
          f"net ${r['realised_pnl_dollars']:+.2f} gross")
    print("fill_analysis: all checks pass")


if __name__ == "__main__":
    demo()
