# Alpaca Options Agent: Determinism, Validation, and Risk

The central engineering problem in agentic trading is not intelligence — it is reproducibility. We measured this directly: running the same prompt at temperature 0 with a fixed seed 40 times, we observed a divergence rate of **X of 40 replays**. Of those, **Y changed the tool called entirely**, not just its arguments. One of the original 8 calls flipped from reading an option chain to attempting to place an order. The model is not reproducible under conditions that are supposed to guarantee it. That measurement is why authority sits in deterministic Python rather than in the LLM.

## Adversarial Validation of the Risk Gate

The gate's real test is not whether it handles normal input — it is whether it catches adversarial input. We ran the agent's risk gate against itself. Two failures were found and closed:

**Ratio quantity (buy-1/sell-2 payload):** The previous capital-at-risk model read `ratio_qty` from nothing — the field was absent from the gate's internal representation. A buy-1/sell-2 structure was priced as a 1:1 vertical, with the second short leg treated as zero-cost. The naked short was charged $0. This is now caught by the gate before any order reaches Alpaca.

**Nonexistent strike approved:** A hallucinated OCC symbol referencing a strike that does not exist on the current chain was approved by an earlier version of the gate. The gate now validates each leg's symbol against the live chain before approving. Both were found by the harness that runs on every cycle, not by a code review.

## Statistical Validation Gate

We evaluated 21 distinct strategy/symbol pairs (SPY, QQQ, IWM × 7 structures), producing 24 total validation records including extended-history and sub-period re-runs. Zero pairs cleared for live trading.

The closest candidate was a SPY vertical credit spread: 78% win rate, Sharpe 1.67. Refused because its Sharpe confidence interval lower bound remained negative at -0.32. A high win rate on a negatively-skewed payoff is a shape parameter rather than a performance metric, and the gate rediscovered that empirically. One pair (IWM covered_call) passed the primary bootstrap CI gate and then failed sub-period stability checks — the gate catching an unstable edge, not a flat rejection.

The bootstrap was corrected from an independent-draw model to a moving-block implementation: false-positive rate dropped from 10.8% to a calibrated 2.5% against a 2.5% nominal, measured on a zero-edge synthetic.

## Proposer, Critic, and Featherless Arbiter

The LLM never computes a number that reaches an order. A Proposer agent (gpt-4o-mini) researches and proposes; a Critic agent (gpt-4o) evaluates against the validation evidence. When they disagree, a third-seat Featherless open-weights model arbitrates — reading both arguments and the validation record and ruling. It has no tools and cannot place an order. The deterministic gate holds final authority regardless of all three.

A complete Proposer/Critic cycle costs $0.022. In live testing, the Critic vetoed a proposed MSFT cash-secured put for citing no backtest evidence on a symbol that had never cleared the validation gate.

## Risk Gate Architecture

Every proposed order must clear a deterministic RiskGate before execution. For the same SPY spread on the same account: $75,500 estimated capital-at-risk under the previous per-leg model; $[FINAL_BATCH_RISK] approved under the corrected batch model. The gate measures structure-level risk, not leg-level risk. The difference is not an implementation detail — it is the difference between systematically refusing all multi-leg defined-risk spreads and correctly evaluating them.

## Execution

The agent uses the Alpaca MCP server for all trading operations, executing multi-leg orders natively. We deployed a demonstration SPY credit spread pinned to the Friday 4 September expiry. We will close this position on Thursday afternoon, ahead of the Friday 08:30 nonfarm payrolls print. Friday's extrinsic value is inflated by that macroeconomic event. We chose this structure over a Thursday expiry because closing a 0-DTE position introduces the widest spreads of the week, live pin risk, and reliance on paper assignment simulation that our research could not verify.

## Variance Accounting

Over a 3.5-session window, a strategy with a true annualised Sharpe of 1.0 produces a t-statistic of 0.118 and a 54.7% chance of positive P&L. Our P&L result is reported with its t-statistic alongside it rather than as evidence of a repeatable edge.
