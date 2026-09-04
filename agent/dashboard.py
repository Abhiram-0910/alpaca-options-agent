"""Export one JSON snapshot for the static dashboard: logs/dashboard.json.

This file is a contract between two worktrees -- this repo writes it, the dashboard reads
it. The shape is documented in docs/DASHBOARD-SCHEMA.md; change one and change the other.

Two rules the reader depends on:

  * Nothing here is invented. Every field is copied from an artifact that already exists
    (logs/backtest_report.json, logs/trade_log.jsonl) or fetched live from Alpaca. Where a
    value was never recorded, the key is present and null rather than filled with a
    plausible-looking number. `estimated_capital_at_risk` is null on most gate decisions
    for exactly this reason: the tool_call log site records `approved` and `reason` but not
    the capital figure the gate computed. Only the demonstration path logs it today.
  * It always produces valid JSON. An empty logs/, a missing backtest report, no Alpaca
    credentials and a closed market each degrade to nulls and empty lists, never to an
    exception -- the dashboard has to render on a cold checkout.

    python -m agent.dashboard
"""
import json
import os
import subprocess
from datetime import datetime, timezone

from agent.config import CONFIG

# Free-tier options data is NOT OPRA. Named here so the dashboard cannot imply otherwise.
DATA_FEED = "Alpaca Indicative Pricing Feed, not OPRA"

# 2: `reproducibility` renamed to `determinism` and enriched with per-replay detail,
# and a `counterfactual` section added. The rename is the breaking part.
SCHEMA_VERSION = 2

_ORDER_EVENTS = ("demonstration_order", "multi_agent_order", "deterministic_order",
                 # Closing orders are trades too. Without this the dashboard showed every
                 # position opening and none of them closing, and the exit reason -- which
                 # for the NFP flatten is the entire point of the record -- appeared nowhere.
                 "position_close_order",
                 # Closes logged before position_close_order existed. Carries the symbol and
                 # the exit reason but no order id or fill price, so those stay null.
                 "position_closed")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _engine_commit() -> str | None:
    """Short hash of the engine that produced these numbers. None outside a git checkout."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip() or None
    except Exception:
        return None


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_jsonl(path: str) -> list:
    """Skips unparseable lines rather than failing the whole export. A half-written last
    line is normal when the agent is mid-cycle while this runs."""
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


# --- account ---------------------------------------------------------------

def _blank_account() -> dict:
    return {"equity": None, "last_equity": None, "buying_power": None,
            "options_buying_power": None, "open_position_count": None,
            "account_number": None, "timestamp": _utcnow(), "source": None,
            "source_version": None, "error": None}


def _position_row(symbol, qty, current_price, market_value, unrealized_pl) -> dict:
    return {"symbol": symbol, "qty": _num(qty), "current_price": _num(current_price),
            "market_value": _num(market_value), "unrealized_pl": _num(unrealized_pl)}


def _account_via_cli():
    """Read account and positions through the Alpaca CLI. None when it cannot."""
    from agent import alpaca_cli
    acct = alpaca_cli.get_account()
    positions = alpaca_cli.get_positions()
    if acct is None or positions is None:
        return None
    section = _blank_account()
    section["source"] = "alpaca-cli"
    section["source_version"] = alpaca_cli.version() or None
    section["equity"] = _num(acct.get("equity"))
    section["last_equity"] = _num(acct.get("last_equity"))
    section["buying_power"] = _num(acct.get("buying_power"))
    section["options_buying_power"] = _num(acct.get("options_buying_power"))
    section["account_number"] = acct.get("account_number")
    rows = {p["symbol"]: _position_row(p["symbol"], p.get("qty"), p.get("current_price"),
                                        p.get("market_value"), p.get("unrealized_pl"))
            for p in positions if isinstance(p, dict) and p.get("symbol")}
    section["open_position_count"] = len(rows)
    return section, rows


def _account_via_sdk():
    """Read the same state through alpaca-py. Raises; the caller reports the error."""
    from alpaca.trading.client import TradingClient
    client = TradingClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key,
                           paper=CONFIG.alpaca_paper)
    acct = client.get_account()
    section = _blank_account()
    section["source"] = "alpaca-py"
    section["equity"] = _num(acct.equity)
    section["last_equity"] = _num(acct.last_equity)
    section["buying_power"] = _num(acct.buying_power)
    section["options_buying_power"] = _num(getattr(acct, "options_buying_power", None))
    section["account_number"] = getattr(acct, "account_number", None)
    rows = {p.symbol: _position_row(p.symbol, p.qty, p.current_price, p.market_value,
                                     p.unrealized_pl)
            for p in client.get_all_positions()}
    section["open_position_count"] = len(rows)
    return section, rows


def _account_section() -> dict:
    """Live account state plus open positions, keyed by option symbol for trade marks.

    Read through the Alpaca CLI first and alpaca-py second, with `source` recording which
    one answered. The CLI is the primary surface deliberately -- it is a first-class Alpaca
    product and this is a real dependency on it, refreshed every cycle, not a demonstration.
    The SDK fallback is what keeps a checkout without the binary (the dashboard worktree, a
    fresh clone) rendering a real account rather than an error panel.

    Returns the section and the position map separately because `trades` needs the map.
    """
    if not CONFIG.alpaca_api_key or not CONFIG.alpaca_secret_key:
        section = _blank_account()
        section["error"] = "no Alpaca credentials in environment"
        return section, {}
    try:
        via_cli = _account_via_cli()
        if via_cli is not None:
            return via_cli
    except Exception:
        # Any CLI problem at all is a fallback, never a failure: the SDK below is the
        # authority on whether the account is actually reachable.
        pass
    try:
        return _account_via_sdk()
    except Exception as exc:
        section = _blank_account()
        section["error"] = f"{type(exc).__name__}: {exc}"
        return section, {}


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --- validation ------------------------------------------------------------

def _ci(pair) -> dict:
    """Both bounds, always both keys. A CI that was never computed is (null, null),
    which is not the same as a CI of (0, 0)."""
    if isinstance(pair, (list, tuple)) and len(pair) == 2:
        return {"lower": _num(pair[0]), "upper": _num(pair[1])}
    return {"lower": None, "upper": None}


def _record(symbol, strategy, scope, passed, metrics, mean_ci, sharpe_ci, reasons,
            enabled_for_paper=None) -> dict:
    metrics = metrics or {}
    return {
        "symbol": symbol,
        "strategy": strategy,
        # "primary" is one distinct strategy/symbol pair. The other scopes are re-runs of a
        # pair that already has a primary record -- count pairs by scope == "primary".
        "scope": scope,
        # Did THIS check pass. On a primary record that is the bootstrap-CI gate alone.
        "passed": passed,
        # Did the pair clear for live trading, which is a strictly higher bar: a pair can pass
        # the primary gate and still be refused because the extended retest or the sub-period
        # stability check failed. IWM/covered_call is exactly that case. Headline counts use
        # this field, never `passed` -- confusing them turns "nothing cleared" into "1 cleared".
        # Null on non-primary scopes, where the question does not apply.
        "enabled_for_paper": enabled_for_paper,
        "trades": metrics.get("trades"),
        "win_rate": _num(metrics.get("win_rate")),
        "sharpe": _num(metrics.get("sharpe")),
        "mean_return_pct": _num(metrics.get("mean_return_pct")),
        "total_pnl_dollars": _num(metrics.get("total_pnl_dollars")),
        "mean_return_ci": _ci(mean_ci),
        "sharpe_ci": _ci(sharpe_ci),
        "reasons": list(reasons or []),
    }


def _validation_section(report) -> list:
    """Flattens the nested backtest report into one list of records.

    Four scopes, all in the same list, distinguished by `scope`:
      primary                 -- the 21 strategy/symbol pairs the gate ran on
      extended                -- extended-history retest, only where one was run
      sub_period_first_half   -- stability check on the first half of extended history
      sub_period_second_half  -- and the second

    The half-period records carry sharpe and mean_return_pct only; the engine does not save
    their trade counts or CI bounds, so those stay null. Do not sum trades across scopes.
    """
    records = []
    if not isinstance(report, dict):
        return records
    for symbol, data in report.items():
        if not isinstance(data, dict):
            continue
        for strategy, s in (data.get("strategies") or {}).items():
            if not isinstance(s, dict):
                continue
            records.append(_record(symbol, strategy, "primary", s.get("passed_backtest"),
                                   s.get("metrics"), s.get("mean_return_ci"),
                                   s.get("sharpe_ci"), s.get("reasons"),
                                   enabled_for_paper=s.get("enabled_for_paper")))
            ext = s.get("extended_retest")
            if not isinstance(ext, dict):
                continue
            records.append(_record(symbol, strategy, "extended", ext.get("passed"),
                                   ext.get("metrics"), None, None, ext.get("reasons")))
            sub = ext.get("sub_period_stability")
            if not isinstance(sub, dict):
                continue
            for half, scope in (("first_half", "sub_period_first_half"),
                                ("second_half", "sub_period_second_half")):
                h = sub.get(half)
                if isinstance(h, dict):
                    records.append(_record(symbol, strategy, scope, h.get("passed"), h,
                                           None, None, sub.get("reasons") if half == "first_half" else None))
    return records


# --- gate decisions --------------------------------------------------------

def _gate_decisions(rows: list) -> list:
    """Every RiskGate verdict the log preserves, rejections first.

    Three log shapes carry a verdict: a `tool_call` with an `approved` field (the LLM paths),
    and `demonstration_approved` / `demonstration_rejected` (the demonstration path logs its
    verdict under its own types), normalised here onto one `approved` bool.
    """
    out = []
    for r in rows:
        kind = r.get("type")
        if kind == "tool_call" and "approved" in r:
            out.append({
                "ts": r.get("ts"),
                "approved": r.get("approved"),
                "tool": r.get("tool"),
                "agent": r.get("agent"),
                "reason": r.get("reason"),
                "estimated_capital_at_risk": _num(r.get("estimated_capital_at_risk")),
                "capital_basis": r.get("capital_basis"),
                "validation_status": r.get("validation_status"),
                "symbol": _order_symbol(r.get("input")),
            })
        elif kind in ("demonstration_rejected", "demonstration_approved"):
            out.append({
                "ts": r.get("ts"),
                "approved": kind == "demonstration_approved",
                "tool": "place_option_order",
                "agent": "demonstration",
                "reason": r.get("reason"),
                "estimated_capital_at_risk": _num(r.get("estimated_capital_at_risk")),
                "capital_basis": r.get("capital_basis"),
                "validation_status": r.get("validation_status"),
                "symbol": _order_symbol(r.get("payload")),
            })
    # Newest first, then rejections ahead of approvals: the dashboard's headline is what the
    # gate refused, not what it waved through. Two passes because the sort is stable.
    out.sort(key=lambda d: d["ts"] or "", reverse=True)
    out.sort(key=lambda d: bool(d["approved"]))
    return out


# --- trades ----------------------------------------------------------------

def _order_symbol(payload):
    """Underlying/contract symbol from an order payload, whichever the payload carries."""
    if not isinstance(payload, dict):
        return None
    if payload.get("symbol"):
        return payload["symbol"]
    legs = payload.get("legs")
    if isinstance(legs, list):
        for leg in legs:
            if isinstance(leg, dict) and leg.get("symbol"):
                return leg["symbol"]
    return None


def _leg_symbols(payload) -> list:
    if not isinstance(payload, dict):
        return []
    legs = payload.get("legs")
    if not isinstance(legs, list):
        return [payload["symbol"]] if payload.get("symbol") else []
    return [l["symbol"] for l in legs if isinstance(l, dict) and l.get("symbol")]


def _entry_credit(payload):
    """Net credit per structure, or None.

    On a multi-leg order Alpaca signs the limit price: negative is a credit received,
    positive is a debit paid. A debit is not a credit, so it returns None rather than an
    absolute value that would read as income on the dashboard.
    """
    if not isinstance(payload, dict):
        return None
    price = _num(payload.get("limit_price"))
    if price is None or price >= 0:
        return None
    return abs(price)


def _trades_section(rows: list, positions: dict) -> list:
    out = []
    for r in rows:
        if r.get("type") not in _ORDER_EVENTS:
            continue
        payload = r.get("payload") if isinstance(r.get("payload"), dict) else None
        legs = _leg_symbols(payload)
        if not legs and r.get("leg"):
            legs = [r["leg"]]
        if not legs and r.get("symbol") and r.get("type") in ("position_close_order",
                                                               "position_closed"):
            legs = [r["symbol"]]
        # A leg still showing in the account is open; one that has expired or been closed is
        # simply absent, which is why current_mark is null rather than zero.
        marks = {s: positions[s]["current_price"] for s in legs if s in positions}
        out.append({
            "ts": r.get("ts"),
            "event": r.get("type"),
            "symbol": r.get("symbol") or _order_symbol(payload),
            "strategy": r.get("strategy"),
            # Present only on a close, and the reason the agent gave for closing.
            "exit_reason": r.get("reason"),
            "closing": r.get("type") in ("position_close_order", "position_closed"),
            # Absent on every path except the demonstration one, where it is the whole point.
            "validation_status": r.get("validation_status"),
            "legs": legs,
            "entry_credit": _entry_credit(payload),
            "limit_price": _num(payload.get("limit_price")) if payload else _num(r.get("limit_price")),
            "capital_at_risk": _num(r.get("capital_at_risk")),
            "capital_basis": r.get("capital_basis"),
            "open": bool(marks),
            "current_mark": marks or None,
            "error": r.get("error"),
        })
    out.sort(key=lambda d: d["ts"] or "", reverse=True)
    return out


# --- heartbeats ------------------------------------------------------------

# Enough to cover a full session at a 15-minute interval without unbounded growth.
_HEARTBEAT_LIMIT = 120


def _heartbeats_section(rows: list) -> dict:
    """Proof the agent was alive and deciding, not switched off.

    An account that did not trade for six hours and an agent nobody started produce the same
    empty position list. The difference lives here: `last_seen_at` with `declined` counts is
    a record of six hours of decisions.
    """
    beats = [r for r in rows if r.get("type") == "heartbeat"]
    recent = beats[-_HEARTBEAT_LIMIT:]
    return {
        "last_seen_at": beats[-1].get("ts") if beats else None,
        "total_cycles": len(beats),
        "cycles_traded": sum(1 for b in beats if b.get("traded")),
        "cycles_declined": sum(1 for b in beats if not b.get("traded") and not b.get("error")),
        "cycles_failed": sum(1 for b in beats if b.get("error")),
        "recent": [{
            "ts": b.get("ts"),
            "cycle": b.get("cycle"),
            "action": b.get("action"),
            "market_open": b.get("market_open"),
            "traded": bool(b.get("traded")),
            "entries_blocked": b.get("entries_blocked"),
            "must_be_flat": b.get("must_be_flat"),
            "cycle_cost_usd": _num(b.get("cycle_cost_usd")),
            "session_spend_usd": _num(b.get("session_spend_usd")),
            "consecutive_failures": b.get("consecutive_failures"),
            "error": b.get("error"),
        } for b in recent],
    }


# --- adversarial -----------------------------------------------------------

def _adversarial_section(logs: str) -> dict:
    """The self-test report, if one has been run. Copied through, never re-derived.

    Absent until `python main.py --adversarial` has run; `null` fields say so rather than
    implying a clean result nobody produced.
    """
    report = _read_json(os.path.join(logs, "adversarial.json"))
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        return {"ran_at": None, "attacks_run": None, "blocked": None, "got_through": None,
                "orders_submitted": None, "results": []}
    meta = report.get("meta") or {}
    return {
        "ran_at": meta.get("generated_at"),
        "attacks_run": meta.get("attacks_run"),
        "blocked": meta.get("blocked"),
        "got_through": meta.get("got_through"),
        "masked_by_validation_gate": meta.get("masked_by_validation_gate"),
        # Proof nothing reached the broker, counted on the account either side of the run.
        "orders_submitted": meta.get("orders_submitted"),
        "order_count_source": meta.get("order_count_source"),
        "verdict_basis": meta.get("verdict_basis"),
        "results": report["results"],
    }


# --- fill analysis ---------------------------------------------------------

def _fill_analysis_section(rows: list) -> dict:
    """Indicative quote vs simulated fill, per leg, for every order submitted.

    Answers whether Alpaca's paper fill engine prices against fresher data than the free
    Indicative Pricing Feed lets us see. `mean_delta` is over filled legs only; with no fills
    yet it is null, and null here means "not yet measurable", never "no difference".
    """
    from agent.fill_analysis import realised_pnl
    entries = [r for r in rows if r.get("type") == "fill_analysis"]
    legs = [l for e in entries for l in (e.get("legs") or [])]
    filled = [l for l in legs if l.get("delta") is not None]
    deltas = [l["delta"] for l in filled]
    return {
        "orders_measured": len(entries),
        "legs_measured": len(legs),
        "legs_filled": len(filled),
        "mean_delta": round(sum(deltas) / len(deltas), 4) if deltas else None,
        "legs_above_mid": sum(1 for l in filled if l["delta_sign"] == "above_mid"),
        "legs_below_mid": sum(1 for l in filled if l["delta_sign"] == "below_mid"),
        "legs_at_mid": sum(1 for l in filled if l["delta_sign"] == "at_mid"),
        "delta_sign_convention": "positive = fill printed above the indicative mid we could see",
        "feed": DATA_FEED,
        "realised": realised_pnl(entries),
        "orders": [{
            "ts": e.get("ts"),
            "order_id": e.get("order_id"),
            "context": e.get("context"),
            "order_status": e.get("order_status"),
            "legs_filled": e.get("legs_filled"),
            "error": e.get("error"),
            "legs": e.get("legs") or [],
        } for e in entries],
    }


# --- reproducibility -------------------------------------------------------

def _determinism_section(logs: str) -> dict:
    """Stratified measurement supersedes the pooled one where available."""
    strat = _read_json(os.path.join(logs, "replay_stratified.json"))
    if isinstance(strat, dict) and strat.get("cells"):
        return _determinism_stratified(strat)
    return _determinism_pooled(logs)


def _determinism_stratified(rep: dict) -> dict:
    """Per-cell divergence. There is deliberately no single headline number.

    The previous section reported one pooled figure across every call. That was wrong twice
    over: 31 of 40 replays were a single model in a single role, and the cells turn out to
    span 0% to 98%, so no one number describes the system. Cells, quotability and per-cell
    measures were fixed in agent/replay.py CELL_RULES before the run.
    """
    cells = []
    for c in rep["cells"]:
        cells.append({
            "cell": f"{c['provider']}/{c['model']}/{c['role']}",
            "provider": c["provider"], "model": c["model"], "role": c["role"],
            "n": c["replays_counted"],
            "unique_decisions": c["unique_decisions"],
            "repeats_per_decision": c["repeats_per_decision"],
            "exact": c["exact"], "equivalent": c["equivalent"], "divergent": c["divergent"],
            "divergence_rate": c["divergence_rate"],
            "divergence_rate_ci95": c["divergence_rate_ci95"],
            # False where the responder emits no tool calls at all: "divergent" is then
            # unreachable by construction and the rate above must not be read as determinism.
            "divergence_rate_meaningful": c.get("divergence_rate_meaningful", True),
            "wording_changed": c.get("wording_changed"),
            "wording_changed_rate": c.get("wording_changed_rate"),
            "decision_turns": c["decision_turns"],
            "decision_changed": c["decision_changed"],
            "decision_changed_rate": c["decision_changed_rate"],
            "decision_changed_ci95": c["decision_changed_ci95"],
            "ruling_turns": c.get("ruling_turns"),
            "ruling_changed": c.get("ruling_changed"),
            "ruling_changed_rate": c.get("ruling_changed_rate"),
            "ruling_changed_ci95": c.get("ruling_changed_ci95"),
            "primary_measure": c["primary_measure"],
            "quotable": c["quotable"],
            "caveat": c["caveat"],
            "across_fingerprint_change": c["across_fingerprint_change"],
            "failed_to_replay": c["failed_to_replay"],
        })
    return {
        "design": "stratified by (provider, model, role)",
        "n_per_cell": rep.get("n_per_cell"),
        "pre_registered": rep.get("pre_registered"),
        "conditions": rep.get("conditions"),
        "measured_at": rep.get("generated_at"),
        "headline": rep.get("headline"),
        "pooled_rate": None,
        "pooled_rate_withheld_because": (
            "cells span 0% to 98% divergence, so no single figure describes the system. The "
            "critic runs with tool_choice forced and must not be pooled with a free-choice "
            "cell; the arbiter emits JSON text rather than tool calls and is measured "
            "separately. An earlier 70% pooled figure was 78% one cell and is superseded."),
        "supersedes": "the pooled 40-replay measurement reported before 4 Sep 2026",
        "cells": cells,
    }


def _determinism_pooled(logs: str) -> dict:
    """What replaying past decisions actually showed.

    Of the 77 agentic-trading studies audited in the 2026 literature, none reached the top
    reproducibility tier. Neither does this, and the number below is the measurement rather
    than the claim.
    """
    from agent.replay import summary
    info = summary()
    report = _read_json(os.path.join(logs, "replay_report.json"))
    section = {
        "calls_recorded": info["calls_recorded"],
        "distinct_decisions": info["distinct_decisions"],
        "tier": info["reproducibility"],
        "replays": None, "exact": None, "equivalent": None, "divergent": None,
        "divergence_rate": None,
        "divergence_rate_ci95": {"lower": None, "upper": None, "method": "Wilson score"},
        "divergent_tool_changed": None, "divergent_args_only": None,
        "distinct_decisions_replayed": None, "repeats_per_decision": None,
        "failed_to_replay": None,
        "across_fingerprint_change": None, "conditions": None, "replayed_at": None,
        "headline": None,
        "results": [],
    }
    if isinstance(report, dict):
        section.update({
            "replays": report.get("replays"),
            "exact": report.get("exact"),
            "equivalent": report.get("equivalent"),
            "divergent": report.get("divergent"),
            "divergence_rate": report.get("divergence_rate"),
            "divergence_rate_ci95": report.get("divergence_rate_ci95")
                or {"lower": None, "upper": None, "method": "Wilson score"},
            "divergent_tool_changed": report.get("divergent_tool_changed"),
            "divergent_args_only": report.get("divergent_args_only"),
            "distinct_decisions_replayed": report.get("distinct_decisions_replayed"),
            "repeats_per_decision": report.get("repeats_per_decision"),
            "failed_to_replay": report.get("failed_to_replay"),
            "across_fingerprint_change": report.get("across_fingerprint_change"),
            "conditions": report.get("conditions"),
            "replayed_at": report.get("generated_at"),
            "headline": _determinism_headline(report),
            # Per-replay detail, prose included: a reader checking this claim needs to see
            # what actually differed, not a count.
            "results": report.get("results") or [],
        })
    return section


# --- arbiter ---------------------------------------------------------------

def _arbiter_section(rows: list) -> dict:
    """The third seat: how often it ruled, which way, and whether it was reachable.

    `authority` is the property the whole design rests on, so it is stated in the data and
    not only in prose: the ruling is advisory, and `overruled_critic` counts the times it
    declined to end a cycle -- never the times it caused an order. An order still exists only
    if the deterministic gate approved it, which is why `orders_from_overrule` is read from
    gate decisions rather than from the council.
    """
    rulings = [r for r in rows if r.get("type") == "arbiter_ruling"]
    unavailable = [r for r in rows if r.get("type") in ("arbiter_unavailable", "arbiter_failed")]
    by = {k: sum(1 for r in rulings if r.get("ruling") == k)
          for k in ("proceed", "abandon", "deadlock")}
    return {
        "consulted": len(rulings),
        "unavailable": len(unavailable),
        "rulings": by,
        "overruled_critic": by["proceed"],
        "model": next((r.get("model") for r in reversed(rulings) if r.get("model")), None),
        "authority": ("advisory only — a 'proceed' ruling does not execute anything, it only "
                      "declines to end the cycle, and control then falls through to the same "
                      "strategy cross-check and RiskGate.check() a Critic approval reaches"),
        "invoked_when": "the Critic rejects a trade the Proposer proposed, and only then",
        "fails_closed": ("any ruling other than 'proceed' — including an unparseable or empty "
                          "response, a timeout, or an absent API key — leaves the veto standing"),
        "recent": [{
            "ts": r.get("ts"), "ruling": r.get("ruling"), "rationale": r.get("rationale"),
            "model": r.get("model"), "latency_ms": r.get("latency_ms"),
            "proposal_symbol": r.get("proposal_symbol"),
            "proposal_strategy": r.get("proposal_strategy"),
            "error": r.get("error"),
        } for r in rulings[-25:]],
        "unavailable_reasons": [r.get("reason") or r.get("error") for r in unavailable[-10:]],
    }


def _determinism_headline(report: dict) -> str:
    """One sentence a reader can check against results[]."""
    n = report.get("replays") or 0
    if not n:
        return None
    parts = [f"{n} replays at temperature 0, fixed seed, same model: "
             f"{report.get('exact')} exact, {report.get('equivalent')} equivalent, "
             f"{report.get('divergent')} divergent"]
    rate = report.get("divergence_rate")
    ci = report.get("divergence_rate_ci95") or {}
    # A report written before these fields existed still summarises; it just says less.
    if rate is not None and ci.get("lower") is not None:
        parts.append(f" ({rate:.0%}, 95% CI {ci['lower']:.0%}-{ci['upper']:.0%})")
    parts.append(".")
    changed = report.get("divergent_tool_changed")
    if changed is not None:
        parts.append(f" {changed} of the divergences changed which tool was called, not just "
                     f"its arguments.")
    fp = report.get("across_fingerprint_change")
    if fp is not None:
        parts.append(f" {fp} crossed a system_fingerprint change.")
    return "".join(parts)


# --- counterfactual --------------------------------------------------------

def _counterfactual_section(logs: str) -> dict:
    """What the refused strategies would have returned. Copied through, never re-derived."""
    report = _read_json(os.path.join(logs, "counterfactual.json"))
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        return {"ran_at": None, "window": None, "pairs_refused": None,
                "refused_profitable": None, "total_pnl_dollars_if_all_taken": None,
                "interpretation": None, "caveats": [], "results": []}
    return {
        "ran_at": report.get("generated_at"),
        "window": report.get("window"),
        "engine": report.get("engine"),
        "marks": report.get("marks"),
        "pairs_evaluated": report.get("pairs_evaluated"),
        "pairs_refused": report.get("pairs_refused"),
        "refused_profitable": report.get("refused_profitable"),
        "refused_unprofitable": report.get("refused_unprofitable"),
        "total_pnl_dollars_if_all_taken": report.get("total_pnl_dollars_if_all_taken"),
        "mean_pnl_dollars": report.get("mean_pnl_dollars"),
        "best": report.get("best"),
        "worst": report.get("worst"),
        "interpretation": report.get("interpretation"),
        "caveats": report.get("caveats") or [],
        "results": report.get("results"),
    }


# --- meta ------------------------------------------------------------------

def _bootstrap_meta() -> dict:
    """Method and per-strategy block length, read from the engine rather than restated.

    Block size is not one number: it is ceil(hold_days / step_days) per strategy, so an
    overlapping schedule gets a wider CI and a non-overlapping one collapses to the plain
    i.i.d. bootstrap at 1.
    """
    meta = {
        "method": "percentile bootstrap; circular moving-block where trades overlap",
        "n_boot": None, "ci": None, "seed": None, "block_size_by_strategy": None,
    }
    try:
        import inspect
        from agent.backtest.engine import _block_size_for, STRATEGY_NAMES
        from agent.backtest.metrics import bootstrap_confidence_interval
        defaults = inspect.signature(bootstrap_confidence_interval).parameters
        meta["n_boot"] = defaults["n_boot"].default
        meta["ci"] = defaults["ci"].default
        meta["seed"] = defaults["seed"].default
        meta["block_size_by_strategy"] = {n: _block_size_for(n) for n in STRATEGY_NAMES}
    except Exception:
        pass
    return meta


def _mtime(path: str):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
    except OSError:
        return None


# --- entry point -----------------------------------------------------------

def export_dashboard(path: str = None) -> dict:
    """Write logs/dashboard.json and return the same dict. Never raises on missing inputs."""
    logs = CONFIG.logs_dir
    path = path or os.path.join(logs, "dashboard.json")
    report_path = os.path.join(logs, "backtest_report.json")

    account, positions = _account_section()
    report = _read_json(report_path)
    rows = _read_jsonl(os.path.join(logs, "trade_log.jsonl"))
    validation = _validation_section(report)

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "generated_at": _utcnow(),
            "data_feed": DATA_FEED,
            "engine_commit": _engine_commit(),
            "paper_trading": CONFIG.alpaca_paper,
            "bootstrap": _bootstrap_meta(),
            "backtest_report_generated_at": _mtime(report_path),
            # The two counts the dashboard must not conflate. Pairs are the headline
            # ("21 evaluated, none cleared"); records include the extended and half-period
            # re-runs of pairs already counted.
            "distinct_pairs_evaluated": sum(1 for r in validation if r["scope"] == "primary"),
            "total_validation_records": len(validation),
            "pairs_cleared": sum(1 for r in validation
                                 if r["scope"] == "primary" and r["enabled_for_paper"] is True),
            "pairs_passing_primary_gate": sum(1 for r in validation
                                              if r["scope"] == "primary" and r["passed"] is True),
        },
        "account": account,
        "validation": validation,
        "gate_decisions": _gate_decisions(rows),
        "trades": _trades_section(rows, positions),
        "heartbeats": _heartbeats_section(rows),
        "adversarial": _adversarial_section(logs),
        "fill_analysis": _fill_analysis_section(rows),
        "determinism": _determinism_section(logs),
        "arbiter": _arbiter_section(rows),
        "counterfactual": _counterfactual_section(logs),
    }

    os.makedirs(logs, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)
    return snapshot


if __name__ == "__main__":
    snap = export_dashboard()
    m = snap["meta"]
    print(f"Wrote {os.path.join(CONFIG.logs_dir, 'dashboard.json')}")
    print(f"  validation: {m['distinct_pairs_evaluated']} distinct pairs "
          f"({m['pairs_cleared']} cleared), {m['total_validation_records']} records total")
    print(f"  gate decisions: {len(snap['gate_decisions'])} "
          f"({sum(1 for d in snap['gate_decisions'] if not d['approved'])} rejections)")
    print(f"  trades: {len(snap['trades'])}")
    cf = snap["counterfactual"]
    print(f"  counterfactual: {cf['refused_profitable']}/{cf['pairs_refused']} refused pairs "
          f"profitable, ${cf['total_pnl_dollars_if_all_taken']} total")
    ab = snap["arbiter"]
    print(f"  arbiter: consulted {ab['consulted']}, unavailable {ab['unavailable']}, "
          f"rulings {ab['rulings']}")
    rp = snap["determinism"]
    if rp.get("design"):
        print("  determinism: stratified, per cell (pooled figure deliberately withheld)")
        for c in rp["cells"]:
            dm = "" if c["divergence_rate_meaningful"] else "  [rate meaningless: no tool calls]"
            q = "" if c["quotable"] else "  [not quotable]"
            print(f"      {c['cell']:44s} n={c['n']:>3} div={c['divergence_rate']:>6.1%}{dm}{q}")
    else:
        print(f"  determinism: {rp['calls_recorded']} calls recorded; {rp['replays']} replays "
              f"-> {rp['exact']} exact / {rp['equivalent']} equivalent / {rp['divergent']} divergent"
              + (f" ({rp['divergence_rate']:.0%}, CI "
                 f"{rp['divergence_rate_ci95']['lower']:.0%}-{rp['divergence_rate_ci95']['upper']:.0%})"
                 if rp.get("divergence_rate") is not None else ""))
    fa = snap["fill_analysis"]
    rl = fa["realised"]
    print(f"  fill analysis: {fa['orders_measured']} orders, {fa['legs_filled']}/"
          f"{fa['legs_measured']} legs filled, mean delta {fa['mean_delta']}")
    print(f"  realised P&L : ${rl['realised_pnl_dollars']} gross "
          f"({rl['opening_legs']} opening / {rl['closing_legs']} closing legs, "
          f"round trip complete: {rl['round_trip_complete']})")
    adv = snap["adversarial"]
    print(f"  adversarial: {adv['attacks_run']} attacks, {adv['blocked']} blocked, "
          f"{adv['got_through']} got through, {adv['orders_submitted']} orders submitted")
    hb = snap["heartbeats"]
    print(f"  heartbeats: {hb['total_cycles']} cycles "
          f"({hb['cycles_traded']} traded, {hb['cycles_declined']} declined, "
          f"{hb['cycles_failed']} failed), last seen {hb['last_seen_at']}")
    acct = snap["account"]
    detail = acct["error"] or "equity {}, {} open positions".format(
        acct["equity"], acct["open_position_count"])
    print("  account: " + str(detail))
