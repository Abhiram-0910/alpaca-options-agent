"""One command, run before the open, that checks everything the session needs.

Each check answers a single question that could otherwise only be answered by the session
failing. Every one is a real probe -- a credential is used, a process is spawned, a chain is
fetched -- never a "does the setting look present" inspection, because a config value that
looks right and does not work is the exact failure this exists to catch.

Exit code is 0 only when nothing is RED. WARN does not fail the run: a warning is something
that degrades the session without stopping it, and the operator gets to decide.

    python main.py --preflight
"""
import asyncio
import json
import os
import shutil
import time
from datetime import date, datetime, timedelta, timezone

from agent.config import CONFIG

GREEN, RED, WARN = "GREEN", "RED", "WARN"
MIN_FREE_DISK_MB = 200


class Check:
    def __init__(self, name, status, detail, seconds=None):
        self.name, self.status, self.detail, self.seconds = name, status, detail, seconds

    def as_dict(self):
        return {"name": self.name, "status": self.status, "detail": self.detail,
                "seconds": None if self.seconds is None else round(self.seconds, 2)}


def _timed(fn):
    t0 = time.monotonic()
    try:
        status, detail = fn()
    except Exception as exc:
        status, detail = RED, f"{type(exc).__name__}: {exc}"
    return status, detail, time.monotonic() - t0


# --- individual checks -----------------------------------------------------

def _check_credentials():
    missing = [n for n, v in (("ALPACA_API_KEY", CONFIG.alpaca_api_key),
                              ("ALPACA_SECRET_KEY", CONFIG.alpaca_secret_key)) if not v]
    if missing:
        return RED, f"missing: {', '.join(missing)}"
    if not CONFIG.alpaca_paper:
        return RED, "ALPACA_PAPER_TRADE is not true; this project has no live path"
    llm = "openai" if CONFIG.openai_api_key else ("anthropic" if CONFIG.anthropic_api_key else None)
    if not llm:
        return RED, "no LLM key set; neither the single-agent nor multi-agent path can run"
    extra = "" if os.environ.get("FEATHERLESS_API_KEY") else \
        "; FEATHERLESS_API_KEY absent, so the arbiter seat is unavailable and every Critic veto stands"
    return (GREEN if not extra else WARN), f"Alpaca paper + {llm}{extra}"


def _check_account():
    """Real API call, not a key-length check."""
    from alpaca.trading.client import TradingClient
    client = TradingClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key, paper=True)
    acct = client.get_account()
    if not str(acct.account_number).startswith("PA"):
        return RED, f"account {acct.account_number} does not look like a paper account"
    if str(acct.status).upper().endswith("ACTIVE") is False and "ACTIVE" not in str(acct.status).upper():
        return RED, f"account status is {acct.status}"
    equity = float(acct.equity)
    if equity <= 0:
        return RED, f"equity is {equity}"
    return GREEN, (f"{acct.account_number} {acct.status}, equity ${equity:,.0f}, "
                   f"options level {getattr(acct, 'options_trading_level', '?')}")


def _check_clock():
    from alpaca.trading.client import TradingClient
    client = TradingClient(CONFIG.alpaca_api_key, CONFIG.alpaca_secret_key, paper=True)
    clock = client.get_clock()
    drift = abs((datetime.now(timezone.utc) - clock.timestamp).total_seconds())
    state = "OPEN" if clock.is_open else "closed"
    detail = (f"market {state}, next open {clock.next_open:%Y-%m-%d %H:%M %Z}, "
              f"local clock drift {drift:.1f}s")
    # A large drift matters here: the session-window rules are wall-clock rules.
    return (WARN if drift > 60 else GREEN), detail


def _check_cli():
    from agent import alpaca_cli
    if not alpaca_cli.binary_path():
        return WARN, "alpaca CLI not installed; the export falls back to alpaca-py"
    acct = alpaca_cli.get_account()
    if acct is None:
        return WARN, "alpaca CLI installed but not authenticated; export falls back to alpaca-py"
    return GREEN, f"CLI {alpaca_cli.version()} authenticated as {acct.get('account_number')}"


def _check_kill_switch():
    from agent.kill_switch import is_active, reason
    if is_active():
        return RED, f"KILL SWITCH IS ACTIVE: {reason()}"
    return GREEN, "off; orders are permitted subject to every other gate"


def _check_session_window():
    from agent.session_window import entries_blocked, must_be_flat, LAST_TRADING_DAY
    blocked, flat = entries_blocked(), must_be_flat()
    if flat:
        return WARN, f"must be flat: {flat}"
    if blocked:
        return WARN, f"no new entries: {blocked}"
    return GREEN, f"entries permitted; last trading day is {LAST_TRADING_DAY}"


def _check_gate_armed():
    """The gate must REFUSE something it should refuse -- and refuse it for the right reason.

    A first version of this check passed while proving almost nothing: with nothing cleared
    for paper, the validation gate refuses every order first, so the capital cap could have
    been entirely broken and this would still have read GREEN. It now runs the probe twice,
    once with validation satisfied, so the capital cap is the layer actually under test.
    """
    from agent.risk.gates import RiskGate
    from agent.adversarial import _validation_satisfied

    def probe():
        gate = RiskGate()
        gate.refresh({"equity": "100000", "last_equity": "100000"}, [])
        exp = date.today() + timedelta(days=2)
        return gate.check("place_option_order", {
            "symbol": f"SPY{exp:%y%m%d}P00755000", "side": "sell", "qty": 400,
            "limit_price": "1.20"})

    full = probe()
    if full.get("approved"):
        return RED, "gate APPROVED a 400-contract naked short put; it is not armed"
    with _validation_satisfied():
        capped = probe()
    if capped.get("approved"):
        return RED, ("capital cap is NOT armed: with validation satisfied the gate approved "
                     "a 400-contract short put")
    cap_reason = capped.get("reason") or ""
    if "capital at risk" not in cap_reason:
        return WARN, f"refused, but not by the capital cap: {cap_reason[:80]}"
    ok = RiskGate().check("get_account_info", {})
    if not ok.get("approved"):
        return RED, "gate rejected a non-order tool call; it is over-blocking"
    return GREEN, f"capital cap refused it: {cap_reason[:66]}"


def _check_dashboard_writable():
    from agent.dashboard import export_dashboard
    snap = export_dashboard()
    path = os.path.join(CONFIG.logs_dir, "dashboard.json")
    size = os.path.getsize(path)
    if size < 100:
        return RED, f"dashboard.json is only {size} bytes"
    return GREEN, (f"wrote {path} ({size / 1024:.0f} KB), account source "
                   f"{snap['account'].get('source')}")


def _check_disk():
    usage = shutil.disk_usage(CONFIG.logs_dir if os.path.isdir(CONFIG.logs_dir) else ".")
    free_mb = usage.free / (1024 * 1024)
    if free_mb < MIN_FREE_DISK_MB:
        return RED, f"only {free_mb:.0f} MB free (need {MIN_FREE_DISK_MB} MB)"
    return GREEN, f"{free_mb / 1024:.1f} GB free"


# --- async checks (MCP + chain) --------------------------------------------

async def _check_mcp_and_chain() -> list:
    """Spawn the MCP server for real and fetch a real chain through it.

    These are one connection deliberately: the expensive, most-likely-to-fail step is
    starting the server, and doing it twice doubles the risk for no information.
    """
    from agent.mcp.client import AlpacaMCPClient
    from agent.mcp_parsers import parse_option_chain_snapshot
    from agent.demonstration import SYMBOL, DEMONSTRATION_EXPIRY

    out = []
    t0 = time.monotonic()
    try:
        async with AlpacaMCPClient() as mcp:
            tools = await mcp.list_tools_anthropic_format()
            out.append(Check("MCP server", GREEN,
                             f"spawned, {len(tools)} tools exposed", time.monotonic() - t0))

            t1 = time.monotonic()
            raw = await mcp.call_tool("get_option_chain", {
                "underlying_symbol": SYMBOL,
                "expiration_date_gte": date.today().isoformat(),
                "expiration_date_lte": (date.today() + timedelta(days=6)).isoformat(),
                "limit": 400})
            quotes = parse_option_chain_snapshot(raw)
            expiries = {q.expiry for q in quotes if getattr(q, "expiry", None)}
            if not quotes:
                out.append(Check("Option chain", RED,
                                 f"{SYMBOL} chain returned no quotes", time.monotonic() - t1))
            else:
                out.append(Check("Option chain", GREEN,
                                 f"{SYMBOL}: {len(quotes)} quotes across "
                                 f"{len(expiries)} expiries", time.monotonic() - t1))

            target = DEMONSTRATION_EXPIRY
            if target in expiries:
                strikes = sum(1 for q in quotes if getattr(q, "expiry", None) == target)
                out.append(Check("Demonstration expiry", GREEN,
                                 f"{target} listed with {strikes} contracts"))
            else:
                out.append(Check("Demonstration expiry", RED,
                                 f"{target} NOT in the chain; offered "
                                 f"{', '.join(str(e) for e in sorted(expiries)[:6])}"))
    except Exception as exc:
        out.append(Check("MCP server", RED, f"{type(exc).__name__}: {exc}",
                         time.monotonic() - t0))
        out.append(Check("Option chain", RED, "skipped; MCP did not start"))
        out.append(Check("Demonstration expiry", RED, "skipped; MCP did not start"))
    return out


# --- runner ----------------------------------------------------------------

SYNC_CHECKS = [
    ("Credentials", _check_credentials),
    ("Alpaca account", _check_account),
    ("Market clock", _check_clock),
    ("Alpaca CLI", _check_cli),
    ("Kill switch", _check_kill_switch),
    ("Session window", _check_session_window),
    ("Risk gate armed", _check_gate_armed),
    ("Dashboard writable", _check_dashboard_writable),
    ("Disk space", _check_disk),
]


async def run_preflight(path: str = None) -> dict:
    path = path or os.path.join(CONFIG.logs_dir, "preflight.json")
    checks = []
    for name, fn in SYNC_CHECKS:
        status, detail, secs = _timed(fn)
        checks.append(Check(name, status, detail, secs))
    checks.extend(await _check_mcp_and_chain())

    reds = [c for c in checks if c.status == RED]
    warns = [c for c in checks if c.status == WARN]
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready": not reds,
        "red": len(reds), "warn": len(warns),
        "green": len(checks) - len(reds) - len(warns),
        "checks": [c.as_dict() for c in checks],
    }
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return report


def print_report(report: dict) -> None:
    mark = {GREEN: "GREEN", RED: "RED  ", WARN: "WARN "}
    print("\nPRE-FLIGHT")
    print("-" * 76)
    for c in report["checks"]:
        secs = f"{c['seconds']:>5.2f}s" if c["seconds"] is not None else "      "
        print(f"  [{mark[c['status']]}] {c['name']:<22s} {secs}  {c['detail']}")
    print("-" * 76)
    print(f"  {report['green']} green, {report['warn']} warn, {report['red']} red — "
          + ("READY" if report["ready"] else "NOT READY"))
