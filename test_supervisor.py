"""The supervised loop has to survive the night alone, so the paths that matter are the
ones a live verification run cannot produce on demand: a cycle raising, three raising in a
row, the spend cap biting on measured cost, and the session-window rules firing on wall
clock with nobody there to notice it is 15:00 ET.

Driven over injected callables and an injected clock, so no LLM is called and no order is
placed. The wall-clock cases use agent/session_window.py's real rules at fixed instants.

    python test_supervisor.py
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import agent.config as config_mod
import agent.trade_log as trade_log
import agent.kill_switch as kill_switch_mod
import agent.supervisor as sup
from agent.supervisor import run_supervised, MAX_CONSECUTIVE_FAILURES

ET = ZoneInfo("America/New_York")


def _run(tmp, **kwargs):
    """Run the real loop against a scratch logs dir; return (summary, heartbeat records)."""
    scratch = config_mod.Config(logs_dir=tmp, alpaca_api_key="", alpaca_secret_key="")
    originals = (trade_log.CONFIG, kill_switch_mod.CONFIG, sup.CONFIG)
    trade_log.CONFIG = kill_switch_mod.CONFIG = sup.CONFIG = scratch
    kill_switch_mod.KILL_SWITCH_PATH = os.path.join(tmp, "KILL_SWITCH")
    # Never touch the real dashboard from a test.
    real_refresh = sup._dashboard_refresh
    sup._dashboard_refresh = lambda: "skipped (test)"
    try:
        summary = asyncio.run(run_supervised(
            kwargs.pop("run_once"), kwargs.pop("manage_positions"),
            sleep_fn=lambda _s: asyncio.sleep(0), **kwargs))
    finally:
        sup._dashboard_refresh = real_refresh
        trade_log.CONFIG, kill_switch_mod.CONFIG, sup.CONFIG = originals
    rows = [json.loads(l) for l in open(os.path.join(tmp, "trade_log.jsonl")) if l.strip()]
    return summary, [r for r in rows if r["type"] == "heartbeat"]


async def _noop():
    return 0.0


# The gate consults session_window on the wall clock, and this repo's window closed at
# 15:45 ET on 3 Sep 2026. After that instant every gate check is refused with "no new
# positions" BEFORE it reaches the layer under test, so these assertions started failing on
# 4 Sep for a reason that has nothing to do with the code. Pin the clock to a moment inside
# the trading window: the rule itself is unmodified and is covered by
# agent/session_window.py's own self-check.
import agent.session_window as _sw
from datetime import datetime as _dt
from zoneinfo import ZoneInfo as _Z
_sw._now_et = lambda: _dt(2026, 9, 3, 11, 0, tzinfo=_Z("America/New_York"))


def demo() -> None:
    # 1. A heartbeat on every pass, including passes that do nothing. This is what makes an
    #    empty stretch provably a decision rather than a switched-off agent.
    with tempfile.TemporaryDirectory() as tmp:
        summary, beats = _run(tmp, run_once=_noop, manage_positions=_noop, max_cycles=3,
                              market_is_open=lambda: False)
        assert summary["cycles"] == 3, summary
        assert len(beats) == 3, beats
        assert all(b["market_open"] is False for b in beats), beats
        assert all("market closed" in b["action"] for b in beats), beats
        assert all(b["traded"] is False for b in beats), beats
        print(f"closed market -> 3 cycles, 3 heartbeats, 0 trades: {beats[0]['action']!r}")

    # 2. One bad cycle logs and continues; the counter resets on the next good one.
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 2:
            raise TimeoutError("MCP call timed out")
        return 0.01

    with tempfile.TemporaryDirectory() as tmp:
        summary, beats = _run(tmp, run_once=flaky, manage_positions=_noop, max_cycles=4,
                              market_is_open=lambda: True)
        assert summary["cycles"] == 4, summary
        assert summary["stop_reason"] == "reached the 4-cycle limit", summary
        assert beats[1]["error"] == "TimeoutError: MCP call timed out", beats[1]
        assert beats[1]["consecutive_failures"] == 1, beats[1]
        # Reset, not accumulate: the cycle after the failure is clean.
        assert beats[2]["error"] is None and beats[2]["consecutive_failures"] == 0, beats[2]
        # Measured cost only, from the three cycles that actually completed.
        assert summary["session_spend_usd"] == 0.03, summary
        print("one bad cycle -> logged, loop continued, failure counter reset, "
              f"spend ${summary['session_spend_usd']} from completed cycles only")

    # 3. Three in a row trips the kill switch and stops.
    async def always_fails():
        raise ConnectionError("connection dropped")

    with tempfile.TemporaryDirectory() as tmp:
        summary, beats = _run(tmp, run_once=always_fails, manage_positions=_noop,
                              max_cycles=10, market_is_open=lambda: True)
        assert summary["cycles"] == MAX_CONSECUTIVE_FAILURES, summary
        assert "consecutive cycle failures" in summary["stop_reason"], summary
        assert os.path.exists(os.path.join(tmp, "KILL_SWITCH")), "kill switch was not tripped"
        with open(os.path.join(tmp, "KILL_SWITCH")) as f:
            assert "connection dropped" in f.read()
        print(f"{MAX_CONSECUTIVE_FAILURES} consecutive failures -> kill switch tripped, "
              f"loop stopped at cycle {summary['cycles']}")

    # 4. The spend cap bites on measured cost, and stops before spending past it.
    async def pricey():
        return 0.40

    with tempfile.TemporaryDirectory() as tmp:
        summary, beats = _run(tmp, run_once=pricey, manage_positions=_noop, max_cycles=10,
                              max_spend=1.00, market_is_open=lambda: True)
        assert summary["session_spend_usd"] == 1.20, summary
        assert "spend cap reached" in summary["stop_reason"], summary
        # Stops on the pass AFTER the cap is crossed, so the cap is measured, never predicted.
        assert summary["cycles"] == 4, summary
        print(f"spend cap $1.00 -> stopped at ${summary['session_spend_usd']} measured, "
              f"{summary['cycles']} cycles")

    # 5. The session-window rules fire on wall clock, from inside the loop. These are the
    #    real rules at real instants -- Thursday 3 Sep 2026 is the last trading day.
    managed = {"n": 0}

    async def count_manage():
        managed["n"] += 1
        return None

    async def must_not_run():
        raise AssertionError("a new cycle ran after entries were blocked")

    for label, when, expect in [
        ("Thu 14:00 ET (entries open)", datetime(2026, 9, 3, 14, 0, tzinfo=ET), "full"),
        ("Thu 15:15 ET (entries stopped)", datetime(2026, 9, 3, 15, 15, tzinfo=ET), "manage"),
        ("Thu 15:50 ET (must be flat)", datetime(2026, 9, 3, 15, 50, tzinfo=ET), "flatten"),
        ("Fri 10:00 ET (post-NFP)", datetime(2026, 9, 4, 10, 0, tzinfo=ET), "flatten"),
    ]:
        managed["n"] = 0
        real_now = sup.__dict__.get("_now_override")
        import agent.session_window as sw
        original = sw._now_et
        sw._now_et = lambda w=when: w
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary, beats = _run(
                    tmp, run_once=_noop if expect == "full" else must_not_run,
                    manage_positions=count_manage, max_cycles=2, market_is_open=lambda: True)
        finally:
            sw._now_et = original

        first = beats[0]
        if expect == "full":
            assert first["traded"] is True and first["entries_blocked"] is None, first
        elif expect == "manage":
            assert "no new entries" in first["action"], first
            assert first["entries_blocked"] and first["must_be_flat"] is None, first
            assert managed["n"] == 2, managed
        else:
            assert "flattened" in first["action"], first
            assert first["must_be_flat"], first
            # Flattens once, then keeps heartbeating rather than closing repeatedly.
            assert managed["n"] == 1, managed
            assert "already flat" in beats[1]["action"], beats[1]
        print(f"{label:32s} -> {first['action'][:64]}")

    print("supervisor: all checks pass")


if __name__ == "__main__":
    demo()
