"""The unattended loop: what runs the agent when nobody is at the keyboard.

`main.py --loop` used to be a while-True around one cycle. It ran fine while someone was
watching it and had never survived a night alone, which is not the same thing as autonomous.
What was missing is all failure handling and all wall-clock judgement:

  * A cycle that raises must not end the run. An MCP timeout, a 429, a malformed LLM
    response and a dropped socket are all normal over a session, and each one used to be
    caught, printed and then... looped straight into the next cycle with no memory that it
    had happened. Failures are now counted, and MAX_CONSECUTIVE_FAILURES in a row trips the
    kill switch and stops. Consecutive, not cumulative: an isolated timeout every hour is a
    working agent on a flaky network; three in a row is a broken one that should not keep
    sending orders at something it cannot talk to.
  * The session-window rules (agent/session_window.py) have to fire on wall clock, from
    inside the loop, with nobody to notice that it is 15:00 ET. Entries stop, then the book
    is flattened, then the loop keeps heartbeating so the record shows it was alive and
    declining rather than dead.
  * Every pass writes a heartbeat, including the passes that do nothing. An account that
    did not trade for six hours and an agent that was switched off for six hours produce
    the same empty position list and completely different logs, and only one of them is
    evidence of a decision.

The spend cap is enforced on measured cost returned by the cycle, never on an estimate.

    python main.py --loop --interval 15
    python main.py --loop --interval 1 --max-cycles 3    # bounded, for verification
"""
import asyncio
import traceback
from datetime import datetime, timezone

from agent.config import CONFIG
from agent.alerts import alert
from agent.kill_switch import TradingKilled, activate as kill_switch_activate, is_active as kill_switch_active
from agent.session_window import entries_blocked, must_be_flat
from agent.trade_log import log_event

# Three in a row, not three in total. See the module docstring.
MAX_CONSECUTIVE_FAILURES = 3


def _dashboard_refresh() -> str:
    """Refresh logs/dashboard.json so a deployed dashboard tracks reality every cycle.

    Never allowed to break the loop: a dashboard that is one cycle stale is a cosmetic
    problem, and an agent that stopped trading because it could not write a JSON file is
    not."""
    try:
        from agent.dashboard import export_dashboard
        export_dashboard()
        return "ok"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


async def run_supervised(run_once, manage_positions, *, interval_minutes: int = 30,
                          max_spend: float = 0.0, max_cycles: int = None,
                          sleep_fn=asyncio.sleep, market_is_open=None) -> dict:
    """Run cycles unattended until stopped, capped, or tripped.

    `run_once` and `manage_positions` are passed in rather than imported so this module does
    not depend on main.py (which imports it), and so a verification run can drive the real
    loop over cheap callables.

    Returns a summary dict; also the return value the caller prints.
    """
    if market_is_open is None:
        from main import market_is_open as _market_is_open
        market_is_open = _market_is_open

    session_spend = 0.0
    consecutive_failures = 0
    cycle = 0
    flattened = False
    stop_reason = None

    log_event("supervisor_start", interval_minutes=interval_minutes, max_spend_usd=max_spend,
              max_cycles=max_cycles, max_consecutive_failures=MAX_CONSECUTIVE_FAILURES)
    print(f"Supervised loop starting — every {interval_minutes} min, "
          f"spend cap ${max_spend:.2f}" + (f", {max_cycles} cycles" if max_cycles else "") + ".")

    while True:
        if max_cycles is not None and cycle >= max_cycles:
            stop_reason = f"reached the {max_cycles}-cycle limit"
            break
        cycle += 1
        beat = {"cycle": cycle, "action": None, "market_open": None, "traded": False,
                "cycle_cost_usd": 0.0, "consecutive_failures": consecutive_failures,
                "error": None}

        # 1. Kill switch first: a killed agent does not even ask Alpaca what time it is.
        if kill_switch_active():
            beat["action"] = "stopped: kill switch active"
            _beat(beat, session_spend)
            stop_reason = "kill switch is active"
            break

        # 2. Spend cap, on measured cost accumulated from completed cycles.
        if max_spend > 0 and session_spend >= max_spend:
            beat["action"] = f"stopped: spend cap ${max_spend:.2f} reached"
            _beat(beat, session_spend)
            log_event("session_spend_cap_reached", session_spend_usd=round(session_spend, 5),
                      cap_usd=max_spend)
            alert("session_spend_cap_reached", session_spend_usd=round(session_spend, 5),
                  cap_usd=max_spend)
            stop_reason = f"spend cap reached (${session_spend:.4f} >= ${max_spend:.2f})"
            break

        try:
            open_now = market_is_open()
            beat["market_open"] = open_now
            flat_reason = must_be_flat()
            entry_reason = entries_blocked()
            beat["entries_blocked"] = entry_reason or None
            beat["must_be_flat"] = flat_reason or None

            if not open_now:
                # Closed is the normal overnight state, not an error. Heartbeat and wait.
                beat["action"] = "declined: market closed"
                if entry_reason:
                    beat["action"] += f"; entries also blocked ({entry_reason})"

            elif flat_reason:
                # Past the flat-by deadline. Flatten once, then keep heartbeating so the
                # record shows a live agent declining rather than a process that exited.
                if not flattened:
                    await manage_positions()
                    flattened = True
                    log_event("session_window_flatten", reason=flat_reason)
                    alert("session_window_flatten", reason=flat_reason)
                    beat["action"] = f"flattened: {flat_reason}"
                else:
                    beat["action"] = f"declined: already flat — {flat_reason}"

            elif entry_reason:
                # Entries stopped but the book may still be held: manage what is open,
                # open nothing new.
                await manage_positions()
                beat["action"] = f"managed only, no new entries: {entry_reason}"

            else:
                cost = await run_once()
                session_spend += cost or 0.0
                beat["cycle_cost_usd"] = round(cost or 0.0, 5)
                beat["traded"] = True
                beat["action"] = "ran a full cycle"

            consecutive_failures = 0

        except TradingKilled as exc:
            # Not a failure: the kill switch is a deliberate human decision. Stop cleanly.
            beat["action"] = f"stopped: {exc}"
            _beat(beat, session_spend)
            stop_reason = str(exc)
            break

        except Exception as exc:
            consecutive_failures += 1
            beat["error"] = f"{type(exc).__name__}: {exc}"
            beat["consecutive_failures"] = consecutive_failures
            beat["action"] = (f"cycle failed ({consecutive_failures}/"
                              f"{MAX_CONSECUTIVE_FAILURES} consecutive)")
            log_event("cycle_error", error=str(exc), consecutive_failures=consecutive_failures,
                      traceback=traceback.format_exc()[-2000:])
            alert("cycle_error", error=str(exc), consecutive_failures=consecutive_failures)
            print(f"  cycle {cycle} failed: {exc}")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                why = (f"{consecutive_failures} consecutive cycle failures, last: {exc}. "
                       f"Supervisor stopped itself rather than keep trading against a broken "
                       f"path. Run `python kill_switch.py off` after fixing it.")
                kill_switch_activate(why)
                alert("supervisor_tripped", reason=why)
                beat["action"] = "TRIPPED KILL SWITCH: " + why
                _beat(beat, session_spend)
                stop_reason = why
                break

        # Stamped after the pass, not before it: seeded from the previous cycle's value, a
        # heartbeat written after a recovery still reported the old count and the log read as
        # though the agent were failing when it was not.
        beat["consecutive_failures"] = consecutive_failures
        beat["dashboard"] = _dashboard_refresh()
        _beat(beat, session_spend)
        await sleep_fn(interval_minutes * 60)

    summary = {"cycles": cycle, "session_spend_usd": round(session_spend, 5),
               "stop_reason": stop_reason, "flattened": flattened,
               "consecutive_failures": consecutive_failures}
    log_event("supervisor_stop", **summary)
    print(f"\nSupervised loop stopped after {cycle} cycles — {stop_reason}. "
          f"Measured spend ${session_spend:.4f}.")
    return summary


def _beat(beat: dict, session_spend: float) -> None:
    """One heartbeat line, logged and printed, on every pass including the idle ones."""
    beat["session_spend_usd"] = round(session_spend, 5)
    beat["ts"] = datetime.now(timezone.utc).isoformat()
    log_event("heartbeat", **beat)
    flags = []
    if beat.get("market_open") is False:
        flags.append("closed")
    if beat.get("entries_blocked"):
        flags.append("entries blocked")
    if beat.get("must_be_flat"):
        flags.append("must be flat")
    print(f"  [cycle {beat['cycle']}] {beat['action']}"
          + (f" [{', '.join(flags)}]" if flags else "")
          + (f" — ${beat['session_spend_usd']:.4f} spent" if beat["session_spend_usd"] else ""))
