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
  "heartbeats":     { ... },
  "adversarial":    { ... },
  "fill_analysis":  { ... },
  "determinism":    { ... },
  "arbiter":        { ... },
  "counterfactual": { ... }
}
```

> **schema_version 2 — breaking.** The `reproducibility` section is now `determinism`,
> carrying per-replay detail, a divergence rate with a Wilson 95% interval, and a count of
> divergences that changed which tool was called. A reader keyed on `reproducibility` must
> be updated. `counterfactual` is new and additive.

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
| `source` | string \| null | which surface answered: `"alpaca-cli"` or `"alpaca-py"`. `null` when no read was attempted |
| `source_version` | string \| null | CLI version when `source` is `"alpaca-cli"` |
| `error` | string \| null | `null` on success; otherwise why every other field is `null` |

The account and positions are read through the **Alpaca CLI** (`alpacahq/cli`) first and
alpaca-py second; `source` records which one answered, and the two were cross-checked to
agree field for field. The CLI is the primary surface deliberately, refreshed every cycle by
the supervised loop. The SDK fallback is what keeps a checkout without the binary — this
worktree included — rendering a real account rather than an error panel. Order placement
does **not** go through the CLI; it stays on the MCP server, behind one risk gate.

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
| `closing` | bool | true on a row that closed a position rather than opened one |
| `exit_reason` | string \| null | why the position was closed — the session-window/NFP reason on a flatten |
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

## `adversarial`

The risk layer under attack by hostile model output. Written by
`python main.py --adversarial` (`agent/adversarial.py`) into `logs/adversarial.json` and
copied through here verbatim. Absent until that has been run, in which case every count is
`null` and `results` is `[]` — never a clean result nobody produced.

| field | type | notes |
|---|---|---|
| `ran_at` | ISO-8601 UTC \| null | |
| `attacks_run` / `blocked` / `got_through` | int \| null | |
| `masked_by_validation_gate` | int \| null | attacks the validation gate stops *before* their intended defence is reached |
| `orders_submitted` | int \| null | must be `0`. Counted on the account either side of the run, not asserted from internal state |
| `order_count_source` | string \| null | how that count was read |
| `verdict_basis` | string \| null | which run the verdict comes from |
| `results[]` | array | one record per attack |

Each `results[]` entry carries `id`, `name`, `expected_to_be_stopped_because`, `verdict`
(`"blocked"` or `"GOT THROUGH"`), `approved`, `rejection_reason`,
`estimated_capital_at_risk`, `payload`, and where relevant a `full_stack` block.

**Read `verdict` from the isolated run, and understand why.** The first run of this harness
reported 13/13 blocked and was nearly worthless: six attacks died at the backtest-validation
gate before ever reaching the defence they were written to test. "Nothing cleared on SPY" is
true and says nothing about whether a 400-contract order is caught by the capital cap. So
every attack runs twice — `full_stack` is what happens today, and the top-level verdict comes
from an isolated run with validation satisfied and nothing else lifted, forcing each attack to
meet its intended layer. `masked_by_validation_gate` counts how many defences are currently
unexercised in production; if a strategy ever clears, that masking stops.

Two real holes were found this way and fixed — a `ratio_qty` mismatch priced a 1×2 as a 1:1
vertical, leaving a naked short charged nothing, and an unlisted contract was approved. The
second is only closed when a caller supplies the chain it fetched (the gate does no network
I/O); `results[].without_chain` records what happens when nobody does.

---

## `fill_analysis`

Indicative quote versus simulated fill, per leg, for every order submitted. This exists to
answer an open question: does Alpaca's paper fill engine price against fresher data than the
free Indicative Pricing Feed lets us see? If it does, every expected-credit figure in this
project is systematically off in a direction we can measure.

| field | type | notes |
|---|---|---|
| `orders_measured` / `legs_measured` / `legs_filled` | int | |
| `mean_delta` | float \| null | over **filled legs only**. `null` means not yet measurable, never "no difference" |
| `legs_above_mid` / `legs_below_mid` / `legs_at_mid` | int | |
| `delta_sign_convention` | string | positive = the fill printed **above** the indicative mid we could see |
| `feed` | string | the feed the indicative side came from |
| `orders[]` | array | per-order records, each with `legs[]` |
| `realised` | object | realised P&L — see below |

`realised` sums the **signed cash flow of every filled leg**: a sell is cash in, a buy is
cash out, whether the leg opens or closes. No entry/exit pairing, so it cannot mis-pair a
spread. `realised_pnl_dollars` is **gross of fees** — Alpaca's per-contract fees are not in
the fill prices. It is `null` until something fills, and `round_trip_complete` is false while
`legs_open` is non-zero, in which case the total is a running figure and not a result.
`cash_flows[]` shows the per-leg arithmetic so the number can be checked by hand.

Each leg carries `indicative_bid` / `indicative_ask` / `indicative_mid`, `quote_captured_at`,
`on_chain`, `filled_price`, `filled_qty`, `filled_at`, `status`, `delta`, `delta_sign` and
`capture_lag_seconds`.

The pre-trade quote is read from the chain snapshot the caller already fetched to build the
order — no extra round trip, nothing new between the decision and the submission. The cost is
a gap between when that chain was read and when the order went in, and `capture_lag_seconds`
records it rather than hiding it. Everything on the fill side happens after submission, where
latency is free.

An unfilled or canceled leg yields `filled_price: null` and `delta: null`. No zero is ever
fabricated, and an unfilled leg is not averaged into `mean_delta` as though it filled at mid.

---

## `determinism`

What replaying past decisions actually showed. **Was `reproducibility` in schema_version 1.** Written from `logs/llm_calls.jsonl` (every
LLM call recorded whole) and `logs/replay_report.json` (`python main.py --replay all`).

| field | type | notes |
|---|---|---|
| `calls_recorded` / `distinct_decisions` | int | |
| `tier` | string | the reproducibility tier actually reached |
| `replays` / `exact` / `equivalent` / `divergent` | int \| null | `null` until a replay has been run |
| `divergence_rate` | float \| null | fraction of replays that diverged |
| `divergence_rate_ci95` | object | `{lower, upper, method}` — Wilson score, which stays inside [0,1] where the normal approximation does not |
| `divergent_tool_changed` | int \| null | divergences that changed **which tool was called** — an action change |
| `divergent_args_only` | int \| null | divergences that kept the same tools and changed only arguments |
| `distinct_decisions_replayed` / `repeats_per_decision` | int \| null | repeated trials on one fixed input are the direct test of the claim |
| `failed_to_replay` | int \| null | replays that could not be issued (e.g. a 429). Excluded from every count above |
| `headline` | string \| null | one sentence checkable against `results[]` |
| `across_fingerprint_change` | int \| null | replays where OpenAI's `system_fingerprint` moved between record and replay |
| `conditions` | string \| null | the settings the replay ran under |
| `results[]` | array | per-decision outcomes |

Three outcomes: `exact` (identical text and tool calls), `equivalent` (same tool calls with
the same arguments, different prose), `divergent` (different action). `equivalent` is the
honest target — an agent that picks the same trade for differently-worded reasons has
reproduced its decision, and demanding identical prose would test something we do not care
about. A replay that could not be issued at all is `replay_failed` and is excluded from the
counts rather than scored as a divergence.

**The measured result, and it is the point of this section.** Under temperature 0, a fixed
seed, the same model and an *unchanged* `system_fingerprint` — the conditions under which
OpenAI's best-effort determinism is supposed to hold — 8 replays returned **2 exact, 1
equivalent, 5 divergent**. One divergence flipped from `get_option_chain`, a read, to
`place_option_order`, an order, on identical inputs.

That is the strongest argument in this project for putting every order behind a
deterministic gate: the model is not reproducible even under ideal conditions, and the same
prompt can move it from reading data to attempting a trade. A replay only re-issues the
request to the model; it never executes what comes back.

---

## `arbiter`

The third seat (`agent/arbiter.py`, a Featherless model). Consulted only when the Critic
rejects a trade the Proposer proposed — never on a Critic approval, and never on a Proposer
skip, because it exists to resolve disagreement and there is none in either case.

| field | type | notes |
|---|---|---|
| `consulted` | int | times a genuine disagreement reached it |
| `unavailable` | int | times it could not be reached at all |
| `rulings` | object | counts of `proceed` / `abandon` / `deadlock` |
| `overruled_critic` | int | `proceed` rulings. **Not** a count of orders |
| `model` | string \| null | most recent model that answered |
| `authority` / `invoked_when` / `fails_closed` | string | stated in the data, not only in prose |
| `recent[]` | array | last 25 rulings with rationale, latency and any error |
| `unavailable_reasons[]` | array | why it could not be reached |

**Its ruling is advisory, and that is enforced in code rather than asserted.** A `proceed`
ruling does not execute anything — it only declines to end the cycle, and control then falls
through to the same strategy cross-check and the same `RiskGate.check()` that a Critic
approval would have reached. There is no path in `multi_agent.py` from a ruling to an order
tool that skips the gate, which `test_adversarial.py` asserts against the source. So
`overruled_critic` counts times the council declined to stop early, never times an order
happened; an order exists only where `gate_decisions` shows an approval.

Every failure mode fails closed. `abandon`, `deadlock`, an unparseable or empty response, a
timeout, or an absent `FEATHERLESS_API_KEY` all leave the Critic's veto standing.

---

## `counterfactual`

What the refused strategies would have returned, priced with the same simulator that refused
them. Written by `python main.py --counterfactual`.

| field | type | notes |
|---|---|---|
| `ran_at` | ISO-8601 UTC \| null | |
| `window` | object \| null | `entry_date`, `mark_date`, `trading_days_held`, `underlying_move_pct` per symbol |
| `pairs_evaluated` / `pairs_refused` | int \| null | |
| `refused_profitable` / `refused_unprofitable` | int \| null | |
| `total_pnl_dollars_if_all_taken` | float \| null | every refused trade taken at once |
| `mean_pnl_dollars` / `best` / `worst` | | |
| `engine` / `marks` | string | which code produced it and on what price path |
| `interpretation` | string | what the number does and does not establish |
| `caveats[]` | array | read these before quoting the number |
| `results[]` | array | per-pair `pnl_dollars`, `net_return_pct`, `exit_reason`, `closed_early`, `refusal_reasons` |

`underlying_move_pct` is there because a short-window result is largely a function of that
window's direction, and the P&L should never be read without it. `closed_early` is true
wherever the window was shorter than the strategy's natural hold, which makes these
**marks, not realised results**.

This prices the gate's decision; it does not judge it. The gate refuses on the width of the
bootstrap interval, never on the sign of the most recent observation — so a short window
cannot confirm or overturn a refusal in either direction.

---

## Changing this file

Add fields freely — readers should ignore unknown keys. Renaming or removing a field, or
changing a type, is a breaking change: bump `schema_version` and say so in both worktrees.
