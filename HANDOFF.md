# Handoff Notes — Alpaca Options Trading Agent

Written for whoever picks this up next. Covers what's built, why it's built that way, whether
that was the right call, what's actually wrong with it right now, and what to do about it.
Repo: https://github.com/Sairishwanth89/alpaca_software

## 1. What this is

An autonomous options-trading agent for Alpaca's paper environment, built for lablab.ai's
"Alpaca AI Trading Agents Hackathon." Core hackathon rules: must be an autonomous agent using
Alpaca's Trading API, must use Alpaca's MCP server or CLI, must trade options, competition
account must start at exactly $100,000 (fixed, not adjustable), and a fresh dedicated paper
account is required for judging — **the account currently wired up is not fresh, it has test
trades on it. Create a new one before final submission.**

Judging is 5 weighted criteria: P&L Performance, Technology Implementation, Creativity &
Originality, Presentation & Execution, Social engagement — not pure profit.

## 2. What's built, and why, module by module

### 2a. The core idea: don't trust a strategy until it's proven

The single organizing principle of this codebase: **nothing gets traded because an LLM thinks
it's a good idea.** Every strategy has to survive a statistical gate first
(`agent/backtest/metrics.py`, `agent/backtest/engine.py`), and only what survives is ever
presented to the live agent as tradeable. This is the right call for a hackathon judged partly
on "Technology Implementation" — most competing submissions will be an LLM with tool access and
a prompt; a real validation layer is a genuine differentiator, and it's also just correct
practice for anything that touches real capital, paper or not.

The gate (`validate_strategy_result` in `metrics.py`):
- At least 30 simulated trades (guards against small-sample noise).
- A bootstrap confidence interval whose **lower bound** excludes zero for **both** mean return
  and Sharpe — not just "doesn't straddle zero" (a strategy with a CI entirely below zero is a
  confirmed loser, not a pass, even though it also "excludes zero").
- Anything that passes gets automatically retested on a much longer lookback window
  (`EXTENDED_LOOKBACK_DAYS`), and demoted if it doesn't hold up — this caught a real case: a
  commodity-style calendar spread strategy that looked good on a short window reversed to a
  clear fail on extended history, which is exactly the overfitting pattern this exists to catch.
- Later strengthened further with a **sub-period stability** check
  (`validate_sub_period_stability`): the extended-history trades get split chronologically in
  half, and *both* halves have to individually pass, not just the combined sample. This is what
  demoted the original headline strategy (see §4).

Every validated (or rejected) result gets written to `docs/strategy_graveyard.md` with real
numbers — pass or fail — so a falsified idea is documented, not silently deleted, and doesn't
get re-tested from scratch by mistake later.

**Is this the right way to do it?** Yes, I'd defend this as the correct default for a trading
system, hackathon or not. The mistake most people make with a "let the AI decide" trading demo
is skipping exactly this step. Where I'd push back on my own design: see §4, because the
backtest engine itself has real, newly-discovered bugs that undermine some of what this gate
was supposed to guarantee.

### 2b. Two ways to reason about a trade: single-agent and Proposer/Critic

`agent/live_agent.py` (Anthropic) and `agent/live_agent_openai.py` (OpenAI, structurally
identical, different SDK) give an LLM Alpaca's real MCP tools and let it research + decide +
execute in one tool-use loop. `agent/multi_agent.py` splits this into two roles: a **Proposer**
whose tool list has every order-placing tool *removed* (it is structurally incapable of trading,
only of calling a local `propose_trade` tool), and an independent, adversarially-prompted
**Critic** that can veto the proposal before anything reaches the deterministic risk gate.

**Why built this way:** the single-agent version is the obvious, first-thing-anyone-builds
approach — necessary but not differentiated. The Proposer/Critic split is a genuine second
opinion with actual privilege separation (not just "ask the same model twice"), and it directly
answers a real self-criticism: the core trading *reasoning* here is fairly conventional
(read data, pick from an enumerated strategy list) — the two-agent structure is one of the few
places the LLM does something a rules engine couldn't cheaply replicate.

**Is this the right way?** The Critic reviews only what the Proposer *reports* — it doesn't
independently re-fetch live data to check the Proposer isn't misrepresenting what it saw. That's
a real, disclosed gap, not an oversight: giving the Critic its own tool loop would double the
research cost for a check that's really about internal-consistency and evidence-citation, not
data re-verification. Reasonable tradeoff, worth knowing about.

### 2c. Zero-cost deterministic execution — for testing, not for the actual entry

`agent/deterministic_agent.py` mechanically trades only symbol/strategy combinations that
already cleared the statistical gate — no LLM call anywhere. Built specifically so the trading
*mechanics* (real-chain strike matching, risk gates, order placement) could be tested for free
before spending anything on the LLM paths. It caught several real bugs this way (see §5) at
zero cost, which is exactly what it was for.

**Is this the right way?** Yes for testing. It should **not** be the primary way this system
presents itself for judging, though — the hackathon explicitly wants an *AI* trading agent, and
a purely rule-following executor doesn't showcase that, even though the statistical machinery
behind it is a real technology asset either way.

### 2d. Order & position management, kill switch, guardrails

Every trading path only ever *opens* positions. `agent/order_manager.py` is what closes the
loop: cancels stale unfilled orders, force-closes anything within `FORCE_CLOSE_DTE` days of
expiration (pin-risk protection), and applies a universal stop-loss/profit-take off Alpaca's own
reported unrealized P&L. Runs first, automatically, in every cycle.

`agent/kill_switch.py` — a manual, independent-of-everything-else lever
(`python kill_switch.py on/off/status`) that blocks all new orders and optionally cancels
everything open, checked both inside the risk gate and at the top of every agent's cycle (so a
killed session doesn't even spend money researching).

`agent/risk/gates.py` (`RiskGate`) is the actual enforcement point every order-placing call goes
through: position-count limit, per-trade and portfolio-wide capital caps (percentage *and*
optional absolute-dollar, whichever is stricter), DTE bounds parsed from the real OCC symbol
(never trusting the LLM's arithmetic), naked-call protection, a daily-loss circuit breaker
correctly anchored to Alpaca's own `last_equity` field (not local state that could reset), and —
added after a live OpenAI-driven test trade proved it was necessary — a hard block on trading
any symbol with no backtest-cleared strategy. That last one matters: "prefer validated
strategies" was originally only prompt text, and a cheaper model traded an unvalidated symbol
(NVDA) on its very first real run. It's a code-level gate now, not a suggestion.

**Is this the right way?** Yes, and this is probably the second-strongest part of the codebase
after the validation gate. But §5 has real, serious bugs found in this exact layer — the design
intent is right, the implementation has gaps.

### 2e. Self-learning loop — deliberately not fine-tuning

`agent/reflection.py` logs a structured post-mortem on every closed position, checking two
things, neither of which is "did this trade make money": (1) process integrity — did entry
respect what the risk gate is supposed to guarantee; (2) once enough live history exists,
realized-vs-backtested drift. The summary feeds into the next cycle's prompt as plain context —
never a weight update.

**Why not fine-tune:** two reasons, both real. Not enough data (a handful of real trades total),
and more importantly, a strategy with a genuine edge still loses a predictable fraction of the
time (the account's one validated strategy at one point had a 70% backtest win rate — 30% of
*correctly executed* trades were still expected to lose). A naive "avoid what led to a loss"
loop would spend its whole learning budget unlearning real edge based on ordinary variance. This
is the right call — don't undo it in the name of "making the learning loop do more."

### 2f. Everything else worth knowing about

- **Prompt caching + real cost tracking** (`agent/llm_cost.py`, `agent/openai_cost.py`): every
  API call's actual dollar cost is computed from real token usage, not estimated, and `--loop`
  enforces a hard `--max-spend` cap that stops the session once *measured* spend hits it.
- **`agent/skew_strategy.py`**: IV put/call skew observation, deliberately live-only and never
  wired into the validated strategy set — skew can't be backtested with what this project has
  (no historical options chains), so it only accumulates real observations and never trades.
- **`setup.py`**: one-command onboarding — installs deps, checks for `uv`/`uvx`, collects keys
  interactively, verifies connectivity, runs the backtest. This is the only manual step a new
  user should need.
- **MCP-only execution**: every trading/data operation goes through Alpaca's official MCP server
  (`agent/mcp/client.py`, spawned via `uvx alpaca-mcp-server`), satisfying the hackathon's
  MCP/CLI requirement. `alpaca-py` (the direct SDK) is used only for offline backtest data pulls
  and a market-clock check — never for a trading action.

## 3. Honest overall assessment

**Technology Implementation:** genuinely strong — the validation methodology, the multi-agent
architecture, the guardrail layer, and (see §5) the fact that testing this against a real
account kept finding and fixing real bugs rather than assuming things worked, are all real
substance for the write-up.

**Creativity:** honestly middling. The actual trading *logic* an LLM reasons over is
conventional — pick from a fixed strategy list based on data it read. The creativity in this
project is almost entirely in the governance layer around the AI (validation gate, adversarial
critic, zero-cost testing mode), not in a novel signal or a new kind of reasoning. Said this to
the user directly earlier and it's still true.

**P&L Performance risk:** thin, and it's a real tension, not a false modesty thing. The
validation gate is strict on purpose, which means the account trades rarely — good statistics,
unexciting demo. As of this writing only one strategy/symbol combination has ever cleared the
full gate, and see §4 for why even that's now in question.

## 4. The current strategy situation — read this carefully

Over the course of this build:
- **AMD `long_directional`** was the first strategy to clear the full gate (Sharpe 2.39, 6-year
  extended history). Stress-testing it (parameter sensitivity, cost sensitivity, chronological
  sub-period split) found the edge was **concentrated in the second half of its 6-year window**
  — the first half alone didn't clear the bar (Sharpe 0.99). That's exactly the instability
  pattern that shouldn't be trusted, so the validation gate was strengthened
  (`validate_sub_period_stability`) to require both halves to individually pass, and AMD was
  correctly demoted under the new stricter rule.
- Widening the watchlist from 8 to 18 symbols under the new stricter gate found
  **GOOGL `cash_secured_put`** — Sharpe 3.47, 70% win rate, both sub-period halves pass, much
  smaller max drawdown than AMD ever had (~4% of account vs ~18%). This became the new (and, as
  of the last full backtest run, only) validated strategy.
- **A newly-completed review of the backtest engine itself (§5) found that `covered_call` is
  simulated as a naked short call, not a real covered position** — the simulator has no code
  path for a stock leg at all, verified by literally running the code: over a synthetic -17%
  decline, the true covered-call P&L was -$1,150 while the simulator scored it +$1,915 with a
  passing Sharpe of 2.33. GOOGL's cleared strategy is `cash_secured_put`, not `covered_call`, so
  it isn't directly hit by this specific bug — **but the same review also found the bootstrap
  gate itself resamples overlapping trade windows as if they were independent, empirically
  measuring a ~14% false-positive rate against a ~2.5% nominal rate on a zero-edge synthetic
  strategy.** That finding *does* apply to every strategy validated by this engine, GOOGL
  included. Bottom line: **re-validate GOOGL cash_secured_put's result after fixing the issues in
  §5 before trusting it as the account's one live strategy.** It may well still hold up — it's a
  much more conservative, higher-win-rate strategy than AMD ever was — but it hasn't been
  re-checked against a corrected engine yet.

## 5. Known bugs and limitations, prioritized — this is the real "what to fix" list

Four independent fresh-eyes reviews ran against this codebase (dead code, general
cleanup/reuse, the risk-management path, the Alpaca MCP data-retrieval layer), plus a fifth
against the backtest statistical engine specifically. Some fixes from the first four were
already being applied to the working tree as this document was written — **check `git status`
and `git diff` against what's described below before assuming a given item is still open**, the
descriptions here are what was true as of the reviews completing, not necessarily current disk
state.

### Safety/correctness-critical

1. **`covered_call` is scored as a naked short call in the backtest** — no stock-leg modeling
   anywhere in `agent/backtest/simulator.py`. Empirically verified wrong-sign P&L in a decline
   scenario. Fix requires adding a stock-position leg type the simulator actually understands.
2. **Overlapping trade windows resampled as i.i.d. in the bootstrap** — `STEP_DAYS=7` with
   `HOLD_DAYS=21` means ~67% overlap between consecutive trades, all from one price path; the
   bootstrap treats them as independent draws. Empirically measured ~14% false-positive rate vs
   ~2.5% nominal. This is the single most important finding for trusting *any* validated
   strategy's numbers — it affects every strategy the engine has ever passed, not just one.
3. **`enabled_for_paper` is set *before* the extended-retest/sub-period checks run**, only
   walked back by a `demote()` call — and the whole per-symbol block is wrapped in a bare
   `except Exception` with no rollback, so a transient failure (e.g. a flaky network fetch
   during the extended retest) can leave a strategy marked cleared without ever having actually
   passed the stricter checks.
4. **`place_option_order`'s result was never checked for success anywhere** — an order/close
   was logged and alerted as successful even when Alpaca actually rejected it. This directly
   undermines the buy-before-sell leg-ordering fix meant to prevent naked exposure on a partial
   multi-leg fill: if the *first* (protective) leg is outright rejected, not just unfilled, the
   code had no way of knowing and would submit the risk leg anyway. Per the disk-state notes
   above, fixes for this were actively being applied (`parse_order_error` in
   `agent/mcp_parsers.py`, wired into `order_manager.py`/`live_agent_openai.py`) — verify this
   landed everywhere it needs to (`live_agent.py`, `multi_agent.py`, `deterministic_agent.py`
   too) before trusting it's fully closed. One specific gap flagged directly by a reviewer:
   `cancel_order_by_id`'s result is still unchecked even after the other fixes landed.
5. **The portfolio-wide capital cap isn't cumulative across cycles** — `RiskGate` is rebuilt
   fresh every cycle, and its "capital committed" tracker only ever reflects *that cycle's* new
   approvals, never what's already open from previous cycles. Run `--loop` for a while and there
   is effectively no real ceiling on cumulative capital at risk from this specific gate — only
   Alpaca's own buying-power rejection backstops it.
6. **`iron_condor` and `covered_call` are structurally unable to execute live at all.** The
   naked-call gate requires 100 owned shares to sell a call; `place_stock_order` is always
   rejected, so there's no legitimate path to ever own those shares. Every iron condor attempt's
   short-call leg gets silently rejected, killing the whole 4-leg trade — logged as an ordinary
   rejection, not surfaced as the design conflict it is. Both strategies are presented to the
   agent as valid, tradeable options and simply can never fire.
7. **`qty` was never validated as positive** in `RiskGate.check()` — a negative quantity
   (reachable via the LLM-controlled `live_agent.py`/`multi_agent.py` paths, not via
   `deterministic_agent.py` which hardcodes qty=1) bypasses the naked-call check and can deflate
   the cycle's committed-capital tracker, opening room for a later oversized trade.
8. **ATR-derived stop-loss is computed once from the most recent bars of whichever window was
   fetched and applied uniformly to every trade in that window**, including trades from years
   earlier in the same backtest — and the extended retest reuses the same stale value rather
   than recomputing its own ATR.

### Real but lower-severity

9. Position-count and naked-call-cover checks use a stale, mis-keyed snapshot
   (`open_positions` keyed by full OCC option symbol, not the underlying root) — can both
   over-count a single multi-leg spread as several "positions" and fail to recognize existing
   options-only exposure on a symbol as "already held."
10. `committed_this_cycle` has no rollback when a multi-leg batch aborts partway through.
11. `CONFIG.watchlist` has no hard code-level enforcement — only prompt text plus the separately
    togglable backtest-validation gate.
12. `profit_target_pct` is fully implemented in the simulator but never actually passed by
    either backtest driver — every validated strategy's numbers reflect hold-to-stop-or-expiration
    only, not early profit-taking, even for strategies where that's standard practice.
13. `covered_call`'s `max_loss_per_contract` doesn't net out the premium collected (minor,
    conservative-direction — makes the strategy look slightly worse than it is, not better).
14. A meaningful amount of duplicated logic: the Alpaca response-envelope unwrap was
    hand-copied roughly ten times across five files instead of using the shared
    `agent/mcp_parsers.py` module consistently; per-strategy dispatch is hand-rolled in three
    separate places while an unused `StrategyRegistry` abstraction sits there for exactly this;
    no use of `asyncio.gather` anywhere despite several places awaiting independent MCP calls
    sequentially.
15. Several genuinely dead functions/classes (`strategy_drift_report`,
    `price_iron_condor_real_quotes`, `ContractQuote`, `STRATEGY_FUNCS`,
    `StrategyRegistry.all()`/`.enabled_for_live()`) and a few unused imports — safe to remove,
    no behavior change.

### Explicitly disclosed design limitations (not bugs, known tradeoffs)

- The synthetic backtest path prices off historical *underlying* prices with Black-Scholes, not
  real historical bid/ask option chains — disclosed from the start, since full historical chains
  aren't reliably available for a broad watchlist.
- Multi-leg strategies submit legs sequentially, not as an atomic order — a fill-timing gap is
  possible even with the buy-before-sell ordering fix (see bug #4 above for why that fix isn't
  sufficient on its own).
- The order manager's exit rules are universal/strategy-agnostic, not each strategy's own
  specific backtested exit (e.g. the VRP iron condor's 21-DTE managed exit) — noted as a next
  step from the start, not attempted.
- The bootstrap CI fundamentally cannot represent tail risk that didn't occur in the sampled
  history — a methodological ceiling on the whole validation approach for short-premium
  strategies, not fixable by more bootstrap iterations.

## 6. What to actually do next, in order

1. **Read `git status`/`git diff` right now** to see exactly what's already been fixed vs. what
   in §5 is still open — an autonomous review/fix process was active while this doc was being
   written, so the disk state may be ahead of this document by the time you read it.
2. **Fix or at least re-run validation after fixing #1 and #2 in §5** (the covered-call
   naked-simulation bug and the overlapping-window bootstrap bias) before trusting any strategy's
   numbers, GOOGL included — these two affect the credibility of every "PASS" this engine has
   ever produced.
3. **Fix #6** (iron_condor/covered_call structurally untradeable) or explicitly drop those two
   strategies from the presented strategy universe until it's fixed — right now the system tells
   an LLM these are valid choices and then silently fails every time either is attempted.
4. **Get a genuinely fresh Alpaca paper account** before final submission — the current one has
   test trades on it and won't be eligible for judging per the rules.
5. **Run the Claude-driven or OpenAI-driven agent live at least once**, budgeted — as of the
   last check, real autonomous LLM-driven trading activity in the account was still minimal;
   the demo/write-up needs to be able to show the agent actually deciding something, not just
   the deterministic path.
6. **Submission materials** (video, 1-page write-up, slides) — as of this doc, entirely undone,
   and required for judging regardless of how much further engineering happens.
7. If there's time after the above: the lower-severity items in §5, and the dead-code cleanup
   (safe, mechanical, low-risk to do last).

## 7. Setup, quick reference

```bash
pip install -r requirements.txt
python setup.py                        # one-command interactive setup + connectivity check + backtest
python main.py --deterministic         # zero-LLM-cost test path
python main.py --once                  # single Claude-driven cycle
python main.py --once --provider openai
python main.py --multi-agent --once    # Proposer/Critic pipeline (Anthropic only)
python kill_switch.py status           # manual kill switch
python main.py --manage-only           # position/order housekeeping only
python run_backtest.py                 # re-run the statistical validation gate
```
