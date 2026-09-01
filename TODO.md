# TODO.md — Alpaca Options Agent

Read at session start. Updated at session end.

---

## Now — blocking, do in this order

- [ ] **Resolve the judging criteria.** lablab's page says $6,000 / four criteria; judge Tony
      Lee's own LinkedIn post and lablab's X post say $5,000 / "P&L and creativity or
      engagement". Ask in Discord `#ineedhelp`. Changes what the video and write-up optimise for.
- [ ] **Create the fresh Alpaca paper account.** Required for judging; the current one has test
      trades and is ineligible. Fund at exactly $100,000. Record the account ID somewhere
      permanent — it goes on the submission form and P&L is judged from it.
- [ ] **`GET /v2/account`** → confirm `options_trading_level == 3`. PATCH via account
      configurations if not.
- [ ] **Place one real two-leg defined-risk spread** through the exact order path we intend to
      use. This is the live test of MCP issue #97. If it fails, fall back to direct REST POST
      and confirm before building anything on top.
- [ ] **Fix the per-trade capital deadlock.** `_estimate_capital_at_risk` returns strike × 100
      for a short put; the per-trade cap is 8% of equity = $8,000. No cash-secured put on any
      watchlist name can clear it. Either move to defined-risk spreads as the live structure
      (preferred) or size the cap against genuine defined risk rather than notional.
- [ ] **Replace the i.i.d. bootstrap with a moving-block bootstrap** in
      `agent/backtest/metrics.py`. `STEP_DAYS=7` against `HOLD_DAYS=21` is ~67% overlap;
      measured false-positive rate ~14% against a 2.5% nominal. Re-run the full validation
      afterwards. Until this lands, no graveyard PASS may be quoted as validated.

## Next

- [ ] Add a short-horizon timing profile whose positions open Tue/Wed and close by Thu, so the
      traded structure matches the 3.5-session judged window.
- [ ] Add an economic-calendar gate: flat or explicitly long-gamma into NFP (08:30 ET Fri 4 Sep).
- [ ] Remove `iron_condor` and `covered_call` from `STRATEGY_NAMES` until the naked-call gate
      and `place_stock_order` conflict is resolved — right now they are offered to the LLM and
      silently rejected every time.
- [ ] Make the portfolio-wide capital cap cumulative across cycles, not per-cycle.
- [ ] Check `cancel_order_by_id`'s result — still unchecked after the other order-result fixes.
- [ ] Label indicative-feed data as such everywhere it surfaces to the user or a judge.
- [ ] Add the conservative mark-to-market alongside Alpaca's simulated P&L.

## Later

- [ ] Per-strategy exit rules in the order manager instead of universal ones.
- [ ] Recompute ATR per window rather than reusing a stale value in the extended retest.
- [ ] Pass `profit_target_pct` from the backtest drivers — currently implemented and never used.
- [ ] Collapse the ~10 duplicated response-envelope unwraps into `mcp_parsers.py`.
- [ ] Remove dead code: `strategy_drift_report`, `price_iron_condor_real_quotes`,
      `ContractQuote`, `STRATEGY_FUNCS`, `StrategyRegistry.all()`/`.enabled_for_live()`.

## Submission — none of this is started, all of it is required

- [ ] One-page write-up: AI logic, risk gates, Alpaca infrastructure implementation.
- [ ] Video: MP4 **uploaded file, not a link**, under 5 minutes, under 300 MB. Human voice,
      own face — AI voiceover is reported as penalised.
- [ ] Slides as PDF. Cover image PNG/JPG 16:9.
- [ ] Public GitHub repo with a README that runs cold.
- [ ] Deployed demo URL a judge can interact with. Local-only scores as if it doesn't work.
- [ ] Alpaca paper account ID on the form. Missing it means no P&L score at all.
- [ ] Up to 5 social posts tagging `@lablabai` and `@AlpacaHQ`.

## Cut

- Iron condor as a live structure — cut until the stock-leg/naked-call conflict is resolved;
  it cannot currently execute.
- Fine-tuning on trade outcomes — cut. A 70%-win-rate strategy loses 30% of correctly executed
  trades; a naive avoid-what-lost loop would spend its budget unlearning real edge.
- Chasing the P&L leaderboard with size — cut. Expected winning score is ~3σ of a
  zero-edge distribution; matching it means a ~40% chance of a visible blow-up.

## Done

- [x] Research round: 22 reports across 4 prompts, merged into `RESEARCH.md` — 1 Sep
- [x] Audit of the existing codebase at commit `7095748` — 1 Sep
