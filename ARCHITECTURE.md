# ARCHITECTURE.md — Alpaca Options Agent

## Stack

| Layer | Choice | Why |
|---|---|---|
| Reasoning | Anthropic + OpenAI SDKs, constrained output schema | Model proposes; it never computes or executes |
| Execution | Alpaca MCP server via `uvx` | Satisfies the hackathon's MCP/CLI requirement; sponsor's newest surface |
| Data (live) | Alpaca MCP market-data toolset | Free tier = Indicative Pricing Feed, not OPRA |
| Data (historical) | alpaca-py `StockHistoricalDataClient` | Underlying closes only; no historical option chains exist for us |
| Validation | Custom bootstrap gate + graveyard | The differentiator on Technology Implementation |
| Risk | `agent/risk/gates.py`, deterministic Python | Every order passes through it |
| Deploy | Local + scheduled cycles | No hosting dependency at demo time |

## Structure

```
agent/backtest/    validation gate, simulator, engine, stress tests, graveyard writer
agent/strategies/  leg builders + lifecycle registry
agent/risk/        RiskGate — the enforcement point
agent/mcp/         MCP client (spawns uvx alpaca-mcp-server)
agent/*_agent.py   single-agent, proposer/critic, deterministic execution paths
```

## Data flow

Backtest engine pulls split-adjusted underlying closes → derives ATR risk parameters →
simulates each strategy day-by-day with Black-Scholes marks → statistical gate →
promotion/demotion → graveyard. Only cleared symbol/strategy pairs are visible to the live
agent. Live: order manager housekeeping → LLM proposes within a constrained schema →
deterministic policy maps it to a concrete trade → RiskGate → MCP order → reflection log.

## Decisions

- **LLM proposes, deterministic code disposes** — because no credible published result shows
  an LLM trading agent generating reproducible cost-adjusted alpha. FINSABER found no
  significant alpha over 20 years; the Alpha Illusion paper showed reported Sharpe collapsing
  below buy-and-hold once frictions were added; TrustTrade found identical inputs produce
  divergent decisions, which disqualifies a model from anything touching sizing.
  **Rejected:** letting the model pick strikes and sizes. It is what most entries will do.
- **The model is not reproducible, and we measured it per serving stack rather than pooling**
  — TrustTrade's finding that identical inputs produce divergent decisions is the load-bearing
  claim behind every design choice above, so it was reproduced on this system rather than
  borrowed. Every LLM call is recorded whole (`agent/replay.py`) and `--replay` re-issues it.

  **The replay sends cached data, and that is executable, not asserted.** A recorded request
  carries the whole conversation including ~108k characters of frozen tool results; the
  harness re-issues it and never executes what comes back. `verify_replay_isolation.py`
  blocks DNS for every host except the model provider, replays, and reports every host
  resolved. It exits non-zero if anything but the provider is contacted. This closes the
  confound that would otherwise make the whole measurement market-data drift.

  **Stratified, n=60 per cell, cells and quotability pre-registered in `CELL_RULES` before
  the run.** Temperature 0, fixed seed where the provider supports one.

  | cell | n | divergent | 95% CI | decision changed |
  |---|---|---|---|---|
  | gpt-4o-mini / proposer *(free choice)* | 60 | **90.0%** | 79.8–95.3% | **40/40 = 100%** (CI 91.2–100%) |
  | gpt-4o / critic *(tool_choice forced)* | 60 | **98.3%** | 91.1–99.7% | 59/60 = 98.3% (CI 91.1–99.7%) |
  | gpt-4o-mini / single_agent | 60 | **65.0%** | 52.4–75.8% | — no decision turns |
  | Qwen2.5-7B / arbiter *(Featherless)* | 60 | n/a | — | **ruling changed 0/60** (CI 0–6.0%) |

  **There is no pooled figure, deliberately.** The cells span 0% to 98%, so no single number
  describes the system. An earlier 70% was reported before this: it pooled two models, and 31
  of its 40 replays were one model in one role. It is superseded, not refined.

  **The headline is the decision-tool rate, reported per cell and never pooled.** On the free
  choice cell, **every one of 40 turns where the Proposer actually decided produced a
  different decision on replay** — 100%, 95% CI 91.2–100%. The critic's 98.3% is not
  comparable and is not combined with it: its `tool_choice` is forced, so its output space is
  constrained by construction. Constraint did not buy determinism either.

  **Featherless/Qwen is the outlier and the caveat matters more than the number.** Its ruling
  was identical on all 60 replays, while its *wording* differed on 42 of 60 — deterministic in
  verdict, not in prose. Its `divergence_rate` reads 0.0% only because "divergent" requires
  differing tool calls and this responder emits none, so that field is flagged
  `divergence_rate_meaningful: false` in the export. And it is 4 unique decisions replayed 15×:
  it answers "is Featherless deterministic on a fixed input", and is **not** a model
  comparison.

  `single_agent` is quotable with a caveat carried wherever it appears: 11 unique decisions at
  5.5× repeats measures same-input determinism, not conversation diversity. Its 65.0% closely
  matches the 64.5% seen in the earlier run, which is the one continuity between the two
  measurements.

  **This is why the gate is deterministic Python and not a prompt.** A model whose decision
  changes on 100% of replays of byte-identical input cannot be the thing that decides whether
  a trade is permitted. One divergence replaced four `get_option_contracts` reads with a
  single `place_option_order` — a research turn became an order attempt on identical inputs
  (decision `5c11b241404d`; nothing was placed, the harness never executes).
  **Rejected:** claiming reproducibility because temperature is 0, and quoting a pooled rate
  across serving stacks with different non-determinism mechanisms.

- **The gate is priced, not just defended** — `agent/counterfactual.py` re-runs every refused
  strategy through the same simulator that refused it, so the refusal has a dollar figure
  attached instead of only a rationale. It is reported whichever way it comes out. A short
  window can only ever price the decision; it cannot judge it, because the gate refuses on
  the *width* of the bootstrap interval and never on the sign of the latest observation. See
  §Variance.
- **Statistical gate before any strategy is tradeable** — kept from the original build. This
  is the strongest single asset in the codebase and maps directly onto what Alpaca's own
  skills library asks for.
- **Graveyard is append-only, failures included** — a falsified idea documented is worth more
  to a judge than a curated list of winners.
- **Cash-settled European index options preferred where possible** — removes early
  assignment, ex-dividend assignment on short calls, and pin risk in one decision.
  **Rejected:** American-style single-name shorts held near expiry.
- **Defined risk only.** No undefined-risk shorts, ever.
- **Demonstration mode, after the gate refused everything.** As of 1 Sep 2026 the validation
  gate has cleared nothing: three liquid ETFs, seven structures, 21 documented FAILs. The
  closest candidate (`vertical_credit_spread_2d`, 76-81% win rate, Sharpe 1.67-1.81) was
  refused because its Sharpe CI lower bound stays negative — correct behaviour on a
  negatively skewed payoff, and the reason a high win rate is a shape parameter rather than
  evidence.

  The gate governs whether we may **claim** an edge. It does not govern whether an order is
  **safe**. A defined-risk vertical spread's worst case is bounded and known before entry —
  that is why defined risk was the requirement in the first place — so "no evidence of edge"
  and "this order could hurt the account" are different statements, and only the first is
  true here. We therefore execute exactly one bounded demonstration of the full path — chain
  read, strike selection in deterministic Python, risk gate, MCP multi-leg order, managed
  exit — while reporting plainly that zero strategies cleared validation.

  Every constraint demonstration mode adds is tighter than the normal path and none is
  env-tunable: defined-risk multi-leg only, 1 contract, 1 open position, max loss ≤ 0.5% of
  NAV, SPY only. Every other gate stays armed — DTE window, kill switch, daily loss limit,
  the Thursday 15:45 flat rule, order-result checking. It refuses to arm at all if anything
  has cleared validation, so a demonstration trade can never sit alongside a validated one.
  Every order, log line and trade-log entry it produces is stamped
  `validation_status="UNVALIDATED_DEMONSTRATION"`.

  **Rejected:** relaxing the gate's criteria after seeing that everything failed. That is the
  exact post-hoc move the gate exists to prevent, and a reviewer would be right to discount
  every other number in this repo on the strength of it.

## Variance — read before writing any performance claim

The judged window is roughly 3.5 sessions. With `t = Sharpe × √(T/252)`, a strategy with a
true annualised Sharpe of 1.0 produces `t = 0.118` and a 54.7% chance of positive P&L. Skill
accounts for about 1.4% of outcome variance. Detecting an edge at that Sharpe needs ~970
trading days.

Consequence: our P&L result is close to pure noise, and if ~100 entrants all have zero edge,
the expected winning score is around 3σ — meaning the P&L leaderboard is won by whoever
sized largest, not whoever reasoned best. **We do not try to win that leg.** We report the
t-statistic of our own result alongside it, and we report a conservative mark-to-market
(ask-side entries, bid-side exits, spread-width penalty) beside Alpaca's simulated number.

## The evaluation window

- Trading sessions available: Tue 1, Wed 2, Thu 3 Sep, plus 90 minutes on Fri 4 Sep.
- **Nonfarm payrolls prints 08:30 ET Friday 4 Sep = 6:00 PM IST.** Deadline is 8:30 PM IST
  = 11:00 AM ET. Market opens 09:30 ET. The account is marked in a post-NFP session with a
  three-day weekend behind it.
- Therefore: the last real trading decision is **Thursday**, positions must be closable
  inside the window, and the book is flat or explicitly long-gamma into the print.

## Technical debt

- [ ] Bootstrap resamples overlapping windows as i.i.d. — must become a moving-block bootstrap.
- [ ] `iron_condor` and `covered_call` are structurally untradeable but still offered to the LLM.
- [ ] Per-trade capital cap rejects the only currently-validated strategy (see TODO.md).
- [ ] Backtest hold horizon (21 trading days) does not match the judged horizon.
- [ ] Multi-leg legs submitted sequentially, not atomically.
- [ ] Order manager exit rules are universal, not per-strategy.
- [ ] ~10 hand-copied response-envelope unwraps instead of `mcp_parsers.py`.

---

## Standards

Follows the `engineering-standards` skill. **Overrides for this project:** solo/pair build on
`main` plus short branches, not the four-branch chain. No CODEOWNERS. Commit frequently —
judges check whether history is spread across the event window.
