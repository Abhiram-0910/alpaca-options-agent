"""Run the full statistical options-strategy backtest across the watchlist:
simulate all five strategies per symbol, validate each against the
bootstrap-CI gate, retest anything that passes on extended history, and
save the ranking + pass/fail report the live agent reads for context.

Usage:
    python run_backtest.py [SYMBOL ...]
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.backtest.engine import run_backtest, save_report

if __name__ == "__main__":
    symbols = sys.argv[1:] or None
    report = run_backtest(symbols)
    save_report(report)
    for sym, data in report.items():
        if "error" in data:
            print(f"{sym}: {data['error']}")
            continue
        print(f"\n{sym} -- cleared for paper: {data['cleared_for_paper'] or 'none'}")
        for name, s in data["strategies"].items():
            m = s["metrics"]
            status = "PASS" if s["enabled_for_paper"] else "FAIL"
            print(f"  [{status}] {name:24s} trades={s['trades']:3d}  win_rate={m.get('win_rate', 0):.0%}  "
                  f"sharpe={m.get('sharpe', 0):6.2f}  total_pnl=${m.get('total_pnl_dollars', 0):.0f}")
            if s["reasons"]:
                print(f"           reasons: {'; '.join(s['reasons'])}")
    print("\nSaved to logs/backtest_report.json; full pass/fail write-up in docs/strategy_graveyard.md")
