# Autonomous Options Trading Agent — Alpaca AI Trading Agents Hackathon

An autonomous AI agent that trades options on Alpaca's paper trading environment. Claude
reasons over live account state, market data, and news — surfaced through **Alpaca's
official MCP server** — to select and execute one of several options strategies per symbol,
each pre-validated against a statistical backtesting gate, with every order also gated by
a hard-coded risk layer before it ever reaches Alpaca. Two agent architectures are available
side by side (`--once`/`--loop` for single-agent, `--multi-agent` for the two-agent pipeline),
plus a zero-LLM-cost deterministic path for testing the mechanics without spending anything.

## How it works

```
run_backtest.py  ──►  logs/backtest_report.json     (pass/fail per symbol/strategy)
                       docs/strategy_graveyard.md    (every result, pass or fail, with real numbers)
                                │
                                ▼
main.py --loop  ──►  agent/live_agent.py  (single agent)
                        │
                        ├── spawns `uvx alpaca-mcp-server` (agent/mcp/client.py)
                        │     account info · positions · bars · news · option chain · orders
                        │
                        ├── Claude (Anthropic API) — tool-use loop
                        │     reads backtest evidence + live data, researches the watchlist,
                        │     decides whether/what to trade, places the order itself
                        │
                        └── agent/risk/gates.py — intercepts every place_option_order call

main.py --multi-agent  ──►  agent/multi_agent.py  (two agents)
                        │
                        ├── Proposer — same MCP tools MINUS every order-placing one, plus a
                        │     local propose_trade tool; structurally cannot place an order
                        │
                        ├── Critic — separate, adversarially-prompted Claude call (no tool
                        │     loop, bounded cost) that reviews the proposal and can veto it
                        │
                        └── agent/risk/gates.py — same hard checks, still has final say
```

### 1. AI logic
Claude is given the *tools*, not a hand-written decision tree: every account, market-data,
and order-placement operation is one of Alpaca's own MCP tools (`get_account_info`,
`get_stock_bars`, `get_option_chain`, `get_news`, `place_option_order`, ...), exposed to
Claude via the Anthropic Messages API's native tool-use. Each cycle, Claude:

1. Reads its current account/positions snapshot (handed to it up front).
2. Independently researches 2–4 watchlist symbols — bars, news, and the live option chain
   filtered to the allowed DTE window — before proposing anything.
3. Chooses one of five strategies per symbol (see below), strongly steered toward whichever
   combinations actually **passed** the backtest validation gate, citing both that evidence
   and the live data it just pulled.
4. Places the order itself via `place_option_order`; a rejected call comes back as a normal
   tool result explaining why, so Claude can adapt rather than crash.

This is deliberately *not* a single hard-coded "if RSI < 30 then buy" script — the model
is doing the tool selection, the research sequencing, and the final call, bounded by a
strategy universe and a tool-call budget it's told about in its system prompt
(`agent/live_agent.py:_build_system_prompt`).

### 1b. Multi-agent pipeline — `python main.py --multi-agent` (`agent/multi_agent.py`)
A genuine two-agent split, not a cosmetic one: the **Proposer** gets Alpaca's MCP tools with
*every order-placing tool removed from its tool list* — it is structurally incapable of
calling `place_option_order`, only of calling a local `propose_trade` tool to hand off a
structured proposal (symbol, strategy, real OCC option legs, rationale). A separate
**Critic** — a fresh, adversarially-prompted Claude call ("your job is to find reasons this
proposal is a bad idea... default to REJECT unless the case is genuinely compelling") reviews
that proposal against the same backtest evidence and can veto it via `review_decision`. Only
if the Critic approves does the (still deterministic) `RiskGate` get the actual order — three
independent layers have to agree, not one model's self-confidence in its own reasoning.

Cost is bounded on purpose: the Critic is one non-looped call reasoning over what the
Proposer already gathered, not a second full research loop — roughly one extra Claude call
per cycle versus the single-agent path, not a multiple of it. Verified structurally with a
fully mocked Anthropic/MCP test exercising all three outcomes (trade placed, Proposer skips,
Critic vetoes) before ever spending anything real on it, since no Anthropic key was available
to test against live during development.

### 2. The strategies (`agent/strategies/__init__.py`, `agent/backtest/iron_condor.py`)
| Strategy | Structure | Risk profile |
|---|---|---|
| `cash_secured_put` | Sell a ~0.30Δ put | Income; capital-secured, assignment risk |
| `covered_call` | Sell a ~0.30Δ call against ≥100 owned shares | Income; caps upside, requires existing shares |
| `long_directional` | Buy a ~0.40Δ call or put on a momentum signal | Directional; risk capped at premium paid |
| `vertical_credit_spread` | Sell a ~0.30Δ put, buy a further-OTM put | Defined-risk volatility play; two sequential single-leg orders |
| `iron_condor` | Sell ~0.16Δ put + call, buy ~0.08Δ put + call further out, held to expiration | Defined-risk volatility play; four sequential single-leg orders |
| `iron_condor_vrp_45_21` | Same structure, entered at 45 DTE, force-closed at mark-to-market when 21 DTE remain | Volatility-risk-premium play; credit-multiple stop instead of an ATR-distance stop (see below) — **falsified on this watchlist, see below** |

`iron_condor_vrp_45_21` was added specifically to test whether the "sell index-option volatility on a 45-DTE-entry/21-DTE-exit cycle" edge reported elsewhere (real quoted IV vs. subsequent realized vol, on index options) replicates here. It doesn't: across all 8 watchlist symbols (including SPY/QQQ, the closest US analogs to index options available on Alpaca) it fails cleanly — Sharpe -2.0 to -5.3, bootstrap CI entirely negative, negative total P&L on every symbol, even after matching the vol-estimation window to the 45-day hold. This is disclosed as a real, methodologically sound negative result, not a bug: this project's synthetic backtest prices off **trailing realized volatility**, not real quoted IV (full historical option chains aren't reliably available — see Known Limitations), so it isn't actually testing "does IV overprice subsequent RV," and it's plausible the effect genuinely doesn't transfer from index options to single-name US tech stocks + SPY/QQQ over this period regardless. Full numbers for every symbol are in `docs/strategy_graveyard.md`.

### 3. Backtesting engine (`agent/backtest/`)
No strategy reaches the live agent's prompt as "validated" on vibes. `run_backtest.py` runs
every strategy/symbol combination through a full pipeline before any of it is trusted:

- **Pricing** (`iron_condor.py`, `agent/strategies/__init__.py`) — two paths feeding the same
  downstream shape. `price_iron_condor()` targets deltas via Black-Scholes off a vol input
  (realized-vol proxy or quoted IV) when a full historical option chain isn't available — the
  path the backtest actually uses, since reliable historical chains for a broad watchlist
  aren't. `price_iron_condor_real_quotes()` instead looks up each leg's real quoted price from
  a chain snapshot (live or cached), matching strikes to target deltas among the strikes that
  actually exist, and degrades to synthetic only for legs the snapshot is missing — this is
  what a live/paper pricing check should use once real chain data is in hand.
- **Simulation** (`simulator.py`) — one generic day-by-day simulator handles every strategy
  (single-leg and the 4-leg iron condor alike): marks the position to market each day, exits
  early on a stop-loss, a profit target, or a scheduled managed exit (`force_exit_offset` —
  how `iron_condor_vrp_45_21`'s 21-DTE managed close is expressed), or settles at expiration
  on **intrinsic value**, not a recomputed theoretical price, since that's how real settlement
  works. Every leg pays round-trip **transaction-cost friction** (`costs.py`): a bid/ask
  half-spread in bps plus a flat hurdle %, applied per leg, not as one blanket haircut.
  Two distinct stop mechanisms exist and are **not** interchangeable: an **ATR-derived
  underlying-price-distance stop** (`atr.py`), fixed *before* the backtest runs — never chosen
  after seeing which stop made the equity curve look best — for directional/single-leg
  structures; and a **credit-multiple stop** (exit once a loss reaches N× the credit received)
  for multi-leg credit structures. Using the ATR-distance stop on `iron_condor_vrp_45_21` was
  tried first and forced ~93% of trades to stop out regardless of whether the position was
  actually threatened — its larger vega/mark-to-market sensitivity at 45 DTE made a stop
  distance tuned for shorter, directional trades far too tight. Verified against real data,
  fixed by giving that strategy its own stop mechanism instead of reusing the wrong one.
- **Validation gate** (`metrics.py`) — `compute_metrics()` produces win rate, profit factor,
  Sharpe, total return, max drawdown, and an exit-reason breakdown (expiration vs. stop-loss)
  from the trade list. `validate_strategy_result()` is the actual pass/fail bar: at least 30
  simulated trades (guards against small-sample false positives) **and** a bootstrap
  confidence interval that excludes zero on the upside for **both** mean return and Sharpe —
  a strategy whose CI sits entirely below zero is a confirmed loser, not a pass, even though
  it technically "excludes zero" too. Anything short of both bars is a FAIL, no partial credit.
- **Extended-history retest** — anything that passes on the initial window is automatically
  re-run on a much longer lookback; a PASS that only survives on the short window gets demoted
  (`agent/strategies/lifecycle.py`) as likely overfit, not trusted.
- **Lifecycle** (`lifecycle.py`) — each strategy is a `StrategyAdapter` with independent
  `enabled_for_paper`/`enabled_for_live` flags. `enabled_for_paper` is set automatically by
  the validation gate; `enabled_for_live` requires an explicit, separately-recorded approval
  — a strategy is never auto-promoted from paper to live.
- **Graveyard** (`graveyard.py`) — every validation run, pass or fail, is appended to
  `docs/strategy_graveyard.md` with its real numbers, so a falsified strategy/symbol
  combination is documented instead of silently deleted and doesn't get re-tested from
  scratch by a future run.

The resulting pass/fail-with-metrics report is what feeds Claude's system prompt — not a raw
Sharpe ranking, but a statistically-gated "these combinations have actually cleared the bar"
list, with everything else logged as evidence for why it didn't.

### 4. Risk gates (`agent/risk/gates.py`)
Before anything else: `assert_paper_trading()` (`agent/config.py`) is called at the top of
every order-placing entry point — the CLI layer in `main.py` *and* inside both
`live_agent.run_cycle()` and `deterministic_agent.run_cycle()` themselves, so a caller that
imports and calls those directly (bypassing `main.py`) is still blocked. If
`ALPACA_PAPER_TRADE` isn't true, nothing runs — there is no supported live-trading path in
this project, so this is a hard refusal, not a warning.

Every `place_option_order` tool call — regardless of what Claude decides — then passes through:
- **Kill switch** (`agent/kill_switch.py`, `python kill_switch.py`): a manual lever
  independent of every gate below. `python kill_switch.py on "reason" [--cancel-all]`
  blocks every new order immediately, everywhere — checked both inside `RiskGate.check()`
  and at the top of both agents' `run_cycle()` (so a killed session doesn't even start
  researching, saving Anthropic spend too), and optionally cancels every open order right
  now via `cancel_all_orders`. `python kill_switch.py off` resumes. `status` checks state.
- **Position limit**: at most `MAX_POSITIONS_OPEN` distinct underlyings open at once.
- **Per-trade cap**: capital at risk ≤ `MAX_ALLOCATION_PCT_PER_TRADE` of account equity
  **and** ≤ `MAX_ALLOCATION_USD_PER_TRADE` if set (whichever is more restrictive) — the
  dollar cap exists because a percentage-only cap gets more permissive in dollar terms as
  the account grows, which is the wrong direction for a risk ceiling.
- **Portfolio cap**: total options capital-at-risk ≤ `MAX_TOTAL_OPTIONS_ALLOCATION_PCT`
  **and** ≤ `MAX_TOTAL_OPTIONS_ALLOCATION_USD` if set, same reasoning.
- **DTE bounds**: only `MIN_DTE`–`MAX_DTE`-day contracts, parsed straight from the OCC
  option symbol (no trusting Claude's arithmetic).
- **Naked-call protection**: a short call is only approved if the account already holds
  ≥100 shares of that underlying.
- **Daily loss circuit breaker**: once daily P&L breaches `-DAILY_LOSS_LIMIT_PCT`, every
  new order is rejected until the next day. Correctly anchored across cycles and process
  restarts — even though a fresh `RiskGate` is created per cycle, it re-derives the day's
  starting equity from Alpaca's own `last_equity` account field (prior trading day's close,
  stable server-side all day), not from local state that could reset or drift.
- Equity-market-only and options-only: `place_stock_order` and `place_crypto_order` are
  always rejected — this agent's job is the options premium strategies above, not directional
  stock/crypto exposure.

`place_stock_order`/`place_option_order` requests are only ever forwarded to the real MCP
server *after* they pass every check above; a rejection is returned to Claude as a normal
tool result (never a crash), so the agent can reason about why and try something else.

**Alerting** (`agent/alerts.py`): every order placed, every kill-switch/circuit-breaker
trip, every spend-cap stop, and every cycle error is appended to `logs/alerts.log` in
human-readable form; setting `ALERT_WEBHOOK_URL` (a Slack- or Discord-compatible incoming
webhook) also POSTs each one there. Never blocks or fails the actual trading/risk decision
if the webhook is down or unset.

### 5. Alpaca infrastructure
All trading and market-data operations go through **Alpaca's MCP server**
(`uvx alpaca-mcp-server`, spawned as a subprocess and driven over stdio via the official
`mcp` Python SDK — `agent/mcp/client.py`), fulfilling the hackathon's MCP/CLI requirement.
The only place `alpaca-py`'s direct SDK is used is the offline backtest (pulling historical
bars for research) and a `get_clock()` check in the scheduler loop — no trading action ever
bypasses the MCP layer.

Response parsing lives in `agent/mcp_parsers.py` and `agent/live_chain.py`, both written and
fixed against a live account rather than assumed correct:
- Every MCP tool result is wrapped `{"_alpaca_mcp_security": ..., "data": ...}`, and the
  shape *under* `data` differs per tool (`get_account_info`'s is the account dict directly;
  `get_all_positions`' is `{"result": [...]}`, one level deeper). Getting this wrong doesn't
  error — it silently zeroes out equity/positions, which trips `RiskGate`'s "no account
  snapshot" guard and auto-rejects every order. This bug existed in both `live_agent.py` and
  `deterministic_agent.py` until caught by testing against a real account; both are fixed now.
- `get_option_chain`'s `limit` caps total snapshots returned, and a wide DTE window or a
  dense name (SPY/QQQ, with many weekly expiries) can blow through that cap before ever
  reaching the strikes/expiry you actually need — verified live: an unbounded query for a
  ~$450 stock returned only deep out-of-the-money contracts near $170, and a wide-DTE query
  for SPY returned only expiries 10 days out despite asking for 7-45. `live_chain.py` fixes
  this with a two-pass fetch: discover which expiries exist using a narrow near-the-money
  strike band (cheap), then fetch the chosen expiry's full desired strike range on its own
  (also cheap — one expiry's contracts, not the whole window's).

### 6. Zero-LLM-cost testing path (`agent/deterministic_agent.py`, `agent/skew_strategy.py`)
Two ways to exercise real trading mechanics — data fetch, real-chain strike matching, risk
gates, order placement — without spending anything on the Anthropic API:

- **`python main.py --deterministic`** mechanically trades only symbol/strategy combinations
  that passed backtest validation (`cleared_for_paper` in `logs/backtest_report.json`), no LLM
  involved: it builds the same theoretical legs the backtest validated, matches each to the
  closest real listed contract by delta (preferring Alpaca's own reported greek over a
  re-derived Black-Scholes one), runs the match through the same `RiskGate`, and places the
  order. Run against a real paper account during development; caught and fixed the two bugs
  above plus a strike-matching bug (see Known Limitations).
- **`python record_skew.py`** records a real IV put/call skew observation per symbol
  (Alpaca's own quoted greeks/IV, not a model estimate) to `logs/skew_history.jsonl` and
  computes a mean-reversion signal once enough trailing history exists. It **never places an
  order** and is **not** part of the validated strategy universe above — skew is a property of
  the implied vol surface specifically, and there's no realized-vol proxy for skew the way
  there is for a vol level, so it can't be backtested offline with what this project has. It's
  scaffolding for a genuinely different signal (skew richening/cheapening, not volatility
  level), meant to accumulate real history before anyone trusts it — not something to trade
  during a one-week hackathon window.

### 7. Order & position management (`agent/order_manager.py`)
Every trading path above only ever *opens* positions — none of them close one, cancel a
stale unfilled order, or notice a position drifting toward expiration. That's what this
runs first in every cycle (`--once`, `--loop`, `--deterministic`, or standalone via
`--manage-only`), before any new entry is even considered:
- Cancels stale unfilled orders (`STALE_ORDER_MINUTES`, default 60) — freeing up
  `qty_available` before touching positions, since an existing open order on a symbol blocks
  a new close order on it (verified live: a stale sell-to-close order left a position
  un-closeable until it was canceled first).
- Force-closes any option within `FORCE_CLOSE_DTE` (default 2) days of expiration — universal
  pin-risk/assignment protection regardless of which strategy opened it.
- Closes on a universal stop-loss (`POSITION_STOP_LOSS_PCT`, default 75% unrealized loss) or
  profit-take (`POSITION_PROFIT_TAKE_PCT`, default 50% unrealized gain), read directly from
  Alpaca's own `unrealized_plpc` on the position.
- Always closes with a **marketable limit order**, never `market` — Alpaca rejects market
  orders on thinly-quoted options ("no available quote for symbol, please reenter with a
  limit"), verified live; the limit price is derived from the position's own `current_price`,
  aggressive enough to fill without literally crossing at $0.

Disclosed honestly: these are universal, strategy-agnostic rules, not yet each strategy's own
backtested exit (e.g. `iron_condor_vrp_45_21`'s specific 21-DTE-managed exit + 2×-credit
stop from the backtest engine) — a strategy-aware version would cross-reference
`logs/trade_log.jsonl` to recover which strategy opened each position. Noted as a next step
rather than shipped half-working.

### 8. Self-learning loop (`agent/reflection.py`) — process, not outcome
Every closed position gets a structured post-mortem, deliberately **not** built as "learn from
losses." A strategy with a real, validated edge still loses on a predictable fraction of its
trades — GOOGL `cash_secured_put`'s own backtest win rate is 70%, meaning 30% of *correctly
executed* trades lose money. A naive loop that avoids whatever pattern preceded a loss would
spend its entire learning budget unlearning a real edge based on ordinary variance, directly
contradicting the statistical discipline the rest of this project is built on. So this module
checks two things instead, neither of which is "did this trade make money":

- **Process, not outcome**: did entry actually respect what `RiskGate` is supposed to guarantee
  (backtest-cleared symbol, DTE bounds, position size)? With the hard gates already in place,
  this should be clean by construction — a `[PROCESS FLAG]` means something slipped through or a
  position was opened outside this system, which is the actual signal worth surfacing.
- **Realized-vs-backtested drift** (`strategy_drift_report`): once there's enough live history
  (10+ closed trades for the same strategy/symbol), is the live win rate/return still tracking
  what the backtest predicted, or has the edge stopped working? That comparison — not any single
  trade's result — is the statistically honest version of "is this still working." Reports
  `insufficient_live_trades` honestly below that threshold rather than drawing a conclusion from
  a handful of trades.

The resulting summary (`summarize_for_prompt()`) is injected as plain text into the next cycle's
system prompt across all three LLM paths (`live_agent.py`, `live_agent_openai.py`,
`multi_agent.py`) — informational continuity across cycles, **not** a weight update; no
fine-tuning happens anywhere in this project. Explicitly out of scope and why: fine-tuning an
LLM on a handful of real trades is both infeasible (nowhere near enough data) and the wrong
statistical shape for a strategy with expected variance in its outcomes.

De-duplicates by symbol — verified necessary live: `order_manager.py` resubmits a close order
every cycle a position still qualifies for one, and on a thin/illiquid contract that order can go
unfilled and get resubmitted cycle after cycle, which without the guard logged another "closed"
entry each time for a position that never actually closed.

## Setup

**One command:**

```bash
pip install -r requirements.txt
python setup.py
```

`setup.py` installs any missing dependencies, checks for `uv`/`uvx` (needed to launch
Alpaca's MCP server — no separate install step for the server itself, `uvx alpaca-mcp-server`
fetches and runs it on first use), interactively prompts for your Alpaca keys (and, optionally,
an Anthropic key — leave it blank and `--deterministic` still works at zero LLM cost), writes
`.env`, verifies the Alpaca connection actually works, and runs the backtest so
`logs/backtest_report.json` exists before you ever try to trade. Re-run it any time to update
keys — it preserves what's already set if you just hit enter.

**Important — hackathon eligibility**: create a brand-new Alpaca paper trading account
dedicated to this event (an existing/reused account is not eligible for judging), set its
starting balance to $100,000, and give `setup.py` that account's keys.

<details>
<summary>Manual setup (if you'd rather not run the wizard)</summary>

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in ALPACA_API_KEY / ALPACA_SECRET_KEY / ANTHROPIC_API_KEY
python run_backtest.py
```
</details>

## Running it

```bash
# 1. Backtest + validate every strategy/symbol combination against real historical data
python run_backtest.py

# 2a. Zero-LLM-cost: mechanically trade only backtest-cleared combinations (no Anthropic key needed)
python main.py --deterministic

# 2b. Claude-driven: one research-and-trade cycle (needs ANTHROPIC_API_KEY)
python main.py --once

# 2c. Claude-driven, continuous during market hours, with a hard spend cap
python main.py --loop --interval 30 --max-spend 5.00

# 2d. Two-agent pipeline (Proposer -> Critic -> RiskGate) instead of single-agent — combine
#     with --once/--loop the same way
python main.py --multi-agent --once
python main.py --multi-agent --loop --interval 30 --max-spend 5.00

# Manual kill switch — independent of every other gate, blocks all new orders immediately
python kill_switch.py status
python kill_switch.py on "reason" [--cancel-all]
python kill_switch.py off

# Position/order housekeeping only — no new entries, no Anthropic call. Runs automatically
# first inside every mode above too; this is for running it standalone/on its own schedule.
python main.py --manage-only
python main.py --manage-only --loop --interval 15

# Optional: build up real IV-skew history for agent/skew_strategy.py (never trades)
python record_skew.py
```

All tool calls, risk-gate decisions, cycle summaries, and **per-call Anthropic API cost**
(input/output/cache tokens, computed from real `response.usage`, not estimated) are appended
to `logs/trade_log.jsonl` for the write-up/demo video.

### Anthropic API cost
The Claude-driven path (`--once`/`--loop`) is the only thing that spends anything — Alpaca's
MCP server exposes ~70 tools totaling ~20K tokens of schema, resent on every turn of the
tool-use loop. `agent/live_agent.py` caches the tool list and system prompt (`cache_control`
breakpoints), cutting a research cycle from roughly $0.60-0.80 to a few tens of cents;
`main.py --loop` still enforces a hard `--max-spend` cap (default $5, or `MAX_SESSION_SPEND_USD`
in `.env`) that stops the loop once *measured* spend — not an estimate — hits it.
`--deterministic` and `record_skew.py` make zero Anthropic API calls.

## Configuration

Tunable via environment variables (see `agent/config.py`): `MAX_POSITIONS_OPEN`,
`MAX_ALLOCATION_PCT_PER_TRADE`, `MAX_TOTAL_OPTIONS_ALLOCATION_PCT`,
`DAILY_LOSS_LIMIT_PCT`, `MIN_DTE`, `MAX_DTE`, `MAX_TOOL_CALLS_PER_CYCLE`,
`MAX_SESSION_SPEND_USD`. The watchlist itself is set in `agent/config.py`.

## Known limitations (honest, for the write-up)
- `agent/multi_agent.py` was verified structurally with mocked Anthropic/MCP calls (all three
  outcomes: trade placed, Proposer skips, Critic vetoes — see the module docstring) but never
  run against the real Anthropic API, since no key was available during development. The logic
  is tested; the actual quality of the Critic's judgment on real proposals isn't yet.
- The Critic reviews only what the Proposer reports (its rationale + the data it cites) — it
  doesn't independently re-pull live data via its own tool calls, which keeps cost bounded but
  means a Proposer that misrepresents what it found wouldn't be caught by re-verification, only
  by the Critic's own reasoning about internal consistency.
- The backtest's synthetic path prices theoretical Black-Scholes contracts off historical
  *underlying* prices, not historical bid/ask options chains — a deliberate, disclosed
  approximation for comparing strategy families, since full historical chains for a broad
  watchlist aren't reliably available. `price_iron_condor_real_quotes()` exists for when
  real chain data *is* available (e.g. a live/paper pricing check), but true historical
  backtesting with real quoted fills isn't attempted.
- Day-by-day mark-to-market during the holding period (for the stop-loss check) also uses
  Black-Scholes with the entry-day realized-vol estimate held fixed for the life of the
  trade — a simplification; it doesn't re-estimate vol daily or model vol-surface skew.
- `vertical_credit_spread` and `iron_condor` submit their legs as sequential single-leg
  orders rather than an atomic multi-leg order, so there's a brief window where only some
  legs are filled.
- `covered_call` is only reachable once the account already holds ≥100 shares of a symbol,
  which won't happen organically since this agent never buys shares outright — it's kept
  in the strategy universe (and the backtest) for completeness/future extension.
- `enabled_for_live` in `agent/strategies/lifecycle.py` is wired but nothing currently calls
  `promote_to_live()` — this project only runs against Alpaca's paper environment, as required.
- `iron_condor_vrp_45_21` failed validation on every watchlist symbol (see strategy table
  above) — a disclosed negative result attributed to the realized-vol-vs-real-IV proxy gap,
  not a coding bug, but not re-tried further than one vol-window adjustment.
- `agent/skew_strategy.py` has no offline backtest and is deliberately never wired into
  `cleared_for_paper` — treat any signal it produces as informational, not tradeable, until
  proven out over real accumulated history (20+ observations minimum, and even then untested).
- `_match_leg_to_real_chain` in `deterministic_agent.py` matches by delta only, with no
  liquidity/spread-width filter — a thinly-traded, wide-spread contract can still be "the
  closest delta" on a sparse part of the chain and get matched anyway. Worth adding a
  minimum-open-interest or max-spread-width filter before trusting this further.
