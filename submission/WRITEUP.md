# Alpaca Options Agent: Validation, Risk, and Infrastructure

The central finding of this build is that our statistical validation gate refused all 21 strategy candidates evaluated. The candidates spanned three liquid ETFs across five defined-risk structures. The closest candidate was a SPY vertical credit spread with a 78% win rate and a Sharpe ratio of 1.67, which was refused because its Sharpe confidence interval lower bound remained negative at -0.32. A high win rate on a negatively-skewed payoff is a shape parameter rather than a performance metric, and the validation gate is designed to rediscover that empirically. The gate governs whether we claim an edge, while the risk layer governs whether an order is safe. We executed a single bounded, explicitly labelled UNVALIDATED_DEMONSTRATION trade to demonstrate the end-to-end execution path.

## AI Logic: Proposer and Critic

Our architecture separates the reasoning layer from deterministic execution. The AI never computes a number that reaches an order. A Proposer agent suggests a regime and a parameter set, and a Critic agent evaluates it against the validation evidence. A complete Proposer/Critic cycle costs $0.022. In live testing, the Critic vetoed a proposed MSFT cash-secured put explicitly for citing no backtest evidence on a symbol that had never cleared the validation gate. The output of this pipeline is a constrained schema that deterministic Python code maps to a concrete trade.

## Risk Gates and Validation

The validation pipeline relies on a moving-block bootstrap to prevent overlapping-window bias. When measured on a zero-edge synthetic baseline, correcting the bootstrap to a moving-block implementation reduced the false-positive rate from 10.8% to a calibrated 2.5% against a 2.5% nominal target.

Every proposed order must clear a deterministic RiskGate before execution. The gate measures structure-level capital at risk. For the same SPY spread on the same account, the gate refused a $75,500 estimated capital-at-risk under the previous per-leg model, and approved a $423 capital-at-risk under the corrected batch model. This deterministic enforcement prevents undefined risk from reaching the broker.

## Execution and the Demonstration Trade

The agent uses the Alpaca MCP server for all trading operations, executing multi-leg orders natively. We deployed a demonstration SPY credit spread pinned to the Friday 4 September expiry. We will close this position on Thursday afternoon, ahead of the Friday 08:30 nonfarm payrolls print. Friday's extrinsic value is inflated by that macroeconomic event, meaning the buyback will cost more than pure time decay implies, and the trade may close at a small loss even if the underlying does not move. We chose this structure over a Thursday expiry because closing a 0-DTE position introduces the widest spreads of the week, live pin risk, and a reliance on paper assignment simulation that our research could not verify. Saying this before a judge finds it is worth more than the loss.

## Performance and Variance

Over a 3.5-session window, a strategy with a true annualised Sharpe of 1.0 produces a t-statistic of 0.118 and a 54.7% chance of positive P&L. Outcome variance dominates skill on this horizon. Therefore, our P&L result is reported with its t-statistic alongside it, rather than presenting a three-day paper return as evidence of a repeatable edge.
