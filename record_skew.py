"""Records one real IV-skew observation per watchlist symbol and appends it to
logs/skew_history.jsonl. Never places an order — pure observation, safe to
run as often as you like (Alpaca market data is free; this makes no
Anthropic API call). Run this periodically (daily is plenty) to build up the
trailing history a skew mean-reversion signal needs before it means anything.

Usage:
    python record_skew.py [SYMBOL ...]
"""
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.skew_strategy import record_all_observations, MIN_OBSERVATIONS

if __name__ == "__main__":
    symbols = sys.argv[1:] or None
    results = asyncio.run(record_all_observations(symbols))
    for r in results:
        status = r["status"]
        if status == "no_data":
            print(f"{r['symbol']:6s}  no data (chain/price unavailable right now)")
        elif status == "insufficient_history":
            print(f"{r['symbol']:6s}  recorded  ({r['observations']}/{MIN_OBSERVATIONS} observations so far — "
                  f"no signal until {MIN_OBSERVATIONS} is reached)")
        elif status == "no_signal":
            print(f"{r['symbol']:6s}  recorded  skew={r['current_skew']:.4f}  mean={r['mean_skew']:.4f}  "
                  f"z={r['z_score']:+.2f}  (within +/-{1.5} sigma, no signal)")
        else:
            print(f"{r['symbol']:6s}  *** SIGNAL: skew {r['direction']} ***  z={r['z_score']:+.2f}  "
                  f"skew={r['current_skew']:.4f}  mean={r['mean_skew']:.4f}  "
                  f"({r['observations']} observations — informational only, not an order)")
