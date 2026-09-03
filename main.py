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


async def _run_once(multi_agent: bool = False, provider: str = "openai") -> float:
    await _manage_open_positions()
    if multi_agent:
        from agent.multi_agent import run_cycle as _multi_run_cycle
        from functools import partial
        run_cycle = partial(_multi_run_cycle, provider)
        print(f"Starting multi-agent cycle on {provider} (Proposer -> Critic -> RiskGate)...")
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


def _require_api_key(provider: str) -> None:
    """Fail at the argument check, not six MCP round trips into a cycle.

    Applies to the Proposer/Critic path as well as the single-agent one: multi_agent runs on
    either provider now, so a guard that only ever checked Anthropic would let
    `--multi-agent --provider openai` through with no key and vice versa.
    """
    if provider == "openai" and not CONFIG.openai_api_key:
        raise SystemExit("Set OPENAI_API_KEY in .env first (or use --deterministic to skip the LLM).")
    if provider == "anthropic" and not CONFIG.anthropic_api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env first, or pass --provider openai "
                          "(or use --deterministic to skip the LLM entirely).")


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


async def _run_loop(interval_minutes: int, max_spend: float, multi_agent: bool = False,
                     provider: str = "openai", max_cycles: int = None):
    """Unattended. All the failure handling and wall-clock judgement lives in
    agent/supervisor.py — see that module's docstring for what this used to be missing."""
    from functools import partial
    from agent.supervisor import run_supervised
    return await run_supervised(
        partial(_run_once, multi_agent, provider),
        _manage_open_positions,
        interval_minutes=interval_minutes,
        max_spend=max_spend,
        max_cycles=max_cycles,
    )


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
                              "instead of the single-agent loop. Runs on either provider. "
                              "Combine with --once/--loop.")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="openai",
                         help="LLM provider for both the single-agent and Proposer/Critic paths. "
                              "Default: openai, because ANTHROPIC_API_KEY is not set on this "
                              "deployment and a bare `python main.py --once` has to work.")
    parser.add_argument("--manage-only", action="store_true",
                         help="Just run position/order housekeeping (close positions that hit a "
                              "profit-take/stop-loss/near-expiration, cancel stale orders) and exit — "
                              "no new entries, no Anthropic API call.")
    parser.add_argument("--demonstrate", action="store_true",
                         help="Build the single bounded demonstration spread (see "
                              "agent/demonstration.py) and run it through the full risk gate "
                              "WITHOUT submitting. Requires DEMONSTRATION_MODE=true.")
    parser.add_argument("--max-cycles", type=int, default=None,
                         help="Stop --loop after this many cycles. Unbounded by default; set it "
                              "to bound a verification run.")
    parser.add_argument("--export-dashboard", action="store_true",
                         help="Just write logs/dashboard.json from the existing logs and exit. "
                              "The file is refreshed after every other mode anyway; this is for "
                              "regenerating it without running a cycle.")
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

    from agent.dashboard import export_dashboard

    if args.export_dashboard:
        export_dashboard()
        print("Wrote logs/dashboard.json")
        raise SystemExit(0)

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
            _require_api_key(args.provider)
            asyncio.run(_run_loop(args.interval, args.max_spend, args.multi_agent,
                                   args.provider, args.max_cycles))
        else:
            _require_api_key(args.provider)
            asyncio.run(_run_once(args.multi_agent, args.provider))
    except TradingKilled as exc:
        raise SystemExit(str(exc))
    finally:
        # Refresh the dashboard snapshot whatever the cycle did, including when it failed --
        # a dashboard that silently keeps showing the last successful run is worse than one
        # showing a stale timestamp the reader can see. export_dashboard never raises on
        # missing inputs, but a failure here must not mask the real exception either.
        try:
            export_dashboard()
        except Exception as exc:  # pragma: no cover - belt and braces
            print(f"Could not refresh logs/dashboard.json: {exc}")
