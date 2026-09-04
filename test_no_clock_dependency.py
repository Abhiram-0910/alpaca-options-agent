"""No test in this suite may depend on what time it actually is.

This has now bitten three times, each in a different disguise:

  * agent/fill_analysis.py compared a hardcoded 14:00 fill against a live `captured_at`, so
    it passed all morning and started failing the moment the wall clock passed 14:00 UTC.
  * test_adversarial.py, test_risk_gate_mleg.py and test_supervisor.py assert on specific
    risk-gate rejection reasons, and once the session window closed on 3 Sep the
    session-window rule began pre-empting those reasons -- three failures at once, none of
    them caused by a code change.

Every instance surfaced hours after the code was written and looked like a regression. The
fourth would surface during a demo. So this runs the whole suite twice under two very
different fake clocks and fails if any file's result depends on which one it got.

`libfaketime` is not installed and is not worth a dependency, so the clock is moved the way
this codebase actually reads it: the session-window rule, which is what every failure so far
has routed through. A test that passes under a mid-session clock and fails under a
post-deadline one is, by definition, clock-dependent.

    python test_no_clock_dependency.py
"""
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Inside the trading window, and long past it. Every failure so far flips between these two.
CLOCKS = {
    "mid-session (Thu 3 Sep 11:00 ET)": datetime(2026, 9, 3, 11, 0, tzinfo=ET),
    "post-deadline (Mon 7 Sep 11:00 ET)": datetime(2026, 9, 7, 11, 0, tzinfo=ET),
}

SUITE = [
    "test_adversarial.py", "test_dashboard_export.py", "test_supervisor.py",
    "test_risk_gate_mleg.py", "test_block_bootstrap.py", "test_clip_tool_result.py",
]
MODULES = [
    "agent.replay", "agent.fill_analysis", "agent.alpaca_cli", "agent.demonstration",
]

# sitecustomize is imported automatically by CPython before anything else, so this pins the
# clock for the child process without editing a single test file.
SHIM = '''
import datetime as _d
from zoneinfo import ZoneInfo as _Z
_FAKE = _d.datetime.fromisoformat("{iso}")
import agent.session_window as _sw
_sw._now_et = lambda: _FAKE
'''


def _run_under(iso: str, target: str, is_module: bool) -> tuple:
    """Run one target with the session-window clock pinned to `iso`, in a fresh directory.

    The shim goes in its own temp dir per run, and bytecode caching is off. Both matter, and
    the first version of this had neither: the two shims differ only in a date string of
    identical length, so writing them to the same path inside the same filesystem-mtime
    second let CPython reuse the FIRST shim's cached .pyc for the second run. Every target
    then silently ran under one clock and the whole guard reported green while a genuinely
    unpinned test sat in the suite. Verified by unpinning one on purpose.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "sitecustomize.py"), "w") as f:
            f.write(SHIM.format(iso=iso))
        env = dict(os.environ)
        env["PYTHONPATH"] = tmp + os.pathsep + os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        cmd = [sys.executable] + (["-m", target] if is_module else [target])
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
        return p.returncode, (p.stdout + p.stderr)[-400:]


def demo() -> None:
    targets = [(t, False) for t in SUITE] + [(m, True) for m in MODULES]
    dependent = []

    if True:
        for target, is_module in targets:
            results = {}
            for label, when in CLOCKS.items():
                rc, tail = _run_under(when.isoformat(), target, is_module)
                results[label] = (rc, tail)
            codes = {label: rc for label, (rc, _) in results.items()}
            agreed = len(set(codes.values())) == 1
            all_passed = all(rc == 0 for rc in codes.values())
            mark = "OK  " if (agreed and all_passed) else "CLOCK-DEPENDENT"
            print(f"  [{mark}] {target}")
            if not agreed:
                dependent.append((target, codes, results))
                for label, (rc, tail) in results.items():
                    print(f"        {label}: exit {rc}")
            elif not all_passed:
                # Fails under BOTH clocks: broken, but not clock-dependent. Still a failure.
                dependent.append((target, codes, results))
                print(f"        fails under every clock (exit {list(codes.values())[0]}) — "
                      f"broken independently of time")
                print(f"        {list(results.values())[0][1][-200:]}")

    if dependent:
        raise AssertionError(
            f"{len(dependent)} target(s) depend on the real clock or are broken: "
            + ", ".join(t for t, _, _ in dependent))

    print(f"\n{len(targets)} targets run under {len(CLOCKS)} clocks — no result changed")
    print("no clock dependency: all checks pass")


if __name__ == "__main__":
    demo()
