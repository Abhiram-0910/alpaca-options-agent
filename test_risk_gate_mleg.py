"""What the risk gate does with a real multi-leg payload.

Three things worth being able to re-check on demand, because all three are claims the
write-up makes:

  1. The per-leg capital model is what deadlocked the account -- a short SPY put priced at
     notional cannot clear an 8%-of-equity cap at any strike a liquid ETF trades at.
  2. Pricing the same spread as a structure clears it, because the structure's worst case
     really is a few hundred dollars.
  3. Demonstration mode is strictly tighter than the normal path, not looser.

    python test_risk_gate_mleg.py
"""
from datetime import date, timedelta

from agent.config import CONFIG
from agent.risk.gates import RiskGate, mleg_capital_at_risk, _estimate_capital_at_risk

EQUITY = 100_000.0


def _occ(strike: float, days: int = 2, option_type: str = "P") -> str:
    exp = date.today() + timedelta(days=days)
    return f"SPY{exp:%y%m%d}{option_type}{int(round(strike * 1000)):08d}"


def _spread(short_strike=755.0, long_strike=750.0, days=2) -> list:
    return [
        {"symbol": _occ(long_strike, days), "side": "buy", "ratio_qty": "1",
         "position_intent": "buy_to_open"},
        {"symbol": _occ(short_strike, days), "side": "sell", "ratio_qty": "1",
         "position_intent": "sell_to_open"},
    ]


def _gate() -> RiskGate:
    g = RiskGate()
    g.refresh({"equity": EQUITY, "last_equity": EQUITY}, [])
    return g


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
    cap = CONFIG.max_allocation_pct_per_trade * EQUITY

    # 1. The deadlock, stated as arithmetic rather than as a complaint.
    notional = _estimate_capital_at_risk("put", "sell", 755.0, 1)
    assert notional == 75_500.0, notional
    assert notional > cap, "the per-leg model is supposed to blow through the per-trade cap"
    break_even_strike = cap / 100
    assert break_even_strike == 80.0, break_even_strike
    print(f"per-leg model charges a 755 short put ${notional:,.0f} against a ${cap:,.0f} cap")
    print(f"  -> clears only below a ${break_even_strike:.0f} strike, which no liquid ETF trades at")

    # 2. The same trade, priced as the structure it actually is.
    risk, detail = mleg_capital_at_risk(_spread(), qty=1, limit_price="-1.20")
    assert risk == (5.0 - 1.20) * 100, (risk, detail)
    assert risk < cap
    print(f"structure model charges the same spread ${risk:,.0f}  [{detail}]")

    # Undefined risk must still be refused, whatever it is called.
    naked, why = mleg_capital_at_risk(
        [{"symbol": _occ(755.0), "side": "sell", "ratio_qty": "1"},
         {"symbol": _occ(760.0, option_type="C"), "side": "sell", "ratio_qty": "1"}],
        qty=1, limit_price="-2.00")
    assert naked is None and "undefined" in why, why

    # An inverted "spread" whose long leg is nearer the money is not cover.
    bad, why = mleg_capital_at_risk(_spread(short_strike=750.0, long_strike=755.0),
                                    qty=1, limit_price="-1.20")
    assert bad is None, why

    # A credit at or above the width is not a real quote.
    impossible, why = mleg_capital_at_risk(_spread(), qty=1, limit_price="-6.00")
    assert impossible is None and "width" in why, why

    # 3. Gate end to end. Nothing has cleared validation, so the normal path refuses.
    assert not CONFIG.demonstration_mode, "demonstration mode must be off by default"
    decision = _gate().check("place_option_order",
                             {"qty": "1", "limit_price": "-1.20", "legs": _spread()})
    assert not decision["approved"], decision
    assert "validation gate" in decision["reason"], decision["reason"]
    print(f"normal path, nothing validated -> rejected: {decision['reason'][:60]}...")

    # With demonstration mode armed, the same order passes and is stamped.
    object.__setattr__(CONFIG, "demonstration_mode", True)
    try:
        decision = _gate().check("place_option_order",
                                 {"qty": "1", "limit_price": "-1.20", "legs": _spread()})
        assert decision["approved"], decision
        assert decision["validation_status"] == "UNVALIDATED_DEMONSTRATION", decision
        assert decision["estimated_capital_at_risk"] == 380.0, decision
        print(f"demonstration mode -> approved, ${decision['estimated_capital_at_risk']:.0f} at risk, "
              f"stamped {decision['validation_status']}")

        # ...and every tighter constraint still bites.
        for name, payload in [
            ("2 contracts", {"qty": "2", "limit_price": "-1.20", "legs": _spread()}),
            ("single leg", {"qty": "1", "limit_price": "-1.20", "legs": _spread()[:1]}),
            ("wrong symbol", {"qty": "1", "limit_price": "-1.20",
                              "legs": [{**l, "symbol": l["symbol"].replace("SPY", "QQQ")}
                                       for l in _spread()]}),
            ("out of DTE window", {"qty": "1", "limit_price": "-1.20", "legs": _spread(days=30)}),
            ("width over the 0.5% cap", {"qty": "1", "limit_price": "-1.20",
                                          "legs": _spread(short_strike=755.0, long_strike=735.0)}),
        ]:
            d = _gate().check("place_option_order", payload)
            assert not d["approved"], f"{name} should have been refused: {d}"
            # The capital figure has to survive a rejection, not just an approval -- it is the
            # evidence that the gate bound real exposure, and the dashboard reads it as a
            # number rather than scraping it out of the reason prose. Present but null on a
            # refusal thrown before capital was computed; a real number on a cap breach.
            assert "estimated_capital_at_risk" in d, f"{name} rejection dropped the field: {d}"
            if "capital at risk" in (d["reason"] or ""):
                assert d["estimated_capital_at_risk"] is not None, \
                    f"{name} breached the cap but logged no figure: {d}"
                assert d["capital_basis"], f"{name} breached the cap but logged no basis: {d}"
            print(f"  refused {name}: {d['reason'][:70]}")
            print(f"      capital_at_risk={d['estimated_capital_at_risk']}")
    finally:
        object.__setattr__(CONFIG, "demonstration_mode", False)

    print("risk gate mleg: all checks pass")


if __name__ == "__main__":
    demo()
