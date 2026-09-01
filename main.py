"""Entry point for the autonomous Alpaca options-trading agent.

Usage:
    python main.py --once                  single-agent: one Claude research-and-trade cycle
    python main.py --loop                  single-agent: run continuously during market hours
    python main.py --loop --interval 15
    python main.py --multi-agent           two-agent pipeline (Proposer -> Critic -> RiskGate):
                                            add --once/--loop to control cadence, same as above
    python main.py --deterministic         run one zero-LLM-cost cycle (agent/deterministic_agent.py):
                                            mechanically trades only symbol/strategy combinations that
                                            passed backtest validation, no Anthropic API call at all
"""
import argparse
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from alpaca.trading.client import TradingClient

from agent.config import CONFIG
from agent.trade_log import log_event
from agent.alerts import alert
from agent.kill_switch import TradingKilled


def market_is_open() -> bool:
    client = TradingClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key, paper=CONFIG.alpaca_paper)
    return client.get_clock().is_open


async def _manage_open_positions():
    """Runs first in every cycle, before any new entry is even considered — closes/cancels
    what needs closing so the entry logic sees accurate, freed-up buying power, and so
    nothing that's already open just sits unmanaged until a human remembers to check it."""
    from agent.order_manager import manage_cycle
    result = await manage_cycle()
    if result["positions_closed"] or result["orders_canceled"]:
        print("Position/order housekeeping:")
        for p in result["positions_closed"]:
            print(f"  closed {p['symbol']} ({p['reason']})")
        for o in result["orders_canceled"]:
            print(f"  canceled stale order on {o['symbol']} (open {o['age_minutes']:.0f} min)")


async def _run_once(multi_agent: bool = False, provider: str = "anthropic") -> float:
    await _manage_open_positions()
    if multi_agent:
        from agent.multi_agent import run_cycle
        print("Starting multi-agent cycle (Proposer -> Critic -> RiskGate)...")
    elif provider == "openai":
        from agent.live_agent_openai import run_cycle
        print(f"Starting trading cycle (OpenAI, {CONFIG.openai_model})...")
    else:
        from agent.live_agent import run_cycle
        print("Starting trading cycle (Anthropic)...")
    result = await run_cycle()
    print(f"\nCycle done — {result['tool_calls']} tool calls, {result['api_calls']} API round trips, "
          f"${result['cost_usd']:.4f} spent, {len(result['rejections'])} risk-gate/critic rejections.")
    print(f"\nAgent summary:\n{result['summary']}")
    return result["cost_usd"]


async def _run_demonstration_once(submit: bool):
    """One bounded, explicitly unvalidated trade. See agent/demonstration.py for why this
    exists and ARCHITECTURE.md for the alternative that was rejected."""
    await _manage_open_positions()
    from agent.demonstration import run_cycle, DEMONSTRATION_STATUS
    import json
    print(f"Demonstration cycle ({'SUBMIT' if submit else 'dry run'}) — {DEMONSTRATION_STATUS}")
    result = await run_cycle(dry_run=not submit)
    if result["order"]:
        print(json.dumps(result["order"], indent=2, default=str))
    for skip in result["skipped"]:
        print(f"  skipped: {skip}")
    for rej in result["rejections"]:
        print(f"  rejected: {rej}")
    if result["submitted"]:
        print("  SUBMITTED — this is an unvalidated demonstration, not an edge claim.")


async def _run_deterministic_once():
    await _manage_open_positions()
    from agent.deterministic_agent import run_cycle
    print("Starting deterministic cycle (no LLM calls)...")
    result = await run_cycle()
    print(f"\nConsidered: {', '.join(result['considered']) or '(none — no symbol cleared backtest validation)'}")
    for order in result["orders_placed"]:
        legs_desc = ", ".join(f"{l['side']} {l['contract']} @ {l['limit_price']}" for l in order["legs"])
        print(f"  PLACED {order['symbol']} / {order['strategy']}: {legs_desc}")
    for skip in result["skipped"]:
        print(f"  skipped: {skip}")
    for rej in result["rejections"]:
        print(f"  rejected: {rej}")


async def _manage_loop(interval_minutes: int):
    while True:
        if market_is_open():
            try:
                await _manage_open_positions()
            except TradingKilled as exc:
                print(f"{exc}")
            except Exception as exc:
                log_event("cycle_error", error=str(exc))
                alert("cycle_error", error=str(exc))
                print(f"Housekeeping cycle failed: {exc}")
        else:
            print("Market closed — skipping housekeeping cycle.")
        print(f"Sleeping {interval_minutes} minutes...\n")
        await asyncio.sleep(interval_minutes * 60)


async def _run_loop(interval_minutes: int, max_spend: float, multi_agent: bool = False, provider: str = "anthropic"):
    session_spend = 0.0
    while True:
        if max_spend > 0 and session_spend >= max_spend:
            print(f"\nSession spend cap reached (${session_spend:.4f} >= ${max_spend:.2f}). Stopping.")
            log_event("session_spend_cap_reached", session_spend_usd=round(session_spend, 5), cap_usd=max_spend)
            alert("session_spend_cap_reached", session_spend_usd=round(session_spend, 5), cap_usd=max_spend)
            return
        if market_is_open():
            try:
                session_spend += await _run_once(multi_agent, provider)
                print(f"Session spend so far: ${session_spend:.4f}"
                      + (f" (cap ${max_spend:.2f})" if max_spend > 0 else ""))
            except TradingKilled as exc:
                print(f"{exc} Waiting for the kill switch to clear...")
            except Exception as exc:
                log_event("cycle_error", error=str(exc))
                alert("cycle_error", error=str(exc))
                print(f"Cycle failed: {exc}")
        else:
            print("Market closed — skipping cycle.")
        print(f"Sleeping {interval_minutes} minutes...\n")
        await asyncio.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run a single Claude-driven cycle and exit.")
    parser.add_argument("--loop", action="store_true", help="Run continuously during market hours.")
    parser.add_argument("--interval", type=int, default=30, help="Minutes between cycles in --loop mode.")
    parser.add_argument("--max-spend", type=float, default=CONFIG.max_session_spend_usd,
                         help="Stop --loop once cumulative measured spend reaches this many dollars "
                              "(0 disables the cap). Ignored in --once mode.")
    parser.add_argument("--deterministic", action="store_true",
                         help="Run one zero-LLM-cost cycle instead — no Anthropic API key needed.")
    parser.add_argument("--multi-agent", action="store_true",
                         help="Use the two-agent Proposer/Critic pipeline (agent/multi_agent.py) "
                              "instead of the single-agent loop. Anthropic only. Combine with --once/--loop.")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic",
                         help="LLM provider for the single-agent path (ignored with --multi-agent, "
                              "which is Anthropic-only). Default: anthropic.")
    parser.add_argument("--manage-only", action="store_true",
                         help="Just run position/order housekeeping (close positions that hit a "
                              "profit-take/stop-loss/near-expiration, cancel stale orders) and exit — "
                              "no new entries, no Anthropic API call.")
    parser.add_argument("--demonstrate", action="store_true",
                         help="Build the single bounded demonstration spread (see "
                              "agent/demonstration.py) and run it through the full risk gate "
                              "WITHOUT submitting. Requires DEMONSTRATION_MODE=true.")
    parser.add_argument("--submit", action="store_true",
                         help="With --demonstrate, actually place the order. Separate flag on "
                              "purpose: the dry run is the default and submitting is a "
                              "deliberate act.")
    args = parser.parse_args()

    if not CONFIG.alpaca_api_key:
        raise SystemExit("Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env first.")
    if not CONFIG.alpaca_paper:
        raise SystemExit(
            "ALPACA_PAPER_TRADE is not true. This project is built and risk-validated for "
            "Alpaca's PAPER trading environment only — refusing to start."
        )

    try:
        if args.manage_only:
            if args.loop:
                asyncio.run(_manage_loop(args.interval))
            else:
                asyncio.run(_manage_open_positions())
        elif args.demonstrate:
            asyncio.run(_run_demonstration_once(args.submit))
        elif args.deterministic:
            asyncio.run(_run_deterministic_once())
        elif args.loop:
            if args.multi_agent and not CONFIG.anthropic_api_key:
                raise SystemExit("Set ANTHROPIC_API_KEY in .env first (--multi-agent is Anthropic-only).")
            if args.provider == "openai" and not args.multi_agent and not CONFIG.openai_api_key:
                raise SystemExit("Set OPENAI_API_KEY in .env first (or use --deterministic to skip the LLM).")
            if args.provider == "anthropic" and not args.multi_agent and not CONFIG.anthropic_api_key:
                raise SystemExit("Set ANTHROPIC_API_KEY in .env first (or use --deterministic to skip the LLM).")
            asyncio.run(_run_loop(args.interval, args.max_spend, args.multi_agent, args.provider))
        else:
            if args.multi_agent and not CONFIG.anthropic_api_key:
                raise SystemExit("Set ANTHROPIC_API_KEY in .env first (--multi-agent is Anthropic-only).")
            if args.provider == "openai" and not args.multi_agent and not CONFIG.openai_api_key:
                raise SystemExit("Set OPENAI_API_KEY in .env first (or use --deterministic to skip the LLM).")
            if args.provider == "anthropic" and not args.multi_agent and not CONFIG.anthropic_api_key:
                raise SystemExit("Set ANTHROPIC_API_KEY in .env first (or use --deterministic to skip the LLM).")
            asyncio.run(_run_once(args.multi_agent, args.provider))
    except TradingKilled as exc:
        raise SystemExit(str(exc))
