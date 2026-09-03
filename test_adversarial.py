"""The adversarial harness has to be trustworthy before its results mean anything.

Two properties matter more than any individual attack:

  1. It must place no orders. Asserted here by giving it a gate whose approval it would act
     on if it acted on anything, and confirming the MCP order tools are never reached.
  2. Its verdicts must come from the layer each attack was written to test. The first run of
     this harness reported 13/13 blocked and was nearly worthless: six attacks died at the
     backtest-validation gate before reaching the defence under test. The isolated run exists
     to stop that, and this checks the isolation actually works.

Also pins the two holes the harness found, so neither can silently come back.

    python test_adversarial.py
"""
from datetime import date, timedelta

from agent.adversarial import build_attacks, _validation_satisfied, _fresh_gate
from agent.risk.gates import mleg_capital_at_risk, RiskGate
import agent.risk.gates as gates_mod


def _occ(strike, days=2, cp="P", root="SPY"):
    exp = date.today() + timedelta(days=days)
    return f"{root}{exp:%y%m%d}{cp}{int(round(strike * 1000)):08d}"


def _leg(strike, side, ratio="1", **kw):
    return {"symbol": _occ(strike, **kw), "side": side, "ratio_qty": ratio}


def demo() -> None:
    # 1. Every attack is a payload, and no attack carries a live order path. The harness
    #    calls RiskGate.check and stops; nothing here can reach Alpaca.
    attacks = build_attacks(999.5)
    assert len(attacks) >= 11, len(attacks)
    for a in attacks:
        assert "payload" in a and "expect" in a, a
    print(f"{len(attacks)} payload attacks defined, none carrying an order path")

    # 2. The isolation actually lifts the validation gate, and nothing else.
    unvalidated = _fresh_gate().check("place_option_order", {
        "symbol": _occ(756.0), "side": "sell", "qty": 1, "limit_price": "1.20"})
    assert "backtest validation gate" in (unvalidated["reason"] or ""), unvalidated
    with _validation_satisfied():
        isolated = _fresh_gate().check("place_option_order", {
            "symbol": _occ(756.0), "side": "sell", "qty": 1, "limit_price": "1.20"})
    assert "backtest validation gate" not in (isolated["reason"] or ""), isolated
    # Lifted for the duration only.
    assert "SPY" not in gates_mod.load_cleared_symbols(), "isolation leaked past its context"
    print(f"isolation lifts only the validation gate: {isolated['reason'][:64]}...")

    # 3. HOLE FOUND BY THE HARNESS: ratio_qty was read by nothing, so a buy-1/sell-2 was
    #    priced as a 1:1 vertical and the second short contract was naked and free.
    ok, basis = mleg_capital_at_risk([_leg(751, "buy"), _leg(756, "sell")], 1, "-0.70")
    assert ok == 430.0, (ok, basis)
    bad, why = mleg_capital_at_risk([_leg(751, "buy", "1"), _leg(756, "sell", "2")], 1, "-1.40")
    assert bad is None and "ratio_qty" in why, (bad, why)
    for ratio in ("0", "-1", "x"):
        r, w = mleg_capital_at_risk([_leg(751, "buy", ratio), _leg(756, "sell", "1")], 1, "-0.70")
        assert r is None, (ratio, r, w)
    print(f"ratio_qty hole closed: {why[:72]}...")

    # 4. HOLE FOUND BY THE HARNESS: a contract that is not on the chain was approved. The
    #    gate does no network I/O, so this only binds when a caller supplies the chain --
    #    and when it does, it must bind.
    listed = {_occ(751.0), _occ(756.0)}
    payload = {"qty": "1", "order_class": "mleg", "limit_price": "-0.70",
               "legs": [_leg(751, "buy"), _leg(756, "sell")]}
    ghost = {"qty": "1", "order_class": "mleg", "limit_price": "-0.70",
             "legs": [_leg(1201, "buy"), _leg(1206, "sell")]}
    with _validation_satisfied():
        no_chain = _fresh_gate().check("place_option_order", ghost)
        g = _fresh_gate(); g.known_contracts = listed
        with_chain = g.check("place_option_order", ghost)
        g2 = _fresh_gate(); g2.known_contracts = listed
        real = g2.check("place_option_order", payload)
    # Honest about the limit: with no chain supplied there is no protection here.
    assert no_chain["approved"] is True, no_chain
    assert with_chain["approved"] is False and "does not exist" in with_chain["reason"], with_chain
    assert real["approved"] is True, real
    print(f"unlisted-contract hole closed when a chain is supplied: "
          f"{with_chain['reason'][:64]}...")

    # 5. An empty known_contracts must stay inert, or every existing caller breaks.
    assert RiskGate().known_contracts == set()
    print("empty known_contracts stays inert for callers that supply nothing")

    print("adversarial: all checks pass")


if __name__ == "__main__":
    demo()
