# SESSION-LOG.md

Updated at the end of every session, read at the start. Newest entry at the top.

---

## Current state

**Updated:** 1 Sep 2026, 21:15 IST
**Branch:** main
**Agents active:** Claude Code (code), second agent (submission materials) — not yet started
**Status:** Repo runs again, order path proven, capital deadlock fixed. **The validation gate
has cleared nothing** — SPY, QQQ and IWM against seven structures, 21 FAILs. That is the
headline finding, not a setback. Demonstration mode is built and dry-run-approved but has
placed nothing.
**Next:** submit the demonstration spread in-session Wednesday (`main.py --demonstrate
--submit`, requires operator review first), then the submission materials, which remain
entirely undone.

## Sessions

### 1 Sep 2026 — fix the order path, retarget the horizon, run the gate — *Claude Code*

**Done**
- Environment: nothing in the repo could import (`alpaca-py` and `anthropic` missing, stdlib
  venv broken on Python 3.14.4). Rebuilt on `uv`; `alpaca-mcp-server` pre-installed so the
  first spawn doesn't download mid-cycle.
- `probe_mleg.py`: placed and cancelled a real 2-leg SPY spread through the MCP server.
- Retargeted 7-45 DTE → 1-4 DTE, and everything coupled to it.
- `agent/session_window.py`: the dated NFP rule, with its reason logged.
- Circular moving-block bootstrap in `metrics.py`.
- Structure-level capital-at-risk for multi-leg orders in `RiskGate`.
- `agent/demonstration.py` + `main.py --demonstrate`.

**Decided**
- **Order path is MCP multi-leg. The Alpaca CLI is not needed.** Issue #97 is fixed in
  server 3.4.7: `legs` is typed as an array of objects and a real spread was accepted and
  cancelled. Rejected installing the CLI as a fallback — no `go` toolchain on this box, and
  it is Alpha Preview with unverified mleg-options support.
- **Demonstration mode, decided explicitly rather than by running out of time.** With zero
  strategies cleared, the options were: stand down and ship the evidence; one bounded
  unvalidated trade; or re-examine the gate's criteria. Chose the second, built as a named
  mode with constraints strictly tighter than the normal path — never
  `require_backtest_validation=False`. Rejected loosening the gate after seeing everything
  fail: that is the exact post-hoc move the gate exists to prevent. Rationale is in
  ARCHITECTURE.md §Decisions because it is the decision a judge will probe hardest.

**Hit**
- **The gate refused every candidate.** SPY, QQQ, IWM × 7 structures. `vertical_credit_spread_2d`
  came closest on all three — 76-81% win rate, Sharpe 1.67-1.81, positive simulated P&L — and
  was refused because its Sharpe CI lower bound stays negative (−0.32 / −0.17 / −0.26). Correct
  behaviour on a negatively skewed payoff. Not a block-bootstrap artefact: that profile's
  block length is 1 because its 7-day entry step exceeds its 2-day hold, so it failed on a
  plain i.i.d. bootstrap.
- Measured the bootstrap bias rather than asserting it: the i.i.d. gate passed **10.8%** of
  zero-edge random walks against a 2.5% nominal; the block bootstrap passes **2.5%**.
- The capital deadlock was worse than recorded. `_estimate_capital_at_risk` charges a short
  put strike × 100, so it clears an $8,000 cap only below an $80 strike — no liquid ETF
  qualifies. It wasn't GOOGL-specific: no short-premium leg on any liquid symbol could pass.
- `list_tools_anthropic_format` raised `AttributeError` on the installed MCP SDK
  (`inputSchema` → `input_schema`), so **both LLM paths were dead** on their first tool call.
  Only the deterministic path, which never calls it, still worked.
- HANDOFF.md is stale in three places: `covered_call`'s stock leg, `parse_order_error`
  wiring, and `cancel_order_by_id` checking are all already fixed on disk.
- An mleg parent order returns `symbol` and `side` as empty strings, which broke
  `order_manager`'s close-order dedupe. Fixed to read `legs[].symbol`.

**Incomplete**
- No order placed. The demonstration payload is built and gate-approved, awaiting operator
  review and an in-session run.
- `ANTHROPIC_API_KEY` is empty in `.env`, so no LLM-driven cycle can run at all.
- Submission materials: still entirely undone.

### 1 Sep 2026 — audit of the existing build — *Claude (chat)*

**Done**
- Read all 22 external research reports; merged into `RESEARCH.md`.
- Cloned and audited `Sairishwanth89/alpaca_software` at `7095748`.

**Decided**
- Keep the existing codebase and fix forward. Rejected a rebuild: the validation gate, risk
  gate, kill switch and MCP path are the slowest things to build and the strongest scoring
  assets, and there is not time to reproduce them.
- The live track must trade on a horizon that closes inside the judged window. The 21-day
  backtest track becomes the research/methodology evidence, not the traded path.
- Drop `iron_condor` and `covered_call` from the presented strategy universe until tradeable.

**Hit**
- The single validated strategy (GOOGL `cash_secured_put`) requires ≥ strike × 100 in capital
  at risk, and the per-trade cap is 8% of $100k = $8,000. It is rejected by the project's own
  RiskGate. This explains the near-absence of live trading activity.
- The overlapping-window bootstrap bias is documented in HANDOFF.md but **not fixed on disk**.
  Every PASS in the graveyard is at roughly 5.6× the nominal false-positive rate.
- All five commits are dated 2026-09-01 for an event that started 28 Aug.

**Incomplete**
- Nothing merged. Fresh paper account not yet created.
