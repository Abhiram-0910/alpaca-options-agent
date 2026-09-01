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
- **Statistical gate before any strategy is tradeable** — kept from the original build. This
  is the strongest single asset in the codebase and maps directly onto what Alpaca's own
  skills library asks for.
- **Graveyard is append-only, failures included** — a falsified idea documented is worth more
  to a judge than a curated list of winners.
- **Cash-settled European index options preferred where possible** — removes early
  assignment, ex-dividend assignment on short calls, and pin risk in one decision.
  **Rejected:** American-style single-name shorts held near expiry.
- **Defined risk only.** No undefined-risk shorts, ever.

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
