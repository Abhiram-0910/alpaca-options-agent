# CLAUDE.md — Alpaca Options Agent

Autonomous options-trading agent for Alpaca's paper environment, entered in the lablab.ai
× Alpaca "AI Trading Agents Hackathon". Judged on P&L, technology implementation,
creativity, and presentation. Submissions close **4 Sep 2026, 8:30 PM IST**.

**Stack:** Python 3.10+ · alpaca-py (data only) · Alpaca MCP server via `uvx` (all trading)
**Run:** `python main.py --once` · **Backtest:** `python run_backtest.py` · **Kill:** `python kill_switch.py on`

---

## Gotchas

- **Free tier has no OPRA data.** Options quotes come from Alpaca's *Indicative Pricing
  Feed* — a derived, deliberately randomised product. Historical endpoints error out on the
  most recent 15 minutes. Never write code or copy that implies we have real-time NBBO
  option quotes.
- **Greeks are null when the contract expires today (T=0) or has no bid or no ask.** Not a
  paywall — mathematical. Null-handle everywhere; never substitute zero.
- **Multi-leg orders through the MCP server may fail** (`alpacahq/alpaca-mcp-server`
  issue #97: `legs` arrives as a JSON string, not an array). Single-leg works. Direct REST
  POST to `paper-api.alpaca.markets/v2/orders` works. Test the exact path before building on it.
- **Working multi-leg payload shape:** drop the top-level `symbol`; each leg carries
  `ratio_qty` and `position_intent` (`sell_to_open` / `buy_to_open`).
- **Exercise, assignment and expiry are NOT pushed over WebSocket.** Poll the REST
  non-trade-activity endpoints (`OPEXC`, `OPASN`, `OPEXP`, `OPTRD`). In paper they surface
  the *following* day.
- **ITM by $0.01 auto-exercises at expiry.** If buying power is short, Alpaca liquidates the
  position itself up to an hour before expiry. Slightly-OTM can also be liquidated early.
- **Rate limits are 200/min trading and 200/min market data, flat.** Paying for Algo Trader
  Plus raises data only, not trading. REST-polling a watchlist exhausts this in seconds —
  use WebSocket streams.
- **Options are regular hours only.** `extended_hours` must be false or omitted;
  `time_in_force` is `day` or `gtc`.
- `load_dotenv(override=True)` is deliberate — a pre-existing OS env var shadowed the real
  key and sent calls to the wrong credential silently.

---

## Constraints

- Paper only. `assert_paper_trading()` guards every order path. There is no live path.
- Every order-placing call goes through `RiskGate.check()`. No exceptions, no bypass.
- The LLM never does arithmetic that reaches an order: Greeks, margin, breakevens, sizing,
  strike selection and DTE are computed in deterministic Python. The model emits
  `{direction, conviction, regime_label, rationale}` and nothing else.
- No new dependencies without asking.
- Never claim a P&L result is evidence of edge. See ARCHITECTURE.md §Variance.

---

## Files Claude should not touch

- `docs/strategy_graveyard.md` — append-only record written by `record_result()`.
  Never hand-edit; never delete a FAIL.
- `logs/` — generated.

---

## Session start

Read `SESSION-LOG.md` (what happened), `TODO.md` (what's next), `ARCHITECTURE.md` (how it's
built and what was rejected). Then state the plan before writing code.

`AGENTS.md` holds the cross-tool rules shared with Antigravity and OpenCode.

## Session end

Tests pass, `SESSION-LOG.md` and `TODO.md` updated with which agent did the work, and the
work is committed. Commit often — judges check whether history is spread across the event
window, and this repo's history is currently one day.
