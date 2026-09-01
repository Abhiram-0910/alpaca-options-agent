"""Manual kill switch for the trading agent — a lever independent of every
other risk gate. While active, RiskGate rejects every order-placing tool
call, and both live_agent.run_cycle() and deterministic_agent.run_cycle()
refuse to even start (saving Anthropic spend on a killed session too).

Usage:
    python kill_switch.py status
    python kill_switch.py on ["reason"]
    python kill_switch.py on ["reason"] --cancel-all   # also cancels every open order now
    python kill_switch.py off
"""
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.kill_switch import activate, deactivate, is_active, reason as kill_reason, KILL_SWITCH_PATH
from agent.alerts import alert


async def _cancel_all_orders():
    from agent.mcp.client import AlpacaMCPClient
    async with AlpacaMCPClient() as mcp:
        result = await mcp.call_tool("cancel_all_orders", {})
        print(f"cancel_all_orders result: {result[:500]}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in ("status", "on", "off"):
        print(__doc__)
        raise SystemExit(1)

    cmd = args[0]
    if cmd == "status":
        if is_active():
            print(f"KILL SWITCH IS ACTIVE: {kill_reason()}")
        else:
            print("Kill switch is not active. Trading is allowed (subject to every other risk gate).")

    elif cmd == "on":
        cancel_all = "--cancel-all" in args
        reason_parts = [a for a in args[1:] if a != "--cancel-all"]
        why = " ".join(reason_parts) or "manually activated"
        activate(why)
        alert("kill_switch_activated", reason=why, cancel_all=cancel_all)
        print(f"Kill switch ACTIVATED ({KILL_SWITCH_PATH}): {why}")
        print("No new orders will be placed until you run `python kill_switch.py off`.")
        if cancel_all:
            asyncio.run(_cancel_all_orders())

    elif cmd == "off":
        was_active = is_active()
        deactivate()
        if was_active:
            alert("kill_switch_deactivated")
            print("Kill switch deactivated. Trading is allowed again (subject to every other risk gate).")
        else:
            print("Kill switch was not active.")
