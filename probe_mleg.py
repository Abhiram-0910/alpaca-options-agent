"""One-shot probe: does Alpaca's MCP server place a real 2-leg (mleg) options order
from this codebase's own client?

The whole live path depends on the answer, and the codebase has never asked it -- every
strategy here submits spreads as sequential single-leg place_option_order calls, so
alpacahq/alpaca-mcp-server issue #97 ("legs arrives as a JSON string, not an array") has
never actually been exercised. Rather than build the mleg order path and find out, this
places one real, deliberately unmarketable put credit spread on SPY and cancels it.

    python probe_mleg.py            # inspect the tool schema, build and print the payload
    python probe_mleg.py --submit   # ...and actually submit it, then cancel it

Run --submit during regular hours: options are regular-hours only, and after the close the
chain's ask side comes back 0, so strike selection falls back to the previous daily close.
"""
import asyncio
import json
import sys
from datetime import date, timedelta

from agent.config import CONFIG, assert_paper_trading
from agent.mcp.client import AlpacaMCPClient
from agent.mcp_parsers import parse_latest_trade_price, parse_option_chain_snapshot, parse_order_error

UNDERLYING = "SPY"
WIDTH = 5.0          # strike distance between the two put legs
MAX_DTE_SEARCH = 7   # look this far out for the nearest listed expiry


def _classify(error: str) -> str:
    """An mleg rejection and a market-hours rejection are completely different verdicts."""
    low = (error or "").lower()
    if any(k in low for k in ("legs", "validation error", "pydantic", "not a valid list", "type=list")):
        return "MLEG BROKEN -- the legs parameter did not survive the MCP transport (issue #97)"
    if any(k in low for k in ("market is closed", "outside", "hours", "not open")):
        return "INCONCLUSIVE -- rejected on market hours, not on mleg. Re-run during the session."
    return "MLEG REJECTED for another reason -- read the raw response above"


async def main(submit: bool) -> int:
    assert_paper_trading()

    async with AlpacaMCPClient() as mcp:
        # 1. What does the server say `legs` is? If it is typed as a string here, #97 is
        #    present and nothing below will work.
        tools = await mcp.list_tools_anthropic_format()
        tool = next((t for t in tools if t["name"] == "place_option_order"), None)
        if tool is None:
            print("place_option_order is not exposed by this server -- wrong toolset?")
            return 1
        legs_schema = (tool["input_schema"].get("properties") or {}).get("legs")
        print("place_option_order.legs schema:")
        print(json.dumps(legs_schema, indent=2))

        # 2. Nearest listed expiry and two OTM puts WIDTH apart.
        price_raw = await mcp.call_tool("get_stock_latest_trade", {"symbols": UNDERLYING})
        S = parse_latest_trade_price(price_raw)
        chain_raw = await mcp.call_tool("get_option_chain", {
            "underlying_symbol": UNDERLYING,
            # Start at tomorrow, not today: today's expiry is already dead by the time this
            # runs, and MIN_DTE is 1 for exactly the same reason (Greeks are null at T=0).
            "expiration_date_gte": (date.today() + timedelta(days=1)).isoformat(),
            "expiration_date_lte": (date.today() + timedelta(days=MAX_DTE_SEARCH)).isoformat(),
            "strike_price_gte": round(S * 0.90, 2),
            "strike_price_lte": round(S * 0.99, 2),
            "limit": 1000,
        })
        puts = [c for c in parse_option_chain_snapshot(chain_raw) if c.option_type == "put"]
        if not puts:
            print(f"No {UNDERLYING} puts returned in the search window -- cannot probe.")
            return 1

        expiry = min(c.expiry for c in puts)
        same = sorted((c for c in puts if c.expiry == expiry), key=lambda c: c.strike)
        # Short leg: closest strike at or below ~2% OTM. Long leg: WIDTH lower.
        short = min(same, key=lambda c: abs(c.strike - S * 0.98))
        long_ = min(same, key=lambda c: abs(c.strike - (short.strike - WIDTH)))
        if long_.strike >= short.strike:
            print(f"Chain too coarse to build a {WIDTH}-wide spread at {expiry} -- cannot probe.")
            return 1

        print(f"\n{UNDERLYING} last {S:.2f} | expiry {expiry} ({(expiry - date.today()).days} DTE)")
        print(f"  sell {short.symbol} @ {short.price}")
        print(f"  buy  {long_.symbol} @ {long_.price}")

        # 3. Deliberately unmarketable: demand nearly the full width as a credit, which no
        #    counterparty will pay, so the order rests instead of filling. Per the installed
        #    server's own docstring, mleg limit_price is the NET price and negative = credit.
        limit_price = -round(abs(short.strike - long_.strike) * 0.9, 2)
        args = {
            "qty": "1",
            "type": "limit",
            "time_in_force": "day",
            "order_class": "mleg",
            "limit_price": str(limit_price),
            "client_order_id": f"probe-mleg-{date.today().isoformat()}",
            "legs": [
                {"symbol": long_.symbol, "side": "buy", "ratio_qty": "1",
                 "position_intent": "buy_to_open"},
                {"symbol": short.symbol, "side": "sell", "ratio_qty": "1",
                 "position_intent": "sell_to_open"},
            ],
        }
        print(f"\nPayload (net limit {limit_price} = credit, unmarketable on purpose):")
        print(json.dumps(args, indent=2))

        if not submit:
            print("\nDry run. Re-run with --submit during the session to actually place it.")
            return 0

        # 4. Submit.
        raw = await mcp.call_tool("place_option_order", args)
        print(f"\nRaw response:\n{raw[:2000]}")
        error = parse_order_error(raw)
        if error:
            print(f"\nVERDICT: {_classify(error)}\n  {error}")
            return 1

        # 5. Cancel whatever it created, so the probe leaves nothing resting.
        order_id = None
        try:
            body = json.loads(raw)
            order_id = (body.get("data") or body).get("id")
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
        if order_id:
            cancel_raw = await mcp.call_tool("cancel_order_by_id", {"order_id": order_id})
            cancel_error = parse_order_error(cancel_raw)
            print(f"\nCancel {order_id}: {'FAILED -- ' + cancel_error if cancel_error else 'ok'}")
        else:
            print("\nOrder placed but no id found in the response -- CANCEL IT BY HAND.")

        print("\nVERDICT: MLEG WORKS -- a 2-leg order placed and cancelled through the MCP server.")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--submit" in sys.argv)))
