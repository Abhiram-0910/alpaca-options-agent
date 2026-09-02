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

SCHEMA_VERSION = 1

_ORDER_EVENTS = ("demonstration_order", "multi_agent_order", "deterministic_order")


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

def _account_section() -> dict:
    """Live account state plus open positions, keyed by option symbol for trade marks.

    Returns the section and the position map separately because `trades` needs the map.
    """
    section = {"equity": None, "last_equity": None, "buying_power": None,
               "options_buying_power": None, "open_position_count": None,
               "account_number": None, "timestamp": _utcnow(), "error": None}
    positions = {}
    if not CONFIG.alpaca_api_key or not CONFIG.alpaca_secret_key:
        section["error"] = "no Alpaca credentials in environment"
        return section, positions
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key,
                               paper=CONFIG.alpaca_paper)
        acct = client.get_account()
        section["equity"] = _num(acct.equity)
        section["last_equity"] = _num(acct.last_equity)
        section["buying_power"] = _num(acct.buying_power)
        section["options_buying_power"] = _num(getattr(acct, "options_buying_power", None))
        section["account_number"] = getattr(acct, "account_number", None)
        for p in client.get_all_positions():
            positions[p.symbol] = {
                "symbol": p.symbol,
                "qty": _num(p.qty),
                "current_price": _num(p.current_price),
                "market_value": _num(p.market_value),
                "unrealized_pl": _num(p.unrealized_pl),
            }
        section["open_position_count"] = len(positions)
    except Exception as exc:
        section["error"] = f"{type(exc).__name__}: {exc}"
    return section, positions


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

    Two log shapes carry a verdict: a `tool_call` with an `approved` field (the LLM paths),
    and `demonstration_rejected` (the demonstration path, which logs the rejection under its
    own type). The tool_call site does not record the capital figure, hence the null.
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
                "validation_status": r.get("validation_status"),
                "symbol": _order_symbol(r.get("input")),
            })
        elif kind == "demonstration_rejected":
            out.append({
                "ts": r.get("ts"),
                "approved": False,
                "tool": "place_option_order",
                "agent": "demonstration",
                "reason": r.get("reason"),
                "estimated_capital_at_risk": _num(r.get("estimated_capital_at_risk")),
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
        # A leg still showing in the account is open; one that has expired or been closed is
        # simply absent, which is why current_mark is null rather than zero.
        marks = {s: positions[s]["current_price"] for s in legs if s in positions}
        out.append({
            "ts": r.get("ts"),
            "event": r.get("type"),
            "symbol": r.get("symbol") or _order_symbol(payload),
            "strategy": r.get("strategy"),
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
    acct = snap["account"]
    detail = acct["error"] or "equity {}, {} open positions".format(
        acct["equity"], acct["open_position_count"])
    print("  account: " + str(detail))
