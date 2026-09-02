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
        for key in ("schema_version", "meta", "account", "validation", "gate_decisions", "trades"):
            assert key in snap, f"empty export is missing top-level key {key!r}"
        assert snap["validation"] == [], snap["validation"]
        assert snap["gate_decisions"] == [] and snap["trades"] == []
        assert snap["meta"]["distinct_pairs_evaluated"] == 0
        assert snap["meta"]["total_validation_records"] == 0
        # No credentials must degrade to nulls with a stated reason, never to a fake balance.
        assert snap["account"]["equity"] is None, snap["account"]
        assert snap["account"]["error"], "a null account must say why it is null"
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
            f.write(json.dumps({"ts": "2026-09-02T09:16:42+00:00", "type": "demonstration_rejected",
                                "reason": "exceeds the per-trade cap",
                                "validation_status": "UNVALIDATED_DEMONSTRATION",
                                "payload": {"limit_price": "-0.81", "legs": [
                                    {"symbol": "SPY260904P00750000"}]}}) + "\n")
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
        assert len(snap["gate_decisions"]) == 2, snap["gate_decisions"]
        # Rejections first.
        assert snap["gate_decisions"][0]["approved"] is False
        assert snap["gate_decisions"][0]["symbol"] == "SPY260904P00750000"
        # Never recorded at the tool_call log site, so it must be null, not 0.
        assert snap["gate_decisions"][1]["estimated_capital_at_risk"] is None

        print("populated logs/ -> 1 distinct pair vs 4 records, passed-primary-gate 1 but "
              "cleared 0, rejections first, "
              "truncated line skipped, uncomputed CIs null")

    print("dashboard export: all checks pass")


if __name__ == "__main__":
    demo()
