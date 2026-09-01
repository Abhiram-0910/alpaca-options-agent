"""The dated trading-window decision for this specific competition run.

Nonfarm payrolls prints 08:30 ET on Friday 4 September 2026. The submission deadline is
11:00 ET the same morning, so the judged account is marked in a post-NFP session with a
three-day weekend behind it. A short-premium position carried into Thursday's close faces
a gap through an 08:30 macro print that we cannot manage, cannot hedge, and cannot exit
before the account is marked -- and Friday's 90 minutes are needed for submission, not for
trading out of a position we chose to keep.

So: the last real trading decision is Thursday, entries stop before Thursday's close, and
the book is flat by Thursday 15:45 ET.

These are hardcoded dates on purpose. This is one dated judgement about one macro release
in one four-day window, not a calendar framework -- a general economic-calendar gate is
strictly more code and strictly more ways to be wrong for a system with three sessions left
to live.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

LAST_TRADING_DAY = datetime(2026, 9, 3, tzinfo=ET).date()  # Thursday 3 Sep 2026
NO_NEW_ENTRIES_AFTER = time(15, 0)                          # 15:00 ET on the last trading day
FLAT_BY = time(15, 45)                                      # 15:45 ET on the last trading day

REASON = ("flat before 08:30 ET nonfarm payrolls, which we cannot manage and cannot exit "
          "before the judged mark")


def _now_et() -> datetime:
    return datetime.now(ET)


def entries_blocked(now: datetime = None) -> str:
    """Reason new entries are refused right now, or "" if they're allowed.

    Returned rather than raised so the caller logs a decision instead of an error: an empty
    book and a deliberate refusal to trade look identical in an account statement and
    completely different in a trade log, and the deliberate one is the whole point.
    """
    now = now or _now_et()
    today = now.date()
    if today > LAST_TRADING_DAY:
        return f"past the last trading day ({LAST_TRADING_DAY}) - {REASON}"
    if today == LAST_TRADING_DAY and now.time() >= NO_NEW_ENTRIES_AFTER:
        return (f"after {NO_NEW_ENTRIES_AFTER:%H:%M} ET on the last trading day "
                f"({LAST_TRADING_DAY}) - {REASON}")
    return ""


def must_be_flat(now: datetime = None) -> str:
    """Reason every open position should be closed now, or "" if positions may be held."""
    now = now or _now_et()
    today = now.date()
    if today > LAST_TRADING_DAY:
        return f"past the last trading day ({LAST_TRADING_DAY}) - {REASON}"
    if today == LAST_TRADING_DAY and now.time() >= FLAT_BY:
        return f"{FLAT_BY:%H:%M} ET on the last trading day ({LAST_TRADING_DAY}) - {REASON}"
    return ""


def demo() -> None:
    """Self-check: the three states this rule has to get right."""
    wed = datetime(2026, 9, 2, 11, 0, tzinfo=ET)
    thu_early = datetime(2026, 9, 3, 11, 0, tzinfo=ET)
    thu_late = datetime(2026, 9, 3, 15, 30, tzinfo=ET)
    thu_flat = datetime(2026, 9, 3, 15, 50, tzinfo=ET)
    fri = datetime(2026, 9, 4, 9, 45, tzinfo=ET)

    assert not entries_blocked(wed), "Wednesday midday must allow entries"
    assert not must_be_flat(wed)
    assert not entries_blocked(thu_early), "Thursday morning must allow entries"
    assert entries_blocked(thu_late), "entries must stop at 15:00 ET Thursday"
    assert not must_be_flat(thu_late), "15:30 Thursday is past entries but not yet flat"
    assert must_be_flat(thu_flat), "must be flat by 15:45 ET Thursday"
    assert entries_blocked(fri) and must_be_flat(fri), "Friday is post-NFP: no trading at all"
    print("session_window: all checks pass")


if __name__ == "__main__":
    demo()
