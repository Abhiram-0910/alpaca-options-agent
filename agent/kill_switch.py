"""Manual kill switch: a human lever to stop all trading immediately, independent
of every other risk gate. A marker file's mere existence blocks every new order,
everywhere in this project — checked both at the top of each agent's run_cycle()
(so a killed session doesn't even bother researching, saving Anthropic spend too)
and inside RiskGate.check() itself (so it's enforced at the same final choke
point as every other gate, not just at the entry point).
"""
import os

from agent.config import CONFIG

KILL_SWITCH_PATH = os.path.join(CONFIG.logs_dir, "KILL_SWITCH")


class TradingKilled(RuntimeError):
    pass


def is_active() -> bool:
    return os.path.exists(KILL_SWITCH_PATH)


def reason() -> str:
    if not is_active():
        return ""
    try:
        with open(KILL_SWITCH_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def activate(why: str = "") -> None:
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    with open(KILL_SWITCH_PATH, "w", encoding="utf-8") as f:
        f.write(why or "activated (no reason given)")


def deactivate() -> None:
    if os.path.exists(KILL_SWITCH_PATH):
        os.remove(KILL_SWITCH_PATH)


def assert_not_killed() -> None:
    if is_active():
        raise TradingKilled(f"Kill switch is active: {reason()}. Run "
                             f"`python kill_switch.py off` to resume.")
