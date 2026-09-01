"""Loads logs/backtest_report.json and renders it into the plain-text summary
every LLM agent (single-agent live_agent.py, the multi-agent pipeline) puts in
front of Claude — a statistically-gated "these combinations have actually
cleared the bar" list, not a raw Sharpe ranking. Shared so the two agents
can't drift into describing the same evidence differently.
"""
import json
import os

from agent.config import CONFIG


def load_cleared_symbols() -> set:
    """Root symbols with at least one strategy that passed the validation gate — used by
    RiskGate to hard-block entries on anything unproven, not just steer them away via the
    system prompt. Verified necessary live: a cheaper model traded an unvalidated symbol
    (NVDA) the very first real cycle it ran, because "prefer validated strategies" was only
    prompt-level guidance until this existed."""
    backtest_path = os.path.join(CONFIG.logs_dir, "backtest_report.json")
    if not os.path.exists(backtest_path):
        return set()
    with open(backtest_path) as f:
        backtest_report = json.load(f)
    return {sym for sym, data in backtest_report.items() if data.get("cleared_for_paper")}


def load_backtest_summary() -> str:
    backtest_path = os.path.join(CONFIG.logs_dir, "backtest_report.json")
    if os.path.exists(backtest_path):
        with open(backtest_path) as f:
            backtest_report = json.load(f)
    else:
        backtest_report = {}

    lines = []
    for sym, data in backtest_report.items():
        if "error" in data:
            continue
        cleared = data.get("cleared_for_paper") or []
        if cleared:
            for name in cleared:
                m = data["strategies"][name]["metrics"]
                lines.append(f"  {sym}: {name} PASSED validation "
                              f"(sharpe={m['sharpe']}, win_rate={m['win_rate']:.0%}, "
                              f"mean_return={m['mean_return_pct']:.2%}, trades={m['trades']})")
        else:
            lines.append(f"  {sym}: no strategy passed the backtest validation gate — "
                          f"treat this symbol as unproven, trade it only with extra caution "
                          f"(if at all) and say so explicitly in your rationale")
    return "\n".join(lines) if lines else "  (no backtest report found — run run_backtest.py first)"
