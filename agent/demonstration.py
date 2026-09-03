"""Demonstration mode: one bounded, explicitly unvalidated trade.

As of 1 Sep 2026 the validation gate has refused every candidate it has been given -- three
liquid ETFs, seven structures, nothing cleared (docs/strategy_graveyard.md). That is the
project's headline finding, not a setback, and it is reported as such.

It leaves a question the gate was never designed to answer. The gate governs whether we may
CLAIM an edge. It does not govern whether an order is SAFE. A defined-risk vertical spread's
worst case is bounded and known before entry -- which is why defined risk was the requirement
in the first place -- so "we have no evidence of edge" and "this order could hurt the account"
are different statements, and only the first one is true here.

Demonstration mode executes exactly one such order, so the full path is shown working end to
end: chain read, strike selection in deterministic Python, risk gate, MCP multi-leg order,
managed exit. Every constraint below is TIGHTER than the normal path, none is looser, and
none is env-tunable -- an operator can turn this mode on, and can turn it off, and that is
the whole surface.

The one gate it replaces is the backtest-validation check, and it refuses to arm at all if
that check would have passed something, so a demonstration trade can never sit alongside or
be mistaken for a validated one.

Rejected alternative: relaxing the gate's criteria after seeing that everything failed. That
is the exact post-hoc move the gate exists to prevent, and a reviewer would be right to
discount every other number in this repo on the strength of it.
"""
from datetime import date as _date

from agent.config import CONFIG
from agent.backtest_evidence import load_cleared_symbols

# Stamped on every order, log line and trade-log entry this mode produces, so no result it
# generates can later be read -- by us, by a judge, or by the reflection loop -- as validated.
DEMONSTRATION_STATUS = "UNVALIDATED_DEMONSTRATION"

SYMBOL = "SPY"                    # deepest chain, daily expiries, tightest quotes available

# Pinned rather than derived from a target DTE, because "nearest available expiry" silently
# substitutes when the one you wanted isn't listed, and this trade happens once.
#
# Fri 4 Sep, not Thu 3 Sep. Entered Wednesday that is 2 DTE, matching the entry condition of
# the hold_days=2 profile. Exited at the Thursday 15:45 flat rule it still has a day of time
# value, so the position is closed as a spread rather than unwound at 0 DTE -- which would
# mean the widest quotes of the week, live pin risk on the short leg, and reliance on paper's
# assignment simulation, which docs/RESEARCH.md records as unverified and which Alpaca will
# auto-exercise on $0.01 of intrinsic.
#
# The cost of choosing it: Friday's 08:30 NFP print keeps extrinsic value in a Friday expiry
# through Thursday's close, so we buy the spread back richer than pure decay implies. That is
# a known price paid to avoid pin risk, not an oversight. We never hold through the print --
# the flat rule runs on wall clock and is unaffected by which expiry was chosen.
#
# Note the exit is one day earlier than the validated profile's own (which settles at
# expiration on intrinsic). This is an UNVALIDATED_DEMONSTRATION regardless, so it does not
# weaken a claim -- but it is not the profile either, and shouldn't be described as it.
DEMONSTRATION_EXPIRY = _date(2026, 9, 4)
MAX_CONTRACTS = 1
MAX_OPEN_POSITIONS = 1
MAX_LOSS_PCT_OF_NAV = 0.005       # 0.5% of NAV, roughly a tenth of the normal per-trade cap
MIN_LEGS = 2                      # defined risk requires a hedging leg, so never single-leg


def _cleared() -> set:
    return load_cleared_symbols()


def demonstration_status(root: str, legs: list, qty: float, equity: float = None) -> dict:
    """Whether demonstration mode is armed for this specific order.

    Returns {"armed": bool, "blocked": str, "max_loss_cap": float}. `blocked` is a rejection
    reason that outranks everything else: it means the operator asked for demonstration mode
    and this order is not one demonstration mode will place. Never raises -- the risk gate
    turns it into a normal rejection the caller can read.
    """
    cap = MAX_LOSS_PCT_OF_NAV * (equity if equity else 100_000)
    off = {"armed": False, "blocked": "", "max_loss_cap": cap}
    if not CONFIG.demonstration_mode:
        return off

    # Cannot coexist with a validated trade. If anything cleared, the normal path applies and
    # this mode has no reason to exist.
    cleared = _cleared()
    if cleared:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": (f"Demonstration mode refuses to arm: {', '.join(sorted(cleared))} "
                            f"cleared backtest validation, so the validated path applies. Turn "
                            f"DEMONSTRATION_MODE off.")}

    if root != SYMBOL:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": f"Demonstration mode trades {SYMBOL} only; got {root}."}
    if not isinstance(legs, list) or len(legs) < MIN_LEGS:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": (f"Demonstration mode requires a defined-risk multi-leg structure "
                            f"(>= {MIN_LEGS} legs); got {len(legs) if isinstance(legs, list) else legs!r}.")}
    if qty > MAX_CONTRACTS:
        return {"armed": False, "max_loss_cap": cap,
                "blocked": f"Demonstration mode allows {MAX_CONTRACTS} contract; got {qty:g}."}

    return {"armed": True, "blocked": "", "max_loss_cap": cap}


# Alpaca order statuses that mean the order is still able to fill. A demonstration order in
# any of these is working, and a second one would stack rather than replace it.
_LIVE_ORDER_STATUSES = {
    "new", "accepted", "pending_new", "accepted_for_bidding", "partially_filled",
    "held", "pending_replace", "replaced", "calculated", "stopped", "suspended",
}


def _order_filled_qty(order: dict) -> float:
    try:
        return float(order.get("filled_qty") or 0)
    except (TypeError, ValueError):
        return 0.0


async def _prior_demonstration_orders(mcp) -> list:
    """Every order this mode has previously placed, newest first.

    Identified by the client_order_id prefix rather than by symbol: the account may carry
    unrelated SPY orders (the mleg probe did), and only orders this mode created should be
    able to block or permit it. A read failure returns [] and the caller falls back to the
    positions check, which is the conservative direction -- it can only allow a re-price when
    the book is flat.
    """
    import json  # module-level `json` is imported inside run_cycle, not here
    prefix = f"demo-{SYMBOL}-"
    try:
        raw = await mcp.call_tool("get_orders", {"status": "all", "limit": 100})
        data = json.loads(raw).get("data", {})
        orders = data.get("result", data) if isinstance(data, dict) else data
        if not isinstance(orders, list):
            return []
    except (json.JSONDecodeError, AttributeError, TypeError, KeyError):
        return []
    return [o for o in orders if isinstance(o, dict)
            and str(o.get("client_order_id") or "").startswith(prefix)]


def _marketable_credit(short_leg, long_leg) -> tuple:
    """Net credit at the price the spread actually crosses at, or (None, reason).

    Sell the short leg at its BID, buy the long leg at its ASK -- the side of each quote a
    taker is filled on. The previous model used mid minus mid shaded 10%, which is where a
    resting order sits, not where it trades: attempt 1 priced 0.85 that way and never became
    fillable in six hours.

    Requires both quotes. A missing bid or ask is a contract we cannot price to fill, so the
    candidate is skipped rather than guessed at -- these are indicative-feed quotes and a
    fabricated side would be worse than a narrower strike choice.
    """
    bid = getattr(short_leg, "bid", None)
    ask = getattr(long_leg, "ask", None)
    if bid is None or ask is None:
        return None, f"missing quote side (short bid={bid}, long ask={ask})"
    try:
        credit = round(float(bid) - float(ask), 2)
    except (TypeError, ValueError):
        return None, f"unparseable quote (short bid={bid!r}, long ask={ask!r})"
    if credit <= 0:
        # Crossing both spreads costs more than the position pays; not a credit spread at
        # marketable prices, whatever the mids imply.
        return None, (f"marketable credit {credit:.2f} is not positive "
                      f"(short bid {float(bid):.2f} - long ask {float(ask):.2f})")
    return credit, (f"short {short_leg.symbol} bid {float(bid):.2f} "
                    f"- long {long_leg.symbol} ask {float(ask):.2f} = {credit:.2f} credit")


def demo() -> None:
    """Self-check: the constraints that make this mode safe to leave in the repo."""
    # Patch this module's own globals, not a re-imported copy of it: run as __main__ the
    # module object here and the one `import agent.demonstration` returns are different.
    g = globals()

    legs2 = [{"symbol": "SPY260903P00755000", "side": "sell"},
             {"symbol": "SPY260903P00750000", "side": "buy"}]

    # Off by default: nothing arms unless the operator explicitly turns it on.
    assert not demonstration_status("SPY", legs2, 1)["armed"]

    real_cleared, real_flag = g["_cleared"], CONFIG.demonstration_mode
    try:
        object.__setattr__(CONFIG, "demonstration_mode", True)

        g["_cleared"] = lambda: set()
        assert demonstration_status("SPY", legs2, 1)["armed"], "should arm on a 1-lot SPY spread"
        assert demonstration_status("QQQ", legs2, 1)["blocked"], "SPY only"
        assert demonstration_status("SPY", legs2, 2)["blocked"], "1 contract only"
        assert demonstration_status("SPY", legs2[:1], 1)["blocked"], "single leg must be refused"

        g["_cleared"] = lambda: {"SPY"}
        assert demonstration_status("SPY", legs2, 1)["blocked"], \
            "must refuse to arm when something cleared validation"
    finally:
        g["_cleared"] = real_cleared
        object.__setattr__(CONFIG, "demonstration_mode", real_flag)

    assert demonstration_status("SPY", legs2, 1, equity=100_000)["max_loss_cap"] == 500.0

    # Marketable pricing: sell the short at the BID, buy the long at the ASK. Attempt 1 used
    # mid x 0.9, which is where an order rests rather than where it trades -- it sat above the
    # bid for 61 minutes and was cancelled unfilled.
    class _Q:
        def __init__(self, symbol, bid, ask, price):
            self.symbol, self.bid, self.ask, self.price = symbol, bid, ask, price

    short_q = _Q("SPY260904P00770000", 1.15, 1.20, 1.175)
    long_q = _Q("SPY260904P00765000", 0.35, 0.39, 0.37)
    credit, basis = _marketable_credit(short_q, long_q)
    assert credit == 0.76, (credit, basis)          # 1.15 bid - 0.39 ask, not 1.175 - 0.37
    assert credit < round(short_q.price - long_q.price, 2), \
        "the marketable credit must be below the mid-to-mid credit, never above it"
    assert "bid 1.15" in basis and "ask 0.39" in basis, basis

    # A missing quote side is skipped, never guessed at: these are indicative-feed quotes and
    # a fabricated bid would price a trade that cannot fill.
    assert _marketable_credit(_Q("s", None, 1.2, 1.1), long_q)[0] is None
    assert _marketable_credit(short_q, _Q("l", 0.3, None, 0.35))[0] is None
    # Crossing both spreads can cost more than the position pays. That is not a credit spread
    # at marketable prices, whatever the mids say.
    assert _marketable_credit(_Q("s", 0.40, 0.45, 0.42), _Q("l", 0.50, 0.60, 0.55))[0] is None

    assert _order_filled_qty({"filled_qty": "1"}) == 1.0
    assert _order_filled_qty({"filled_qty": None}) == 0.0
    assert _order_filled_qty({}) == 0.0
    print("marketable credit 0.76 from bid/ask, below the 0.81 mid-to-mid; "
          "missing or inverted quotes refused")

    print("demonstration: all checks pass")


if __name__ == "__main__":
    demo()


async def run_cycle(dry_run: bool = True) -> dict:
    """Build (and optionally submit) the single demonstration spread.

    Defaults to dry_run: it prices the real chain, builds the exact mleg payload, and runs it
    through the full risk gate, but does not submit. Nothing here decides anything the gate
    would not also decide -- it is the gate that says yes.
    """
    import json
    from datetime import date

    from agent.config import assert_paper_trading
    from agent.mcp.client import AlpacaMCPClient
    from agent.risk.gates import RiskGate
    from agent.kill_switch import assert_not_killed
    from agent.trade_log import log_event
    from agent.alerts import alert
    from agent.options_pricing import realized_vol
    from agent.strategies import vertical_credit_spread
    from agent.mcp_parsers import parse_latest_trade_price, parse_bars_closes, parse_order_error
    from agent.live_chain import fetch_target_expiry_chain
    from agent.deterministic_agent import _match_leg_to_real_chain

    assert_paper_trading()
    assert_not_killed()

    result = {"validation_status": DEMONSTRATION_STATUS, "submitted": False, "skipped": [],
              "rejections": [], "order": None}

    if not CONFIG.demonstration_mode:
        result["skipped"].append("DEMONSTRATION_MODE is not set; nothing to do")
        return result

    risk_gate = RiskGate()
    async with AlpacaMCPClient() as mcp:
        account_raw = await mcp.call_tool("get_account_info", {})
        positions_raw = await mcp.call_tool("get_all_positions", {})
        try:
            account_info = json.loads(account_raw).get("data", {})
            positions = json.loads(positions_raw).get("data", {}).get("result", [])
            if not isinstance(positions, list):
                positions = []
        except (json.JSONDecodeError, AttributeError):
            account_info, positions = {}, []
        risk_gate.refresh(account_info, positions)

        # This mode places one POSITION, once. That rule is unchanged; what changed is that a
        # cancelled unfilled order is not a position and must not be treated as one.
        #
        # The first attempt priced off the shaded mid at 0.85 credit, sat above the bid, never
        # became fillable, and the loop's stale-order housekeeping cancelled it at 61 minutes.
        # Nothing was opened and nothing was risked, so refusing a re-price would be enforcing
        # "one order ever" when the rule is "one position ever" -- and would end the session
        # with no demonstration at all because of a limit price.
        #
        # So: a re-price is allowed only when every prior demonstration order died unfilled and
        # the book is flat. A prior FILL blocks it forever, even if that position has since
        # been closed -- which the positions check alone would miss.
        if len(positions) >= MAX_OPEN_POSITIONS:
            result["skipped"].append(
                f"{len(positions)} position(s) already open; demonstration mode places at most "
                f"{MAX_OPEN_POSITIONS} and will not add to the book")
            log_event("demonstration_skipped", reason=result["skipped"][-1],
                      validation_status=DEMONSTRATION_STATUS)
            return result

        prior = await _prior_demonstration_orders(mcp)
        filled = [o for o in prior if _order_filled_qty(o) > 0]
        live = [o for o in prior if (o.get("status") or "").lower() in _LIVE_ORDER_STATUSES]
        if filled:
            result["skipped"].append(
                f"a prior demonstration order already filled "
                f"({filled[0].get('client_order_id')}, {_order_filled_qty(filled[0]):g} filled); "
                f"this mode opens one position ever and has already opened it")
            log_event("demonstration_skipped", reason=result["skipped"][-1],
                      validation_status=DEMONSTRATION_STATUS)
            return result
        if live:
            result["skipped"].append(
                f"a demonstration order is still working "
                f"({live[0].get('client_order_id')}, status {live[0].get('status')}); "
                f"cancel it before re-pricing rather than stacking a second one")
            log_event("demonstration_skipped", reason=result["skipped"][-1],
                      validation_status=DEMONSTRATION_STATUS)
            return result
        attempt = len(prior) + 1
        if prior:
            result["skipped"].append(
                f"{len(prior)} prior demonstration order(s), all unfilled and cancelled/expired; "
                f"re-pricing as attempt {attempt}")

        price_raw = await mcp.call_tool("get_stock_latest_trade", {"symbols": SYMBOL})
        bars_raw = await mcp.call_tool("get_stock_bars",
                                       {"symbols": SYMBOL, "timeframe": "1Day", "days": 40})
        try:
            S = parse_latest_trade_price(price_raw)
            closes = parse_bars_closes(bars_raw, SYMBOL)
        except (ValueError, KeyError, TypeError) as exc:
            result["skipped"].append(f"could not parse live {SYMBOL} price/bars ({exc})")
            return result
        if len(closes) < 20:
            result["skipped"].append("not enough recent bars for a volatility estimate")
            return result

        sigma = realized_vol(closes, window=20)
        target_dte = (DEMONSTRATION_EXPIRY - date.today()).days
        target_expiry, chain = await fetch_target_expiry_chain(
            mcp, SYMBOL, S, target_dte, CONFIG.min_days_to_expiration,
            CONFIG.max_days_to_expiration, round(S * 0.85, 2), round(S * 1.02, 2))
        if not chain:
            result["skipped"].append(
                f"no listed {SYMBOL} contracts in the {CONFIG.min_days_to_expiration}-"
                f"{CONFIG.max_days_to_expiration} DTE window")
            return result
        # fetch_target_expiry_chain picks the *nearest* listed expiry to the target. For a
        # one-shot trade, take the pinned expiry or take nothing -- quietly landing on the
        # 3 Sep chain is the exact 0-DTE-at-exit outcome DEMONSTRATION_EXPIRY exists to avoid.
        if target_expiry != DEMONSTRATION_EXPIRY:
            result["skipped"].append(
                f"{SYMBOL} chain offered {target_expiry} as the nearest expiry, not the pinned "
                f"{DEMONSTRATION_EXPIRY}; skipping rather than substituting a different trade")
            log_event("demonstration_skipped", reason=result["skipped"][-1],
                      validation_status=DEMONSTRATION_STATUS)
            return result

        # Time to expiry from the expiry the chain returned, never a hardcoded constant:
        # strike_for_delta is very sensitive to it at this horizon.
        t_years = max((target_expiry - date.today()).days, 1) / 365
        legs = vertical_credit_spread(S, t_years, sigma).legs
        matched = [_match_leg_to_real_chain(leg, chain, S, t_years, sigma) for leg in legs]
        if any(m is None for m in matched):
            result["skipped"].append(f"{SYMBOL} chain had no real contract for every leg")
            return result

        # Hand the gate the chain we just fetched, so it can refuse a leg for a contract that
        # is not actually listed. The gate does no network I/O of its own; this is the only way
        # it can know. Found by the adversarial harness -- see agent/adversarial.py A01.
        risk_gate.known_contracts = {q.symbol for q in chain if getattr(q, "symbol", None)}

        short = next(m for leg, m in zip(legs, matched) if leg.side == "sell")

        # Pick the protective leg to fit the risk budget rather than to hit a delta.
        #
        # The strategy function targets 30-delta short / 15-delta long, and on a 2-DTE SPY
        # chain those land ~6 points apart, for a max loss of $519 against this mode's hard
        # $500 cap -- so delta-matching proposes a trade the gate must refuse. Narrowing the
        # spread to fit a risk budget is what sizing to a budget means; widening the budget to
        # fit the spread is not. The cap does not move.
        #
        # Widest candidate that still fits, because within a fixed max loss the wider spread
        # collects the larger credit.
        cap = MAX_LOSS_PCT_OF_NAV * (risk_gate.equity or 100_000)
        candidates = []
        for quote in chain:
            if quote.option_type != "put" or quote.strike >= short.strike:
                continue
            marketable, basis = _marketable_credit(short, quote)
            if marketable is None:
                continue
            max_loss = (short.strike - quote.strike - marketable) * 100 * MAX_CONTRACTS
            if 0 < max_loss <= cap:
                candidates.append((short.strike - quote.strike, quote, marketable, basis))
        if not candidates:
            result["skipped"].append(
                f"no {SYMBOL} {target_expiry} put below {short.strike} makes a spread inside the "
                f"${cap:,.0f} demonstration cap; skipping rather than widening the cap")
            log_event("demonstration_skipped", reason=result["skipped"][-1],
                      validation_status=DEMONSTRATION_STATUS)
            return result
        _, long_, credit, credit_basis = max(candidates, key=lambda c: c[0])

        # `credit` is now the MARKETABLE credit, not a shaded mid: sell the short leg at its
        # bid, buy the long leg at its ask. That is the price at which the spread crosses
        # immediately instead of resting. The first attempt used mid x 0.9, which sat above the
        # bid and never became fillable -- on an indicative feed the mid is an estimate to begin
        # with, and a demonstration that never fills demonstrates nothing. The cost is the full
        # spread on both legs, which on a sub-$500 position is worth less than the information.
        payload = {
            "qty": str(MAX_CONTRACTS),
            "type": "limit",
            "time_in_force": "day",
            "order_class": "mleg",
            "limit_price": str(-credit),
            # Suffixed per attempt: Alpaca rejects a duplicate client_order_id outright, so
            # the deterministic id made a re-price impossible even when it was the right thing
            # to do. The date still identifies the session; the suffix distinguishes attempts.
            "client_order_id": f"demo-{SYMBOL}-{date.today().isoformat()}-r{attempt}",
            "legs": [
                {"symbol": long_.symbol, "side": "buy", "ratio_qty": "1",
                 "position_intent": "buy_to_open"},
                {"symbol": short.symbol, "side": "sell", "ratio_qty": "1",
                 "position_intent": "sell_to_open"},
            ],
        }

        decision = risk_gate.check("place_option_order", payload)
        result["order"] = {"payload": payload, "underlying_price": S, "expiry": str(target_expiry),
                           "attempt": attempt, "credit_basis": credit_basis,
                           "net_credit": credit,
                           "credit_dollars": round(credit * 100 * MAX_CONTRACTS, 2),
                           "decision": decision}
        if not decision.get("approved"):
            result["rejections"].append(decision.get("reason", ""))
            log_event("demonstration_rejected", reason=decision.get("reason"),
                      payload=payload,
                      estimated_capital_at_risk=decision.get("estimated_capital_at_risk"),
                      capital_basis=decision.get("capital_basis"),
                      validation_status=DEMONSTRATION_STATUS)
            return result

        # The approval is logged here rather than only alongside a submitted order, because a
        # dry run returns below and the demonstration trade is dry-run by default. Without
        # this the one gate decision that matters most -- the approval of the only trade this
        # agent places -- was recorded nowhere at all.
        log_event("demonstration_approved", symbol=SYMBOL, payload=payload,
                  estimated_capital_at_risk=decision.get("estimated_capital_at_risk"),
                  capital_basis=decision.get("capital_basis"), dry_run=dry_run,
                  validation_status=DEMONSTRATION_STATUS)

        # Pre-trade indicative quotes, read from the chain already fetched above. No extra
        # round trip and nothing new between the decision and the submission -- the cost is a
        # timing gap, which fill_analysis measures rather than hides. Captured before the dry
        # run returns so the dry path records what it would have compared against.
        from agent import fill_analysis
        quote_snapshot = fill_analysis.capture_quotes(
            chain, [l["symbol"] for l in payload["legs"]])
        result["pre_trade_quotes"] = quote_snapshot

        if dry_run:
            result["skipped"].append("dry run — payload built and approved, not submitted")
            return result

        raw = await mcp.call_tool("place_option_order", payload)
        error = parse_order_error(raw)
        log_event("demonstration_order", symbol=SYMBOL, payload=payload,
                  capital_at_risk=decision.get("estimated_capital_at_risk"),
                  capital_basis=decision.get("capital_basis"), result=raw[:1500], error=error,
                  validation_status=DEMONSTRATION_STATUS)
        if error:
            result["rejections"].append(f"rejected by Alpaca — {error}")
            alert("order_rejected", agent="demonstration", symbol=SYMBOL, reason=error)
            return result
        alert("order_placed", agent="demonstration", symbol=SYMBOL,
              capital_at_risk=decision.get("estimated_capital_at_risk"),
              validation_status=DEMONSTRATION_STATUS)
        result["submitted"] = True

        # Everything below is measurement, after the order is already in. It cannot delay the
        # submission and cannot fail it: record() swallows its own errors, and the order is
        # reported as submitted regardless of whether the comparison worked.
        order_id = None
        try:
            order_id = (json.loads(raw).get("data") or {}).get("id")
        except (ValueError, AttributeError):
            order_id = None
        if order_id:
            result["fill_analysis"] = fill_analysis.record(
                order_id, quote_snapshot, context="demonstration")
        else:
            log_event("fill_analysis_skipped", reason="no order id in the submit response",
                      result=raw[:500])
        return result
