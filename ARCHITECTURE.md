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
- **The model is not reproducible, and we measured it rather than citing it** — TrustTrade's
  finding that identical inputs produce divergent decisions is the load-bearing claim behind
  every design choice above, so it was reproduced on this system rather than borrowed. Every
  LLM call is recorded whole (`agent/replay.py`) and `--replay` re-issues it. At temperature
  0, a fixed seed, the same model and an **unchanged `system_fingerprint`** — the conditions
  under which OpenAI's best-effort determinism is supposed to hold — the measured divergence
  rate is in `logs/replay_report.json` and the export's `determinism` section, with a Wilson
  95% interval and a count of how many divergences changed *which tool was called* rather
  than only its arguments. One divergence replaced four
  `get_option_contracts` reads with a single `place_option_order` — a research turn became
  an order attempt on byte-identical inputs (decision `5c11b241404d`; the harness only
  re-issues the request and never executes what comes back, so nothing was placed).
  **This is why the gate is deterministic Python and not a prompt.** A model that can move
  from reading data to attempting a trade without its inputs changing cannot be the thing
  that decides whether a trade is permitted.
  **Rejected:** claiming reproducibility because temperature is 0. Before this work,
  temperature and seed were not even set — the runs were not merely non-reproducible, they
  were not attempting to be.
- **An evidence block that steers away from its own validated universe** — kept as a finding,
  because it is the most instructive failure in this build and it never once looked like one.

  The Proposer proposed a cash-secured put on AAPL **17 consecutive times** and was rejected
  17 consecutive times for the same reason: AAPL never passed validation. Every layer below
  it behaved perfectly — the Critic vetoed each time on correct grounds, the arbiter upheld
  each veto, the risk gate would have refused anyway, nothing reached the account. The
  pipeline looked like it was working. It was looping.

  **Cause: the evidence block only listed the symbols that had been backtested.** SPY, QQQ
  and IWM each carried an explicit "no strategy passed" warning. The other 15 watchlist
  symbols were absent entirely, so they carried no signal at all. The model read
  absence-of-mention as absence-of-objection and picked AAPL, the first unmentioned name in
  the watchlist. The three symbols with evidence were the only three it was warned about.
  A prompt that presents evidence this way does not merely fail to steer — it steers
  *away* from the validated universe, and the more thorough the warning on the tested
  symbols the stronger that push becomes.

  **CORRECTED 4 Sep — the first write-up of this finding was wrong, and the correction is
  the better finding.** It said the proposals were "byte-identical AAPL". They were not.
  Checking the payloads rather than the summary line:

  | across 22 AAPL proposals | distinct values |
  |---|---|
  | OCC option symbols | **19** |
  | rationales | **22** |
  | (symbol, strategy) pairs | **2** |

  Only the *ticker and the strategy label* repeated. Everything else varied, and often
  incoherently: one proposal was a **call** (`AAPL260904C00305000`) labelled
  `cash_secured_put`; another proposed a **$145 strike** with a rationale citing "strong
  support around the $325 level". These are not the outputs of a model stuck in a groove.

  So the mechanism is not determinism at all — it is a **prompt-level attractor**. The
  evidence block warned about the only three symbols that had evidence and said nothing
  about the other fifteen, so AAPL, first among the unwarned, won every cycle regardless of
  how much the rest of the output moved. The model was as variable as ever; the funnel it
  was pouring through had one exit.

  This also dissolves a contradiction we thought we had. A ~70% per-call divergence rate and
  "17 identical proposals" would have been in real tension. There were never identical
  proposals, so there is no tension: same-input replays diverge, and different-input cycles
  converged on one ticker for a reason that has nothing to do with sampling.

  **On temperature:** the earlier claim that "temperature 0 exposed it" does not survive
  either, because there was no repetition to expose. On 2 Sep at temperature 1.0 the
  proposals varied (one skip, then MSFT); from 3 Sep at temperature 0 they varied too, and
  simply kept landing on the same ticker. What made the bug legible was the *ticker* column
  of the log repeating 22 times, which would have looked the same at any temperature.

  **Fixed two ways.** Every watchlist symbol now appears in the evidence block, with
  never-backtested ones marked `NEVER EVALUATED — not tradeable`, and the prompt states the
  operational rule instead of hedging it ("if no symbol shows PASSED, the correct output is
  `action=skip`"). And `run_cycle` now short-circuits: when validation is required and
  nothing has cleared, the set of approvable proposals is empty, so it logs a structured
  `no_validated_universe` decision and returns without calling a model at all — 0 tool
  calls, 0 API calls, $0.00.

  **Rejected:** feeding the Critic's rejection reasons back to the Proposer as memory. The
  Critic judges *rationale quality* and reads prose, so that gradient teaches the model to
  phrase its way past the reviewer rather than to propose better trades. The risk gate is
  deterministic and would still refuse, so the cost would never show up as money — it would
  show up as a Critic-approved proposal on an unvalidated symbol sitting in the audit trail,
  which is the more expensive currency here. Also rejected: raising temperature to restore
  variety, which buys different wrong answers and forfeits the determinism measurement.

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
