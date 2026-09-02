"""The autonomous agent loop.

Claude drives an Anthropic tool-use conversation where the tools *are*
Alpaca's MCP server tools (account info, market/option data, news, order
placement). Every order-placing tool call is intercepted by `RiskGate`
before it is ever forwarded to Alpaca. One call to `run_cycle()` is one
research-and-trade cycle; `main.py` schedules cycles during market hours.
"""
import json

from anthropic import AsyncAnthropic

from agent.config import CONFIG, assert_paper_trading
from agent.mcp.client import AlpacaMCPClient
from agent.risk.gates import RiskGate, ORDER_TOOLS
from agent.trade_log import log_event
from agent.kill_switch import assert_not_killed
from agent.alerts import alert
from agent.llm_cost import call_cost as _call_cost
from agent.backtest_evidence import load_backtest_summary
from agent.reflection import summarize_for_prompt
from agent.mcp_parsers import parse_order_error, clip_tool_result

# Formatted at import, not inside _build_system_prompt: multi_agent.py interpolates this
# constant into its own f-strings, where any {placeholder} left in it would survive as
# literal braces in the prompt the model actually reads.
STRATEGY_UNIVERSE = """\
You may only use these five options strategy families (never naked/undefined-risk trades):

1. cash_secured_put — sell a cash-secured put (~0.25-0.35 delta), {min_dte}-{max_dte} DTE. Income/bullish.
   Requires buying power >= strike * 100 * qty.
2. covered_call — sell a call against >=100 owned shares of the same underlying (~0.25-0.35 delta).
   Income, caps upside. Only usable if the account already holds >=100 shares of that symbol.
3. long_directional — buy a call or put (~0.35-0.45 delta), {min_dte}-{max_dte} DTE, sized only by premium paid.
   Use for a clear directional thesis with defined risk = premium paid.
4. vertical_credit_spread — sell a closer put and buy a further-OTM put (bull put credit spread),
   defined max loss = spread width minus credit. Submit the two legs as two separate
   place_option_order calls (sell leg first, then the protective buy leg).
5. iron_condor — sell a closer put + closer call (~0.16 delta each), buy a further put + further
   call (~0.08 delta each) for protection. Defined max loss = wider wing width minus net credit.
   Submit all four legs as four separate place_option_order calls.

Do not place directional equity or crypto orders. Do not sell naked/uncovered options.

Every strategy/symbol combination below has already been run through a rigorous offline backtest:
day-by-day simulation with an ATR-derived stop-loss (fixed before the backtest ran, never tuned
to the results), real transaction-cost friction, and a statistical validation gate that requires
at least 30 simulated trades AND a bootstrap confidence interval that excludes zero on the upside
for BOTH mean return and Sharpe ratio — and anything that passed was re-tested on a much longer
history window to catch overfitting to a lucky short window. Only combinations marked PASSED below
cleared that gate. Full numbers for every combination (pass and fail) are logged to
docs/strategy_graveyard.md if you want more detail than the summary below.""".format(
    min_dte=CONFIG.min_days_to_expiration, max_dte=CONFIG.max_days_to_expiration)


def _build_system_prompt(backtest_summary: str, reflection_summary: str = None) -> str:
    reflection_section = ""
    if reflection_summary:
        reflection_section = f"""
Recent closed positions (facts, not verdicts — a strategy with a real edge still loses some of
the time; GOOGL cash_secured_put's own backtest win rate is 70%, so a loss here is not by itself
evidence anything was wrong. A [PROCESS FLAG] means something didn't match this system's own
records, which IS worth noting in your rationale if you see one on the symbol you're considering):
{reflection_summary}
"""
    return f"""You are an autonomous options-trading agent operating a real Alpaca PAPER trading account.
You act exclusively through the tools provided (Alpaca's MCP server) — never invent data or symbols.

Watchlist (only trade these underlyings): {', '.join(CONFIG.watchlist)}

{STRATEGY_UNIVERSE}

Backtest validation results per symbol — strongly prefer strategies marked PASSED; a symbol with
no PASSED strategy should generally be skipped this cycle rather than traded on discretion alone:
{backtest_summary}
{reflection_section}
Risk gates you cannot bypass (a rejected place_option_order tool call will tell you why):
- Max {CONFIG.max_positions_open} distinct open underlyings at once.
- Max {CONFIG.max_allocation_pct_per_trade:.0%} of account equity at risk per trade.
- Max {CONFIG.max_total_options_allocation_pct:.0%} of account equity in options capital-at-risk total.
- Only options expiring {CONFIG.min_days_to_expiration}-{CONFIG.max_days_to_expiration} days out.
- Daily loss circuit breaker at -{CONFIG.daily_loss_limit_pct:.0%}: no new trades once tripped.

Work through this cycle methodically:
1. Call get_account_info and get_all_positions first to know your starting state.
2. For 2-4 promising watchlist symbols, pull recent stock bars/snapshot, news, and the option chain
   (filter by DTE {CONFIG.min_days_to_expiration}-{CONFIG.max_days_to_expiration} and reasonable
   strikes near the money) before deciding anything.
3. Only place an order when you have a real OCC option symbol from get_option_chain/get_option_contracts
   output and a specific, reasoned strategy — cite the backtest evidence and current data in your rationale.
4. You have a limited tool-call budget this cycle ({CONFIG.max_tool_calls_per_cycle} calls) — research
   efficiently, then act or explicitly decide to skip the cycle.
5. Finish with a short plain-text summary of what you observed and what you did (or why you did nothing).
"""


async def run_cycle() -> dict:
    assert_paper_trading()
    assert_not_killed()

    backtest_summary = load_backtest_summary()
    reflection_summary = summarize_for_prompt()
    system_prompt = _build_system_prompt(backtest_summary, reflection_summary)
    anthropic = AsyncAnthropic(api_key=CONFIG.anthropic_api_key)
    risk_gate = RiskGate()

    async with AlpacaMCPClient() as mcp:
        tools = await mcp.list_tools_anthropic_format()
        # Alpaca's MCP server exposes ~70 tools (~20K tokens of schema) that are byte-identical
        # on every turn of this loop. Mark the end of the tools block and the end of the system
        # prompt as cache breakpoints so every turn after the first reads that ~20K-token prefix
        # at ~10% of input price instead of paying full price on every round trip.
        if tools:
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
        system_blocks = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]

        account_raw = await mcp.call_tool("get_account_info", {})
        positions_raw = await mcp.call_tool("get_all_positions", {})
        # Every Alpaca MCP tool result is wrapped as {"_alpaca_mcp_security": ..., "data": ...} —
        # get_account_info's `data` is the account dict directly; get_all_positions' `data` is
        # {"result": [...]}, one level deeper. Both must be unwrapped before RiskGate sees them,
        # or it silently treats the account as empty (equity=0, no positions) and auto-rejects
        # every order via the "no account snapshot" guard — verified against a live account.
        try:
            account_info = json.loads(account_raw).get("data", {})
            positions = json.loads(positions_raw).get("data", {}).get("result", [])
            if not isinstance(positions, list):
                positions = []
        except (json.JSONDecodeError, AttributeError):
            account_info, positions = {}, []
        risk_gate.refresh(account_info, positions)

        messages = [{
            "role": "user",
            "content": (
                "Begin this trading cycle. Here is your current account snapshot and positions "
                f"(already fetched, no need to re-call those two tools):\n\nACCOUNT:\n{account_raw}\n\n"
                f"POSITIONS:\n{positions_raw}\n\nProceed with market research and, if warranted, trades."
            ),
        }]

        tool_calls_made = 0
        api_calls_made = 0
        cycle_cost = 0.0
        final_summary = ""
        while tool_calls_made < CONFIG.max_tool_calls_per_cycle:
            response = await anthropic.messages.create(
                model=CONFIG.claude_model,
                max_tokens=2048,
                system=system_blocks,
                tools=tools,
                messages=messages,
            )
            api_calls_made += 1
            call_cost = _call_cost(response.usage, CONFIG.claude_model)
            cycle_cost += call_cost
            log_event(
                "api_call_cost",
                model=CONFIG.claude_model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_creation_input_tokens=getattr(response.usage, "cache_creation_input_tokens", 0),
                cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0),
                call_cost_usd=round(call_cost, 5),
                cycle_cost_so_far_usd=round(cycle_cost, 5),
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                final_summary = "".join(
                    b.text for b in response.content if getattr(b, "type", None) == "text"
                )
                break

            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                tool_calls_made += 1
                decision = {"approved": True}
                if block.name in ORDER_TOOLS:
                    decision = risk_gate.check(block.name, block.input)

                if decision.get("approved"):
                    result_text = await mcp.call_tool(block.name, block.input)
                    if block.name in ORDER_TOOLS:
                        # Alpaca rejecting an order comes back as a normal (non-error) MCP result,
                        # not an exception (see parse_order_error's docstring) -- without this check
                        # every approved order-tool call fired an "order_placed" alert regardless of
                        # whether Alpaca actually accepted it, which would misreport a rejected order
                        # as filled to whoever is watching the alerts channel/log.
                        order_error = parse_order_error(result_text)
                        if order_error:
                            alert("order_rejected", agent="live_agent", tool=block.name,
                                  input=block.input, reason=order_error)
                        else:
                            alert("order_placed", agent="live_agent", tool=block.name, input=block.input)
                    if block.name in ("get_account_info", "get_all_positions"):
                        try:
                            parsed = json.loads(result_text).get("data", {})
                            # Update only the field this tool call actually refreshed -- update_account/
                            # update_positions are independent, so there's no need to reconstruct a fake
                            # stand-in for whichever argument wasn't just re-fetched (and doing so risked
                            # losing state: a synthetic positions list built from risk_gate.open_positions
                            # alone would drop held_option_roots, since option legs live there, not there).
                            if block.name == "get_account_info":
                                risk_gate.update_account(parsed)
                            else:
                                positions_list = parsed.get("result", []) if isinstance(parsed, dict) else []
                                risk_gate.update_positions(positions_list if isinstance(positions_list, list) else [])
                        except (json.JSONDecodeError, TypeError):
                            pass
                else:
                    result_text = json.dumps(decision)
                    reason = decision.get("reason") or ""
                    if "circuit breaker" in reason or "Kill switch" in reason:
                        alert("order_blocked_critical", agent="live_agent", tool=block.name, reason=reason)

                log_event(
                    "tool_call",
                    tool=block.name,
                    input=block.input,
                    approved=decision.get("approved"),
                    reason=decision.get("reason"),
                    # Logged on approvals AND rejections. A rejected order's capital figure is
                    # the evidence that the gate bound real exposure, so it has to survive the
                    # cycle -- it is gone from everywhere else once the tool result is clipped.
                    estimated_capital_at_risk=decision.get("estimated_capital_at_risk"),
                    capital_basis=decision.get("capital_basis"),
                    validation_status=decision.get("validation_status"),
                    result=result_text[:2000],
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": clip_tool_result(result_text),
                })

            messages.append({"role": "user", "content": tool_results})

        log_event("cycle_complete", tool_calls=tool_calls_made, api_calls=api_calls_made,
                   cycle_cost_usd=round(cycle_cost, 5), summary=final_summary,
                   rejections=risk_gate.rejections)
        return {
            "tool_calls": tool_calls_made,
            "api_calls": api_calls_made,
            "cost_usd": round(cycle_cost, 5),
            "summary": final_summary,
            "rejections": risk_gate.rejections,
        }
