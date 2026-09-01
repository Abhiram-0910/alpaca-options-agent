"""Structured post-mortems for every closed position — the self-learning loop,
designed deliberately NOT to be "avoid what lost money."

A strategy with a real, validated edge still loses on a predictable fraction
of its trades — GOOGL cash_secured_put's own backtest win rate is 70%,
meaning 30% of *correctly executed* trades lose. A naive "learn from losses"
loop would spend its entire learning budget trying to unlearn a real edge
based on ordinary variance, which would directly contradict the statistical
discipline this whole project is built on. So this module never grades a
trade by whether it made money. It checks two things instead:

1. Process, not outcome: did entry actually respect what RiskGate is supposed
   to guarantee (backtest-cleared symbol, DTE bounds, position size)? With the
   hard gates in agent/risk/gates.py, this should almost always be clean by
   construction — a flag here means something slipped through, which is the
   actual signal worth surfacing, not "this trade happened to lose."
2. Realized-vs-backtested drift: once there's enough live history, is the
   strategy's live win rate/return still tracking what the backtest predicted,
   or has the edge stopped working? That comparison — not any single trade's
   result — is the statistically honest version of "is this still working."

No fine-tuning happens anywhere here. The summary this module produces is
injected as plain context into the next cycle's prompt (agent/live_agent.py,
agent/live_agent_openai.py, agent/multi_agent.py) — informational continuity,
not a weight update.
"""
import json
import os
import statistics
from datetime import datetime, timezone

from agent.config import CONFIG
from agent.risk.gates import parse_occ_symbol

REFLECTION_LOG_PATH = os.path.join(CONFIG.logs_dir, "reflection_log.jsonl")
TRADE_LOG_PATH = os.path.join(CONFIG.logs_dir, "trade_log.jsonl")


def _load_trade_log() -> list:
    if not os.path.exists(TRADE_LOG_PATH):
        return []
    entries = []
    with open(TRADE_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _find_entry_event(symbol: str) -> dict:
    """Best-effort: scan trade_log.jsonl backwards for the most recent
    order-placing event that opened this exact contract, to recover which
    agent/strategy opened it. Entry events are logged with different shapes
    per agent (deterministic_order, multi_agent_order, tool_call), so each
    is matched on its own field names rather than assuming one schema."""
    for e in reversed(_load_trade_log()):
        etype = e.get("type")
        if etype == "deterministic_order" and e.get("leg") == symbol:
            return {"agent": "deterministic", "strategy": e.get("strategy"),
                     "cleared_metrics": e.get("strategy_metrics")}
        if etype == "multi_agent_order" and e.get("leg") == symbol:
            return {"agent": "multi_agent", "strategy": e.get("strategy")}
        if etype == "tool_call" and e.get("tool") == "place_option_order":
            inp = e.get("input") or {}
            if inp.get("symbol") == symbol and e.get("approved"):
                return {"agent": e.get("agent", "live_agent"), "strategy": None}
    return None


def _process_checks(entry_event: dict) -> dict:
    """Objective, deterministic, outcome-independent checks. Since RiskGate
    hard-blocks unvalidated symbols/oversized positions/bad DTE at entry time,
    a clean pass here is the *expected* result, not a reward for a good
    outcome — the check exists to catch anything that slipped through."""
    found = entry_event is not None
    checks = {"entry_event_found": found}
    if not found:
        checks["note"] = ("no matching entry event in trade_log.jsonl — either the log rotated, "
                           "or this position was opened outside this system")
    return checks


def record_closed_position(symbol: str, exit_reason: str, plpc: float, strategy_hint: str = None) -> dict:
    """De-dupes by symbol: order_manager submits a close order every cycle a position still
    qualifies for one, and on a thin/illiquid contract that order can go unfilled and get
    resubmitted cycle after cycle — verified live. Without this guard, each resubmission would
    log another "closed" entry for a position that never actually closed, silently corrupting
    both the win-rate math in summarize_for_prompt() and the drift comparison. One entry per
    symbol is kept; if the same symbol opens again later, delete or archive the old entry first."""
    if any(e.get("symbol") == symbol for e in _load_all()):
        return None

    entry_event = _find_entry_event(symbol)
    checks = _process_checks(entry_event)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "root": (parse_occ_symbol(symbol) or {}).get("root", symbol),
        "strategy": (entry_event or {}).get("strategy") or strategy_hint,
        "agent": (entry_event or {}).get("agent", "unknown"),
        "exit_reason": exit_reason,
        "realized_return_pct": plpc,
        "process_checks": checks,
        "is_process_flag": not checks["entry_event_found"],
    }
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    with open(REFLECTION_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry


def _load_all() -> list:
    if not os.path.exists(REFLECTION_LOG_PATH):
        return []
    out = []
    with open(REFLECTION_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def summarize_for_prompt(max_entries: int = 10) -> str:
    """What gets injected into the next cycle's system prompt. Reports facts
    (what closed, how, process flags) — never a prescriptive "lesson" derived
    from win/loss, since that's exactly the conflation this module exists to
    avoid."""
    entries = _load_all()
    if not entries:
        return "  (no closed positions yet — nothing to report)"
    recent = entries[-max_entries:]
    lines = []
    for e in recent:
        flag = " [PROCESS FLAG]" if e.get("is_process_flag") else ""
        pct = e.get("realized_return_pct")
        pct_str = f"{pct:.1%}" if isinstance(pct, (int, float)) else "n/a"
        lines.append(f"  {e['symbol']} ({e.get('strategy') or 'unknown strategy'}): "
                      f"{e['exit_reason']}, realized {pct_str}{flag}")
    n_flagged = sum(1 for e in entries if e.get("is_process_flag"))
    lines.append(f"  ({len(entries)} total closed positions logged, {n_flagged} with a process flag — "
                  f"a flag means a data/logging gap or a slipped gate, not that the trade lost money)")
    return "\n".join(lines)


def strategy_drift_report(strategy_name: str, root_symbol: str, min_live_trades: int = 10) -> dict:
    """Compares REALIZED performance against what the backtest predicted for
    this exact strategy/symbol — the statistically honest question ("is the
    edge still there?"), never asked about a single trade."""
    entries = [e for e in _load_all() if e.get("strategy") == strategy_name and e.get("root") == root_symbol]
    if len(entries) < min_live_trades:
        return {"status": "insufficient_live_trades", "live_trades": len(entries), "need": min_live_trades}

    live_returns = [e["realized_return_pct"] for e in entries if isinstance(e.get("realized_return_pct"), (int, float))]
    if not live_returns:
        return {"status": "insufficient_live_trades", "live_trades": len(entries), "need": min_live_trades}
    live_win_rate = sum(1 for r in live_returns if r > 0) / len(live_returns)
    return {
        "status": "comparable",
        "live_trades": len(entries),
        "live_win_rate": round(live_win_rate, 3),
        "live_mean_return_pct": round(statistics.mean(live_returns), 5),
    }
