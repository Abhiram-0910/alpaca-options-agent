"""The dashboard exporter must produce valid JSON before the data exists.

Antigravity builds its dashboard in a separate worktree against logs/dashboard.json. If the
exporter throws on an empty logs/, a missing backtest report or absent Alpaca credentials,
the other worktree has nothing to build against -- so those three are the cases under test,
alongside the count the slides currently get wrong (distinct pairs vs. total records).

    python test_dashboard_export.py
"""
import json
import os
import tempfile

import agent.config as config_mod
from agent import dashboard


def _export_with_logs_dir(tmp: str) -> dict:
    """CONFIG is a frozen dataclass, so redirect logs_dir by swapping the instance the
    module already imported rather than mutating it."""
    original = dashboard.CONFIG
    dashboard.CONFIG = config_mod.Config(logs_dir=tmp, alpaca_api_key="", alpaca_secret_key="")
    try:
        return dashboard.export_dashboard()
    finally:
        dashboard.CONFIG = original


def demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        snap = _export_with_logs_dir(tmp)
        out = os.path.join(tmp, "dashboard.json")
        assert os.path.exists(out), "exporter wrote nothing on an empty logs/"
        with open(out, encoding="utf-8") as f:
            reloaded = json.load(f)
        assert reloaded == json.loads(json.dumps(snap, default=str)), "file and return value disagree"
        for key in ("schema_version", "meta", "account", "validation", "gate_decisions",
                     "trades", "heartbeats", "adversarial", "fill_analysis"):
            assert key in snap, f"empty export is missing top-level key {key!r}"
        assert snap["validation"] == [], snap["validation"]
        assert snap["gate_decisions"] == [] and snap["trades"] == []
        # No heartbeats yet must read as "never seen", not as a zero-cycle success.
        assert snap["heartbeats"]["last_seen_at"] is None, snap["heartbeats"]
        assert snap["heartbeats"]["total_cycles"] == 0
        # Never run is not the same as run and clean.
        assert snap["adversarial"]["attacks_run"] is None, snap["adversarial"]
        assert snap["adversarial"]["results"] == []
        # No fills yet must read as not-yet-measurable, never as "no difference".
        assert snap["fill_analysis"]["mean_delta"] is None, snap["fill_analysis"]
        assert snap["fill_analysis"]["legs_filled"] == 0
        assert snap["meta"]["distinct_pairs_evaluated"] == 0
        assert snap["meta"]["total_validation_records"] == 0
        # No credentials must degrade to nulls with a stated reason, never to a fake balance.
        assert snap["account"]["equity"] is None, snap["account"]
        assert snap["account"]["error"], "a null account must say why it is null"
        # No read happened at all, so no surface can be claimed for one.
        assert snap["account"]["source"] is None, snap["account"]
        print("empty logs/ -> valid JSON, all sections present, account nulled with a reason")

    with tempfile.TemporaryDirectory() as tmp:
        # One pair with an extended retest and both half-period records: 1 distinct pair,
        # 4 records. Conflating the two is exactly the arithmetic error this count exists
        # to prevent.
        report = {"IWM": {"strategies": {"covered_call": {
            # The real IWM/covered_call shape: clears the primary bootstrap gate, then fails
            # the sub-period stability check, so enabled_for_paper stays false.
            "passed_backtest": True, "enabled_for_paper": False,
            "metrics": {"trades": 60, "win_rate": 0.44, "sharpe": 3.34},
            "mean_return_ci": [0.001, 0.009], "sharpe_ci": [0.4, 5.1], "reasons": [],
            "extended_retest": {
                "passed": False, "metrics": {"trades": 211, "sharpe": 3.337}, "reasons": [],
                "sub_period_stability": {
                    "passed": False, "reasons": ["first half fails on its own"],
                    "first_half": {"passed": False, "sharpe": 1.706, "mean_return_pct": 0.0059},
                    "second_half": {"passed": True, "sharpe": 3.045, "mean_return_pct": 0.01009},
                }}}}}}
        with open(os.path.join(tmp, "backtest_report.json"), "w") as f:
            json.dump(report, f)
        with open(os.path.join(tmp, "trade_log.jsonl"), "w") as f:
            f.write(json.dumps({"ts": "2026-09-02T09:00:00+00:00", "type": "tool_call",
                                "tool": "place_option_order", "approved": True,
                                "input": {"symbol": "IWM260904P00230000"}}) + "\n")
            # A cap rejection: the figure is a real number, never scraped out of the prose.
            f.write(json.dumps({"ts": "2026-09-02T09:10:00+00:00", "type": "tool_call",
                                "tool": "place_option_order", "agent": "openai",
                                "approved": False,
                                "reason": "Estimated capital at risk $75,500 exceeds the "
                                          "per-trade cap $8,000 (8% of equity).",
                                "estimated_capital_at_risk": 75500.0,
                                "input": {"symbol": "SPY260904P00755000"}}) + "\n")
            # A rejection thrown before capital was computed: null, not zero.
            f.write(json.dumps({"ts": "2026-09-02T09:16:42+00:00", "type": "demonstration_rejected",
                                "reason": "exceeds the per-trade cap",
                                "validation_status": "UNVALIDATED_DEMONSTRATION",
                                "payload": {"limit_price": "-0.81", "legs": [
                                    {"symbol": "SPY260904P00750000"}]}}) + "\n")
            # The demonstration approval. Logged even on a dry run, which is the default and
            # therefore the only record the one trade that matters would otherwise leave.
            f.write(json.dumps({"ts": "2026-09-02T09:20:00+00:00", "type": "demonstration_approved",
                                "symbol": "SPY", "dry_run": True,
                                "estimated_capital_at_risk": 423.0,
                                "capital_basis": "(5.00 width - 0.77 credit) x 100 x 1",
                                "validation_status": "UNVALIDATED_DEMONSTRATION",
                                "payload": {"limit_price": "-0.77", "legs": [
                                    {"symbol": "SPY260904P00751000"}]}}) + "\n")
            # Two heartbeats: one that declined and one that failed. This is what makes a
            # quiet stretch provably a decision rather than a switched-off agent.
            f.write(json.dumps({"ts": "2026-09-02T09:30:00+00:00", "type": "heartbeat",
                                "cycle": 1, "action": "declined: market closed",
                                "market_open": False, "traded": False,
                                "session_spend_usd": 0.0}) + "\n")
            f.write(json.dumps({"ts": "2026-09-02T09:45:00+00:00", "type": "heartbeat",
                                "cycle": 2, "action": "cycle failed (1/3 consecutive)",
                                "market_open": True, "traded": False,
                                "consecutive_failures": 1,
                                "error": "TimeoutError: MCP call timed out"}) + "\n")
            f.write(json.dumps({"ts": "2026-09-02T09:50:00+00:00", "type": "fill_analysis",
                                "order_id": "abc", "context": "demonstration",
                                "order_status": "filled", "legs_filled": 1, "legs": [
                                    {"symbol": "SPY260904P00751000", "indicative_mid": 0.45,
                                     "filled_price": 0.52, "delta": 0.07,
                                     "delta_sign": "above_mid"},
                                    {"symbol": "SPY260904P00756000", "indicative_mid": 1.15,
                                     "filled_price": None, "delta": None,
                                     "delta_sign": None}]}) + "\n")
            f.write("{ this line is truncated\n")

        snap = _export_with_logs_dir(tmp)

        scopes = [r["scope"] for r in snap["validation"]]
        assert scopes == ["primary", "extended", "sub_period_first_half",
                          "sub_period_second_half"], scopes
        assert snap["meta"]["distinct_pairs_evaluated"] == 1, snap["meta"]
        assert snap["meta"]["total_validation_records"] == 4, snap["meta"]
        # A pair that passes the primary gate but fails the retest has NOT cleared. Reporting
        # it as cleared would contradict the write-up's headline finding.
        assert snap["meta"]["pairs_passing_primary_gate"] == 1, snap["meta"]
        assert snap["meta"]["pairs_cleared"] == 0, snap["meta"]

        primary = snap["validation"][0]
        assert primary["mean_return_ci"] == {"lower": 0.001, "upper": 0.009}, primary
        # The engine never saves CI bounds for the half-period runs. Both keys must still be
        # present and null -- a missing key and a zero bound are both worse than an honest null.
        half = snap["validation"][2]
        assert half["sharpe_ci"] == {"lower": None, "upper": None}, half
        assert half["trades"] is None and half["sharpe"] == 1.706, half

        # The truncated line must not have taken the export down with it.
        gates = snap["gate_decisions"]
        assert len(gates) == 4, gates
        # Rejections first, newest first within each group.
        assert [g["approved"] for g in gates] == [False, False, True, True], gates

        by_cap = {g["estimated_capital_at_risk"] for g in gates}
        # The column that carries the evidence: a refused $75,500 against an approved $423.
        assert 75500.0 in by_cap and 423.0 in by_cap, gates

        approval = next(g for g in gates if g["agent"] == "demonstration" and g["approved"])
        assert approval["estimated_capital_at_risk"] == 423.0, approval
        assert approval["capital_basis"] == "(5.00 width - 0.77 credit) x 100 x 1", approval
        assert approval["validation_status"] == "UNVALIDATED_DEMONSTRATION", approval

        # A rejection thrown before capital was computed stays null. Null means "never
        # computed"; 0.0 would read as "this order risked nothing", which is a different and
        # false claim.
        early = next(g for g in gates if g["agent"] == "demonstration" and not g["approved"])
        assert early["estimated_capital_at_risk"] is None, early
        assert early["symbol"] == "SPY260904P00750000", early
        # ...and the figure is never recovered from the reason prose, which does contain it.
        big = next(g for g in gates if g["estimated_capital_at_risk"] == 75500.0)
        assert "$75,500" in big["reason"], big
        assert big["capital_basis"] is None, big

        hb = snap["heartbeats"]
        assert hb["total_cycles"] == 2 and hb["cycles_declined"] == 1, hb
        # A failed cycle is neither a trade nor a decline -- it is its own state.
        assert hb["cycles_failed"] == 1 and hb["cycles_traded"] == 0, hb
        assert hb["last_seen_at"] == "2026-09-02T09:45:00+00:00", hb

        fa = snap["fill_analysis"]
        # The mean is over filled legs only; an unfilled leg must not be averaged in as zero.
        assert fa["legs_measured"] == 2 and fa["legs_filled"] == 1, fa
        assert fa["mean_delta"] == 0.07 and fa["legs_above_mid"] == 1, fa

        print("populated logs/ -> 1 distinct pair vs 4 records, passed-primary-gate 1 but "
              "cleared 0, rejections first, capital column $75,500 refused vs $423 approved, "
              "truncated line skipped, uncomputed CIs null, "
              f"{hb['total_cycles']} heartbeats ({hb['cycles_failed']} failed)")

    print("dashboard export: all checks pass")


if __name__ == "__main__":
    demo()
