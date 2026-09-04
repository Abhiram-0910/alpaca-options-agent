# TODO.md — Alpaca Options Agent

Read at session start. Updated at session end.

---

## Now — blocking, do in this order

- [x] Demonstration order FILLED 15:58:51 UTC — 770P/765P, 0.70 credit, $430 max loss (3 Sep)
- [x] Position closed by the loop at 15:45 ET; account flat, +$8.90 realised (4 Sep)
- [ ] `fill_analysis`/`trades` miss the CLOSING legs — `order_manager.py` never calls
      `fill_analysis.record()`. The realised P&L is not in the export. ~5 lines if wanted.
- [ ] ~~Do not touch the position.~~ The loop flattens it at 15:45 ET / 01:15 IST. Verify only.
- [ ] Feed-vs-fill: write it up as **n=1, no net slippage**, not as a systematic bias. The
      1.15 s capture lag and the limit-price censoring both have to be stated.

- [ ] **ONE SESSION LEFT.** Thu 3 Sep is `LAST_TRADING_DAY`. Entries stop 15:00 ET Thu
      (00:30 IST Fri), flat by 15:45 ET Thu (01:15 IST Fri). Friday the loop refuses to
      trade. The demonstration order must be placed tonight or not at all.
- [ ] **Antigravity — dashboard does not render 6 of 12 sections.** Refreshing the data is
      necessary but NOT sufficient: `determinism` field names all differ
      (`total_replays`/`diverged_count`/`tool_changed_count` vs `replays`/`divergent`/
      `divergent_tool_changed`), `adversarial` and `fill_analysis` are read as arrays but
      exported as objects, and `counterfactual`/`arbiter`/`heartbeats` have no renderer.
      Deployed JSON is still schema_version 1 from 2 Sep 10:22 UTC.
- [ ] Tell Antigravity: export `schema_version` is now **2** — `reproducibility` renamed to
      `determinism`, `counterfactual` added.
- [ ] Run `python main.py --preflight` at 18:50 IST. Currently 11 green / 1 warn / 0 red.
- [x] Featherless arbiter live — first three-model cycle run; default model was gated,
      switched to `Qwen/Qwen2.5-7B-Instruct` (3 Sep)
- [ ] Antigravity: merge main again for the arbiter model-default fix — their copy still has
      the gated `meta-llama/Llama-3.1-8B-Instruct`, which 403s on this plan.
- [ ] ~~`FEATHERLESS_API_KEY` STILL NOT SET~~ — no such line in `.env`. Until it is, no
      three-model cycle can run and the council is two models. Endpoint verified reachable;
      only the credential is missing.
- [x] `FEATHERLESS_API_KEY` set and verified; the council is genuinely three models (3 Sep)
- [ ] Antigravity: 3 of 16 arbiter tests need updating — two assert a removed injection
      vulnerability, one asserts the crashing `log_event` call shape.
- [x] Arbiter wired as advisory third seat; 5 council attacks added, 18/18 blocked (3 Sep)
- [x] Adversarial self-test — 13 attacks, 2 gate holes found and fixed (3 Sep)
- [x] Fill-gap instrumentation — captures on tonight's fill, unanswered until then (3 Sep)
- [x] Replay determinism — 5 of 8 divergent at temp 0 / fixed seed / same fingerprint (3 Sep)
- [ ] **Write the determinism result into the submission.** n=40: 70% divergent (95% CI
      54.6–81.9%), 19 of 28 changing which tool was called, 0 across a fingerprint change.
      Now in ARCHITECTURE.md §Decisions and the export's `determinism` section.
- [ ] **Quote the counterfactual honestly if it is used**: +$1,326.64 over ONE day, marks not
      results, driven by a +0.44%/+0.23%/+1.18% up session. It prices the gate, not judges it.
- [x] Supervised unattended loop — `agent/supervisor.py`, verified 3 live cycles pre-open (3 Sep)
- [x] Alpaca CLI wired as the account/positions read path in the dashboard export (3 Sep)

- [ ] **Place the demonstration spread**, in-session, after operator review:
      `DEMONSTRATION_MODE=true python main.py --demonstrate --submit`. Dry run approved at
      $430 capital at risk — sell SPY 756P / buy 751P expiring **4 Sep**, 0.70 credit. Verify
      the fill, then confirm `main.py --manage-only` closes it before Thursday 15:45 ET.
- [ ] **Decide whether the demonstration trade is enough**, or whether a second one is
      wanted on Thursday. Default is one and only one — that is what the mode enforces.
- [x] LLM paths run on OpenAI — `--provider` defaults to openai, `multi_agent` is
      provider-aware (Proposer gpt-4o-mini, Critic gpt-4o), both cycles verified live (2 Sep)
- [ ] **Resolve the judging criteria.** lablab's page says $6,000 / four criteria; judge Tony
      Lee's own LinkedIn post and lablab's X post say $5,000 / "P&L and creativity or
      engagement". Ask in Discord `#ineedhelp`. Changes what the video and write-up optimise for.
- [x] Fresh paper account created: PA314K6MBKHZ / 68068c02-619a-4002-8211-7a691c37a614, $100,000, zero history (1 Sep)
- [x] `GET /v2/account` → options_trading_level 3 confirmed, no PATCH needed (1 Sep)
- [x] Multi-leg order path proven end to end — MCP `place_option_order` accepts `legs`;
      issue #97 is fixed in server 3.4.7, so the CLI fallback is not needed (1 Sep)
- [x] Per-trade capital deadlock fixed — multi-leg orders priced as structures,
      (width − credit) × 100 × qty, instead of notional per leg (1 Sep)
- [x] Moving-block bootstrap landed; zero-edge false-positive rate measured 10.8% → 2.5% (1 Sep)
- [x] Short-horizon profile added and run on SPY/QQQ/IWM — **nothing cleared** (1 Sep)

## Next

- [x] Short-horizon timing profile matching the judged window (`vertical_credit_spread_2d`) (1 Sep)
- [x] Economic-calendar gate: flat into NFP — `agent/session_window.py`, logs its reason (1 Sep)
- [x] `order_manager` reads `legs[].symbol` on an mleg parent (1 Sep)
- [ ] Write up the 21 FAILs as the headline finding, not an apology. Three liquid ETFs, seven
      structures, a bootstrap corrected from a measured 10.8% to 2.5% false-positive rate, and
      nothing cleared. This is the entry's strongest claim.
- [ ] Remove `iron_condor` and `covered_call` from `STRATEGY_NAMES` and both system prompts —
      still offered to the LLM and still structurally unable to execute.
- [ ] `reflection._find_entry_event` can't match an mleg entry (`inp["symbol"]` is absent), so
      every close gets flagged as a process failure. Scan `inp["legs"]` too.
- [ ] `_close_order_args` builds a single-leg close — closing one leg of a spread leaves a
      naked short between fills. Needs an mleg close with `buy_to_close`/`sell_to_close`.
- [ ] Make the portfolio-wide capital cap cumulative across cycles, not per-cycle.
- [x] Dashboard export contract — `agent/dashboard.py` writes `logs/dashboard.json`,
      shape documented in `docs/DASHBOARD-SCHEMA.md`, sample at `docs/dashboard.example.json`
      because `logs/` is gitignored. Antigravity builds against that (2 Sep)
- [x] `estimated_capital_at_risk` logged on gate rejections and approvals — `_reject()`
      carries the figure and basis at all four cap sites, both LLM tool_call log sites record
      them, and the demonstration path now logs `demonstration_approved` (it previously
      logged nothing when the gate approved, and dry run is the default). Verified $75,500
      refused vs $423 approved (2 Sep)
- [ ] Label indicative-feed data as such everywhere it surfaces to a user or a judge.
      Partly done: `meta.data_feed` in the dashboard export already names it.
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
