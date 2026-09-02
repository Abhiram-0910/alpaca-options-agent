"""The autonomous agent loop — OpenAI (GPT) version.

Structurally identical to agent/live_agent.py (same risk gate, same MCP
server, same system prompt content, same backtest evidence, same kill
switch), swapping only the LLM call layer: OpenAI's Chat Completions
function-calling API instead of Anthropic's tool-use API. Verified against
the real OpenAI API with a minimal round trip before this was written (see
session notes) rather than assumed correct from training data.
"""
import json

from openai import AsyncOpenAI

from agent.config import CONFIG, assert_paper_trading
from agent.mcp.client import AlpacaMCPClient
from agent.risk.gates import RiskGate, ORDER_TOOLS
from agent.trade_log import log_event
from agent.kill_switch import assert_not_killed
from agent.alerts import alert
from agent.openai_cost import call_cost
from agent.backtest_evidence import load_backtest_summary
from agent.reflection import summarize_for_prompt
from agent.live_agent import _build_system_prompt
from agent.mcp_parsers import parse_order_error, clip_tool_result


def _to_openai_tools(mcp_tools: list) -> list:
    """Alpaca's MCP tools come back as {"name", "description", "input_schema"}
    (Anthropic's tool-use shape) — OpenAI's function-calling shape nests the same
    fields one level deeper under "function"."""
    return [
        {"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
        }}
        for t in mcp_tools
    ]


async def run_cycle() -> dict:
    assert_paper_trading()
    assert_not_killed()

    backtest_summary = load_backtest_summary()
    reflection_summary = summarize_for_prompt()
    system_prompt = _build_system_prompt(backtest_summary, reflection_summary)
    client = AsyncOpenAI(api_key=CONFIG.openai_api_key)
    risk_gate = RiskGate()

    async with AlpacaMCPClient() as mcp:
        mcp_tools = await mcp.list_tools_anthropic_format()
        tools = _to_openai_tools(mcp_tools)

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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                "Begin this trading cycle. Here is your current account snapshot and positions "
                f"(already fetched, no need to re-call those two tools):\n\nACCOUNT:\n{account_raw}\n\n"
                f"POSITIONS:\n{positions_raw}\n\nProceed with market research and, if warranted, trades."
            )},
        ]

        tool_calls_made = 0
        api_calls_made = 0
        cycle_cost = 0.0
        final_summary = ""
        while tool_calls_made < CONFIG.max_tool_calls_per_cycle:
            response = await client.chat.completions.create(
                model=CONFIG.openai_model, messages=messages, tools=tools, max_tokens=2048,
            )
            api_calls_made += 1
            call_cost_usd = call_cost(response.usage, CONFIG.openai_model)
            cycle_cost += call_cost_usd
            log_event(
                "api_call_cost", provider="openai", model=CONFIG.openai_model,
                prompt_tokens=response.usage.prompt_tokens, completion_tokens=response.usage.completion_tokens,
                cached_tokens=getattr(response.usage.prompt_tokens_details, "cached_tokens", 0),
                call_cost_usd=round(call_cost_usd, 6), cycle_cost_so_far_usd=round(cycle_cost, 6),
            )

            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if response.choices[0].finish_reason != "tool_calls" or not msg.tool_calls:
                final_summary = msg.content or ""
                break

            for tc in msg.tool_calls:
                tool_calls_made += 1
                name = tc.function.name
                try:
                    tool_input = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_input = {}

                decision = {"approved": True}
                if name in ORDER_TOOLS:
                    decision = risk_gate.check(name, tool_input)

                if decision.get("approved"):
                    result_text = await mcp.call_tool(name, tool_input)
                    if name in ORDER_TOOLS:
                        # See the matching comment in agent/live_agent.py: Alpaca rejecting an
                        # order is a normal non-error MCP result, not an exception, so this used
                        # to fire "order_placed" even for an order Alpaca actually rejected.
                        order_error = parse_order_error(result_text)
                        if order_error:
                            alert("order_rejected", agent="live_agent_openai", tool=name,
                                  input=tool_input, reason=order_error)
                        else:
                            alert("order_placed", agent="live_agent_openai", tool=name, input=tool_input)
                    if name in ("get_account_info", "get_all_positions"):
                        try:
                            parsed = json.loads(result_text).get("data", {})
                            # Update only the field this tool call actually refreshed -- see the matching
                            # comment in agent/live_agent.py for why reconstructing a fake stand-in for the
                            # other argument here was both unnecessary and (post risk-gate refactor) lossy.
                            if name == "get_account_info":
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
                        alert("order_blocked_critical", agent="live_agent_openai", tool=name, reason=reason)

                log_event("tool_call", agent="openai", tool=name, input=tool_input,
                          approved=decision.get("approved"), reason=decision.get("reason"),
                          # Logged on approvals AND rejections -- see the matching comment in
                          # live_agent.py.
                          estimated_capital_at_risk=decision.get("estimated_capital_at_risk"),
                          capital_basis=decision.get("capital_basis"),
                          validation_status=decision.get("validation_status"),
                          result=result_text[:2000])
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": clip_tool_result(result_text)})

        log_event("cycle_complete", agent="openai", tool_calls=tool_calls_made, api_calls=api_calls_made,
                   cycle_cost_usd=round(cycle_cost, 6), summary=final_summary, rejections=risk_gate.rejections)
        return {
            "tool_calls": tool_calls_made,
            "api_calls": api_calls_made,
            "cost_usd": round(cycle_cost, 6),
            "summary": final_summary,
            "rejections": risk_gate.rejections,
        }
