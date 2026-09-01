"""Two-agent pipeline: a Proposer that researches and proposes a trade, and an
independent, adversarially-prompted Critic that reviews the proposal before
anything reaches the deterministic RiskGate and Alpaca.

This is a genuine multi-agent split, not cosmetic: the Proposer's tool list
excludes every order-placing MCP tool entirely — it is *structurally*
incapable of placing an order, only of calling `propose_trade` to hand off a
structured proposal. Only the Critic's approval (`review_decision`) lets
execution proceed, and even then RiskGate — deterministic, not an LLM — gets
the final say on every leg, exactly as in the single-agent path. Three
independent layers have to agree: Proposer wants to trade, Critic doesn't
veto, RiskGate's hard checks pass.

Cost is bounded by design: the Critic is one non-looped call (no tools, no
back-and-forth) reviewing what the Proposer already gathered — not a second
full research loop. Total added cost versus the single-agent path is roughly
one extra Claude call per cycle, not a multiple of it.
"""
import json

from anthropic import AsyncAnthropic

from agent.config import CONFIG, assert_paper_trading
from agent.mcp.client import AlpacaMCPClient
from agent.risk.gates import RiskGate, ORDER_TOOLS, parse_occ_symbol
from agent.trade_log import log_event
from agent.kill_switch import assert_not_killed
from agent.alerts import alert
from agent.llm_cost import call_cost
from agent.backtest_evidence import load_backtest_summary, load_cleared_strategies
from agent.mcp_parsers import parse_order_error
from agent.reflection import summarize_for_prompt
from agent.live_agent import STRATEGY_UNIVERSE


def _call_leg_is_hedged(leg: dict, all_legs: list) -> bool:
    """True if `leg` (a proposal leg dict: symbol/side/qty) is a short call with a further-OTM
    long call among `all_legs` of the same proposal -- i.e. it's the short leg of a defined-risk
    spread (an iron condor's short call, hedged by its own long call), not a naked call that
    needs 100 shares owned as cover. Mirrors agent/deterministic_agent.py's helper of the same
    name, adapted for proposal legs (real OCC symbols with no .strike/.option_type of their own)
    instead of theoretical TradeLeg objects."""
    parsed = parse_occ_symbol(leg.get("symbol", ""))
    if not parsed or (leg.get("side") or "").lower() != "sell" or parsed["option_type"] != "call":
        return False
    for other in all_legs:
        if other is leg:
            continue
        other_parsed = parse_occ_symbol(other.get("symbol", ""))
        if (other_parsed and (other.get("side") or "").lower() == "buy"
                and other_parsed["option_type"] == "call" and other_parsed["strike"] > parsed["strike"]):
            return True
    return False


PROPOSE_TRADE_TOOL = {
    "name": "propose_trade",
    "description": "Submit your final proposal for this cycle. Call this exactly once, after "
                    "you've finished researching — this is how you hand off to the risk reviewer. "
                    "You cannot place orders yourself.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["trade", "skip"]},
            "symbol": {"type": "string", "description": "Watchlist symbol. Required if action=trade."},
            "strategy": {"type": "string", "description": "cash_secured_put | covered_call | "
                         "long_directional | vertical_credit_spread | iron_condor. Required if action=trade."},
            "legs": {
                "type": "array",
                "description": "Real OCC option symbols and sides to submit, in the order they should "
                                "be sent. Required if action=trade.",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Real OCC symbol from "
                                   "get_option_chain/get_option_contracts, e.g. AAPL250321C00150000."},
                        "side": {"type": "string", "enum": ["buy", "sell"]},
                        "qty": {"type": "integer"},
                        "limit_price": {"type": "string"},
                    },
                    "required": ["symbol", "side", "qty"],
                },
            },
            "rationale": {"type": "string", "description": "Why this trade (or why skipping), citing "
                          "backtest evidence and the live data you pulled."},
        },
        "required": ["action", "rationale"],
    },
}

REVIEW_DECISION_TOOL = {
    "name": "review_decision",
    "description": "Submit your verdict on the proposed trade.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["approve", "reject"]},
            "concerns": {"type": "array", "items": {"type": "string"},
                         "description": "Specific issues found, even if the verdict is approve."},
            "rationale": {"type": "string"},
        },
        "required": ["verdict", "rationale"],
    },
}


def _proposer_system_prompt(backtest_summary: str, reflection_summary: str = None) -> str:
    reflection_section = ""
    if reflection_summary:
        reflection_section = f"""
Recent closed positions (facts, not verdicts — a strategy with a real edge still loses some of
the time, so a loss alone is not evidence anything was wrong; a [PROCESS FLAG] means something
didn't match this system's own records, worth noting if it's on a symbol you're considering):
{reflection_summary}
"""
    return f"""You are the RESEARCH agent in a two-agent options-trading pipeline on a real Alpaca \
PAPER account. You act exclusively through the read-only tools provided (Alpaca's MCP server, \
minus every order-placing tool — you cannot place an order no matter what).

Watchlist (only research these underlyings): {', '.join(CONFIG.watchlist)}

{STRATEGY_UNIVERSE}

Backtest validation results per symbol — strongly prefer strategies marked PASSED; a symbol with
no PASSED strategy should generally be skipped rather than traded on discretion alone:
{backtest_summary}
{reflection_section}
Work through this cycle methodically:
1. Call get_account_info and get_all_positions first to know the starting state.
2. For 2-4 promising watchlist symbols, pull recent stock bars/snapshot, news, and the option chain
   (filter by DTE {CONFIG.min_days_to_expiration}-{CONFIG.max_days_to_expiration}) before deciding.
3. Call propose_trade exactly once to finish — either a specific trade with real OCC option symbols
   from the chain data you pulled, or action=skip with your reasoning. A second, independent agent
   will review your proposal before anything is submitted to Alpaca, so be explicit and honest about
   uncertainty in your rationale rather than overselling the case.
4. You have a limited tool-call budget this cycle ({CONFIG.max_tool_calls_per_cycle} calls) — research
   efficiently."""


CRITIC_SYSTEM_PROMPT = f"""You are the RISK REVIEWER in a two-agent options-trading pipeline on a real \
Alpaca PAPER account. A separate research agent has proposed a trade (or proposed skipping). Your job \
is to find reasons this proposal is a bad idea — default to REJECT unless the case is genuinely \
compelling. You are not here to rubber-stamp; you are the second opinion that catches what a single \
agent's own confidence in its reasoning can miss.

{STRATEGY_UNIVERSE}

Risk parameters this trade must respect (a hard, separate risk gate re-checks these mechanically
regardless of your verdict — but flag it if the proposal looks like it violates them):
- Max {CONFIG.max_positions_open} distinct open underlyings at once.
- Max {CONFIG.max_allocation_pct_per_trade:.0%} of account equity at risk per trade.
- Max {CONFIG.max_total_options_allocation_pct:.0%} of account equity in options capital-at-risk total.
- Only options expiring {CONFIG.min_days_to_expiration}-{CONFIG.max_days_to_expiration} days out.

Check specifically: does the rationale actually cite the backtest evidence, or just assert a view?
Does the strategy match what's actually validated for that symbol? Are the option symbols real
(OCC format) rather than made up? Is there anything in the cited data that argues against the trade
that the proposal glossed over? A proposal to skip can also be wrong — e.g. dismissing a genuinely
validated setup for a weak reason — review it with the same scrutiny as a proposal to trade.

Call review_decision exactly once with your verdict."""


async def _run_proposer(anthropic, mcp, tools, system_prompt) -> dict:
    account_raw = await mcp.call_tool("get_account_info", {})
    positions_raw = await mcp.call_tool("get_all_positions", {})

    messages = [{
        "role": "user",
        "content": (
            "Begin this research cycle. Current account snapshot and positions (already fetched, "
            f"no need to re-call those two tools):\n\nACCOUNT:\n{account_raw}\n\nPOSITIONS:\n{positions_raw}"
            "\n\nResearch the watchlist and call propose_trade when you're done."
        ),
    }]

    tool_calls_made, api_calls_made, cost = 0, 0, 0.0
    proposal = None
    while tool_calls_made < CONFIG.max_tool_calls_per_cycle:
        response = await anthropic.messages.create(
            model=CONFIG.claude_model, max_tokens=2048, system=system_prompt, tools=tools, messages=messages,
        )
        api_calls_made += 1
        cost += call_cost(response.usage, CONFIG.claude_model)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            tool_calls_made += 1
            if block.name == "propose_trade":
                proposal = block.input
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                      "content": "Proposal received."})
                continue
            result_text = await mcp.call_tool(block.name, block.input)
            log_event("tool_call", agent="proposer", tool=block.name, input=block.input,
                      result=result_text[:2000])
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_text})

        messages.append({"role": "user", "content": tool_results})
        if proposal is not None:
            break

    if proposal is None:
        proposal = {"action": "skip", "rationale": "Proposer ran out of tool-call budget without proposing."}
    return {"proposal": proposal, "tool_calls": tool_calls_made, "api_calls": api_calls_made, "cost_usd": cost}


async def _run_critic(anthropic, proposal: dict, backtest_summary: str) -> dict:
    content = (
        f"Backtest evidence:\n{backtest_summary}\n\n"
        f"Proposal:\n{json.dumps(proposal, indent=2)}\n\n"
        "Review this proposal and call review_decision."
    )
    response = await anthropic.messages.create(
        model=CONFIG.claude_model, max_tokens=1024, system=CRITIC_SYSTEM_PROMPT,
        tools=[REVIEW_DECISION_TOOL], tool_choice={"type": "tool", "name": "review_decision"},
        messages=[{"role": "user", "content": content}],
    )
    cost = call_cost(response.usage, CONFIG.claude_model)
    verdict_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    verdict = verdict_block.input if verdict_block else {"verdict": "reject", "rationale": "Critic gave no verdict."}
    return {"verdict": verdict, "cost_usd": cost}


async def run_cycle() -> dict:
    assert_paper_trading()
    assert_not_killed()

    backtest_summary = load_backtest_summary()
    reflection_summary = summarize_for_prompt()
    anthropic = AsyncAnthropic(api_key=CONFIG.anthropic_api_key)
    risk_gate = RiskGate()

    async with AlpacaMCPClient() as mcp:
        all_tools = await mcp.list_tools_anthropic_format()
        read_only_tools = [t for t in all_tools if t["name"] not in ORDER_TOOLS] + [PROPOSE_TRADE_TOOL]

        proposer_result = await _run_proposer(anthropic, mcp, read_only_tools,
                                               _proposer_system_prompt(backtest_summary, reflection_summary))
        proposal = proposer_result["proposal"]
        total_cost = proposer_result["cost_usd"]
        total_api_calls = proposer_result["api_calls"]
        total_tool_calls = proposer_result["tool_calls"]

        log_event("proposal", proposal=proposal)

        if proposal.get("action") != "trade":
            log_event("multi_agent_cycle_complete", proposal=proposal, verdict=None,
                       cost_usd=round(total_cost, 5))
            return {"tool_calls": total_tool_calls, "api_calls": total_api_calls,
                    "cost_usd": round(total_cost, 5), "rejections": [],
                    "summary": f"Proposer chose to skip: {proposal.get('rationale', '')}"}

        critic_result = await _run_critic(anthropic, proposal, backtest_summary)
        total_cost += critic_result["cost_usd"]
        total_api_calls += 1
        verdict = critic_result["verdict"]
        log_event("critic_verdict", verdict=verdict)

        if verdict.get("verdict") != "approve":
            alert("proposal_vetoed_by_critic", symbol=proposal.get("symbol"),
                  strategy=proposal.get("strategy"), reason=verdict.get("rationale"))
            log_event("multi_agent_cycle_complete", proposal=proposal, verdict=verdict,
                       cost_usd=round(total_cost, 5))
            return {"tool_calls": total_tool_calls, "api_calls": total_api_calls,
                    "cost_usd": round(total_cost, 5), "rejections": [verdict.get("rationale", "")],
                    "summary": f"Critic REJECTED the proposal for {proposal.get('symbol')} "
                               f"({proposal.get('strategy')}): {verdict.get('rationale', '')}"}

        # Critic approved — account/positions were fetched at the top of the proposer stage;
        # refresh once more so RiskGate has current numbers before the actual execution decision.
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

        symbol = proposal.get("symbol")
        strategy = proposal.get("strategy")
        # RiskGate's backtest-validation gate is symbol-level only (a bare place_option_order
        # call has no strategy label for it to check) -- so a symbol with ONE cleared strategy
        # (e.g. GOOGL/cash_secured_put) would otherwise silently let this proposal through with
        # a completely different, never-validated strategy for that same symbol. The Proposer
        # *does* state a strategy explicitly, so cross-check it here before RiskGate ever sees
        # the legs.
        if CONFIG.require_backtest_validation and strategy not in load_cleared_strategies(symbol):
            cleared = load_cleared_strategies(symbol)
            reason = (f"{symbol}/{strategy} has not itself passed backtest validation "
                      f"(cleared for {symbol}: {', '.join(sorted(cleared)) or 'none'})")
            alert("order_blocked_critical", agent="multi_agent", symbol=symbol, strategy=strategy, reason=reason)
            log_event("multi_agent_cycle_complete", proposal=proposal, verdict=verdict,
                       risk_gate_rejections=[reason], cost_usd=round(total_cost, 5))
            return {"tool_calls": total_tool_calls, "api_calls": total_api_calls,
                    "cost_usd": round(total_cost, 5), "rejections": [reason],
                    "summary": f"Critic approved {symbol}/{strategy} but it hasn't itself cleared "
                               f"backtest validation for {symbol}: {reason}"}

        legs = proposal.get("legs") or []
        rejections = []
        approved_legs = []
        batch_committed = 0.0
        for leg in legs:
            decision = risk_gate.check("place_option_order", {
                "symbol": leg.get("symbol"), "side": leg.get("side"), "qty": leg.get("qty", 1),
                "limit_price": leg.get("limit_price"),
            }, covered_by_paired_long=_call_leg_is_hedged(leg, legs))
            if not decision.get("approved"):
                rejections.append(f"{leg.get('symbol')}: {decision.get('reason')}")
                # Roll back capital already committed by this batch's earlier legs (see the
                # matching comment in deterministic_agent.py) so an abandoned multi-leg proposal
                # doesn't permanently eat into this cycle's real budget.
                risk_gate.release_commitment(batch_committed)
                approved_legs = None
                break
            batch_committed += decision.get("estimated_capital_at_risk") or 0.0
            approved_legs.append(leg)

        if not approved_legs:
            log_event("multi_agent_cycle_complete", proposal=proposal, verdict=verdict,
                       risk_gate_rejections=rejections, cost_usd=round(total_cost, 5))
            return {"tool_calls": total_tool_calls, "api_calls": total_api_calls,
                    "cost_usd": round(total_cost, 5), "rejections": rejections,
                    "summary": f"Critic approved {proposal.get('symbol')}/{proposal.get('strategy')} but "
                               f"RiskGate rejected it: {'; '.join(rejections)}"}

        # Submit buy (protective) legs before sell legs — same reasoning as
        # deterministic_agent.py: legs aren't atomic, and the Proposer's own leg ordering in
        # its proposal isn't something to trust for this, since a naked short between fills
        # is a materially worse failure mode than a temporarily-orphaned long option.
        placed = []
        for leg in sorted(approved_legs, key=lambda l: 0 if l.get("side") == "buy" else 1):
            order_args = {
                "symbol": leg["symbol"], "side": leg["side"], "qty": str(leg.get("qty", 1)),
                "type": "limit" if leg.get("limit_price") else "market",
                "position_intent": "sell_to_open" if leg["side"] == "sell" else "buy_to_open",
                "client_order_id": f"ma-{proposal.get('symbol')}-{proposal.get('strategy')}-{leg['symbol']}",
            }
            if leg.get("limit_price"):
                order_args["limit_price"] = str(leg["limit_price"])
            order_result = await mcp.call_tool("place_option_order", order_args)
            # Alpaca rejecting an order is a normal (non-error) MCP result, not an exception --
            # see parse_order_error's docstring. Without this check, a rejected leg here was
            # logged/alerted/recorded as placed just like a successful one, and the loop would
            # keep submitting the following legs regardless, risking the exact naked exposure the
            # buy-before-sell ordering above exists to prevent.
            order_error = parse_order_error(order_result)
            log_event("multi_agent_order", symbol=proposal.get("symbol"), strategy=proposal.get("strategy"),
                      leg=leg["symbol"], side=leg["side"], result=order_result[:1500], error=order_error)
            if order_error:
                rejections.append(f"{leg['symbol']}: rejected by Alpaca — {order_error}")
                alert("order_rejected", agent="multi_agent", symbol=proposal.get("symbol"),
                      strategy=proposal.get("strategy"), contract=leg["symbol"], side=leg["side"],
                      reason=order_error)
                break
            alert("order_placed", agent="multi_agent", symbol=proposal.get("symbol"),
                  strategy=proposal.get("strategy"), contract=leg["symbol"], side=leg["side"])
            placed.append(leg["symbol"])

        log_event("multi_agent_cycle_complete", proposal=proposal, verdict=verdict, placed=placed,
                   cost_usd=round(total_cost, 5))
        return {
            "tool_calls": total_tool_calls, "api_calls": total_api_calls, "cost_usd": round(total_cost, 5),
            "rejections": rejections,
            "summary": f"Proposed {proposal.get('symbol')}/{proposal.get('strategy')}, critic approved "
                       f"({verdict.get('rationale', '')[:200]}), placed: {', '.join(placed)}"
                       + (f" -- STOPPED after a rejection: {rejections[-1]}" if len(placed) < len(approved_legs) else ""),
        }
