# `logs/dashboard.json` — schema

The contract between this repo and the dashboard worktree. This repo writes the file;
the dashboard reads it. Change one and change the other.

**Producer:** `agent/dashboard.py`, one function — `export_dashboard(path=None) -> dict`.
**Regenerate:** `python main.py --export-dashboard`, or `python -m agent.dashboard`.
Every other `main.py` mode refreshes it in a `finally` block, including when the cycle raises.
**Self-check:** `python test_dashboard_export.py`.

`logs/` is gitignored, so a committed copy of a real export lives at
[`docs/dashboard.example.json`](dashboard.example.json) — build against that, and
regenerate it with:

```
python -c "from agent.dashboard import export_dashboard; export_dashboard('docs/dashboard.example.json')"
```

---

## Two rules the reader can rely on

**1. Nothing is invented.** Every value is copied from an artifact that already exists
(`logs/backtest_report.json`, `logs/trade_log.jsonl`) or fetched live from Alpaca. Where a
value was never recorded, the key is **present and `null`** — never a zero, a placeholder or
an empty string standing in for a number. `null` means "not recorded"; `0` means zero.

**2. It always produces valid JSON.** An empty `logs/`, a missing backtest report, absent
Alpaca credentials, a market that is closed, and a half-written last line in the JSONL each
degrade to nulls and empty lists. The exporter does not raise on missing input.

Consequences worth knowing before you write a chart:

- **`estimated_capital_at_risk` is a real number on both approvals and rejections**, logged
  by the gate itself. It is `null` in exactly two cases, and `null` means "never computed",
  never "risked nothing": on a decision the gate refused *before* it got as far as computing
  capital (unrecognisable OCC symbol, DTE outside the window, kill switch, unvalidated
  symbol), and on records written before this logging existed — those are not backfilled.
  The figure also appears, rounded, inside the rejection's `reason` prose. **Do not parse it
  out of the prose**: the prose is rounded for humans, is free to be reworded, and the
  structured field is the one that is correct.
- **CI bounds are `null` on `extended` and sub-period records.** The engine saves those
  runs' metrics but not their bootstrap intervals. Only `primary` records have real bounds.
- **`current_mark` is `null` on a closed or expired trade.** A leg still showing in the
  account is open; one that is gone is simply absent from the positions list.

---

## Top level

```jsonc
{
  "schema_version": 1,
  "meta":           { ... },
  "account":        { ... },
  "validation":     [ ... ],
  "gate_decisions": [ ... ],
  "trades":         [ ... ],
  "heartbeats":     { ... }
}
```

`schema_version` is an integer. It increments on any breaking change to the shapes below.

---

## `meta`

| field | type | notes |
|---|---|---|
| `generated_at` | ISO-8601 UTC string | when this file was written |
| `data_feed` | string | always `"Alpaca Indicative Pricing Feed, not OPRA"`. Free tier has no OPRA data; options quotes come from a derived, deliberately randomised product. **Do not render copy implying real-time NBBO option quotes.** |
| `engine_commit` | string \| null | short git hash of the engine that produced these numbers; `null` outside a git checkout |
| `paper_trading` | bool | always true — there is no live path |
| `bootstrap` | object | see below |
| `backtest_report_generated_at` | ISO-8601 UTC \| null | mtime of `logs/backtest_report.json`, i.e. how stale `validation` is |
| `distinct_pairs_evaluated` | int | strategy/symbol pairs evaluated — count of `validation` records with `scope == "primary"` |
| `total_validation_records` | int | length of `validation`, including retest and half-period re-runs |
| `pairs_cleared` | int | pairs cleared for live trading (`enabled_for_paper == true`) |
| `pairs_passing_primary_gate` | int | pairs that passed the primary bootstrap-CI gate (`passed == true`), which is a *lower* bar |

### The counts, and the arithmetic to get right

These four are separate numbers on purpose, and three of them are easy to conflate:

- **`distinct_pairs_evaluated` ≠ `total_validation_records`.** At the time of writing they
  are **21 and 24**. There are 3 symbols × 7 strategies = 21 pairs. One pair
  (IWM / `covered_call`) also has an extended-history retest and two sub-period half records,
  which is the extra 3. Every record is in the same flat list, distinguished by `scope`.
  **The headline number is 21.** Do not sum `trades` across scopes — you would count the
  same pair's history several times.
- **`pairs_cleared` ≠ `pairs_passing_primary_gate`.** Currently **0 and 1**. IWM /
  `covered_call` passes the primary bootstrap gate and then fails the sub-period stability
  check, so it never cleared. The project's headline finding is *nothing cleared*; a
  dashboard reading `passed` instead of `enabled_for_paper` would print "1 cleared" and
  contradict it.

### `meta.bootstrap`

| field | type | notes |
|---|---|---|
| `method` | string | `"percentile bootstrap; circular moving-block where trades overlap"` |
| `n_boot` | int \| null | resamples, currently 2000 |
| `ci` | float \| null | interval width, currently 0.95 |
| `seed` | int \| null | RNG seed, currently 42 — runs are reproducible |
| `block_size_by_strategy` | object \| null | strategy name → block length |

Block size is **not one number**. It is `ceil(hold_days / step_days)` per strategy: an
overlapping entry schedule shares price paths between consecutive trades and needs a wider
interval, while a schedule whose step is at least as long as its hold has no overlap and
collapses to the plain i.i.d. bootstrap at `1`. Render it per strategy or not at all.
Currently `vertical_credit_spread_2d` is 1, `iron_condor_vrp_45_21` is 7, the rest are 3.

---

## `account`

One object. Live from Alpaca at generation time.

| field | type | notes |
|---|---|---|
| `equity` | float \| null | |
| `last_equity` | float \| null | previous close — the denominator for day P&L |
| `buying_power` | float \| null | |
| `options_buying_power` | float \| null | |
| `open_position_count` | int \| null | `null` (not `0`) when the fetch failed |
| `account_number` | string \| null | paper account |
| `timestamp` | ISO-8601 UTC | when the fetch was attempted, always present |
| `error` | string \| null | `null` on success; otherwise why every other field is `null` |

If `error` is non-null, show it. An account panel silently reading zero is worse than one
that says the fetch failed.

---

## `validation[]`

One flat list, every strategy/symbol result from the last backtest run, pass or fail.
Filter and group by `scope`; never assume list order.

| field | type | notes |
|---|---|---|
| `symbol` | string | |
| `strategy` | string | |
| `scope` | string | one of the four below |
| `passed` | bool \| null | did **this check** pass |
| `enabled_for_paper` | bool \| null | did the **pair clear** for live trading. `primary` records only; `null` on other scopes |
| `trades` | int \| null | |
| `win_rate` | float \| null | fraction, not percent — `0.4699` is 47% |
| `sharpe` | float \| null | |
| `mean_return_pct` | float \| null | fraction per trade |
| `total_pnl_dollars` | float \| null | |
| `mean_return_ci` | `{lower, upper}` | floats or `null`; both keys always present |
| `sharpe_ci` | `{lower, upper}` | floats or `null`; both keys always present |
| `reasons` | string[] | gate's own prose. Empty on a pass |

### `scope` values

| value | what it is | counts toward a pair? |
|---|---|---|
| `primary` | the strategy/symbol pair the gate ran on | **yes** |
| `extended` | extended-history retest, only where one was run | no — re-run of an existing pair |
| `sub_period_first_half` | stability check on the first half of extended history | no |
| `sub_period_second_half` | ...and the second | no |

The two half-period scopes carry `sharpe` and `mean_return_pct` only. `trades`, `win_rate`
and both CI objects are `null` there because the engine does not save them.

The gate is: at least 30 trades, **and** a bootstrap CI on mean return that excludes zero on
the upside, **and** the same on Sharpe. A CI whose `lower` is ≤ 0 is a fail — that is what
every `reasons` entry currently says.

---

## `gate_decisions[]`

Every RiskGate verdict the trade log preserves. **Sorted rejections first, then newest
first within each group** — the interesting content is what the gate refused.

| field | type | notes |
|---|---|---|
| `ts` | ISO-8601 UTC \| null | |
| `approved` | bool | |
| `tool` | string \| null | MCP tool the gate was called on |
| `agent` | string \| null | `openai`, `proposer`, `demonstration`, … |
| `reason` | string \| null | the gate's own rejection string. `null` on an approval |
| `estimated_capital_at_risk` | float \| null | dollars the gate computed for this order. `null` only where capital was never computed — see rule 1 |
| `capital_basis` | string \| null | how the figure was derived, e.g. `"(5.00 width - 0.77 credit) x 100 x 1"`. Multi-leg orders only; the single-leg model has no basis string |
| `validation_status` | string \| null | e.g. `UNVALIDATED_DEMONSTRATION` |
| `symbol` | string \| null | order symbol where the call carried one; `null` for non-order tools |

Three log shapes feed this, normalised onto one `approved` bool: a `tool_call` record
carrying an `approved` field (the LLM paths), and `demonstration_approved` /
`demonstration_rejected` (the demonstration path logs its verdict under its own types).
The approval is logged even on a dry run, which is the demonstration path's default — that
record is the only trace the single demonstration trade leaves before it is submitted.

This is the column that carries the risk evidence. A refused naked short put and the
approved defined-risk spread that replaced it read as **$75,500 rejected vs $423 approved**,
which is the whole argument for pricing multi-leg orders as structures rather than per leg.

---

## `trades[]`

Every order actually placed, newest first. Sourced from `demonstration_order`,
`multi_agent_order` and `deterministic_order` log records.

| field | type | notes |
|---|---|---|
| `ts` | ISO-8601 UTC \| null | |
| `event` | string | which of the three order events this came from |
| `symbol` | string \| null | |
| `strategy` | string \| null | `null` on the demonstration path, which has no validated strategy |
| `validation_status` | string \| null | `UNVALIDATED_DEMONSTRATION` on the demonstration trade. Label it as such wherever it surfaces |
| `legs` | string[] | OCC contract symbols |
| `entry_credit` | float \| null | net credit per structure, positive. `null` when the order was a debit or the price was unsigned — Alpaca signs a multi-leg limit price, negative for credit received. A debit is not reported as a credit |
| `limit_price` | float \| null | raw signed limit price as submitted |
| `capital_at_risk` | float \| null | from the gate, where the log site recorded it |
| `capital_basis` | string \| null | how it was computed, e.g. `"(6.00 width - 0.81 credit) x 100 x 1"` |
| `open` | bool | whether any leg still shows in the account |
| `current_mark` | object \| null | leg symbol → current price, for legs still open. `null` when none are |
| `error` | string \| null | Alpaca's rejection, if it rejected the order |

An empty `trades` list is a normal state, not a bug: no strategy has cleared validation, so
the agent is correctly refusing to open positions.

---

## `heartbeats`

One object. Written by the supervised loop (`agent/supervisor.py`), one record per pass
**including the passes that do nothing**.

This is the section that separates "the agent evaluated and declined" from "the agent was
off". An account that did not trade for six hours and an agent nobody started produce the
same empty position list; only this tells them apart.

| field | type | notes |
|---|---|---|
| `last_seen_at` | ISO-8601 UTC \| null | most recent heartbeat. `null` means never seen, not "seen with zero cycles" |
| `total_cycles` | int | |
| `cycles_traded` | int | passes that ran a full trading cycle |
| `cycles_declined` | int | passes that deliberately did nothing — market closed, entries blocked, already flat |
| `cycles_failed` | int | passes that raised. A failure is its own state, neither a trade nor a decline |
| `recent[]` | array | the last 120 heartbeats, oldest first |

`recent[]` entries carry `ts`, `cycle`, `action` (prose describing the decision),
`market_open`, `traded`, `entries_blocked`, `must_be_flat`, `cycle_cost_usd`,
`session_spend_usd`, `consecutive_failures` and `error`.

`entries_blocked` and `must_be_flat` hold the session-window reason string when those rules
fired, and `null` otherwise — so a stretch of declines is attributable to a specific rule.
Three consecutive failures trip the kill switch and stop the loop; the last heartbeat before
that says so in `action`.

---

## Changing this file

Add fields freely — readers should ignore unknown keys. Renaming or removing a field, or
changing a type, is a breaking change: bump `schema_version` and say so in both worktrees.
