# Social Posts for Submission

*These posts are drafted for X (Twitter) and LinkedIn. They tag @lablabai and @AlpacaHQ (X) and lablab.ai and Alpaca (LinkedIn). For LinkedIn, replace the X handles with the standard mentions when pasting.*

---

## Post 1: Council Attack C01 (The Arbiter)

Our own AI confidently authorized a catastrophic $172,000 order. And our Python risk layer stopped it. 

In our @lablabai hackathon submission, we run a 3-seat council. We deliberately ran Council Attack C01: asking our independent Featherless arbiter model (Qwen2.5-7B-Instruct) to bless a 400-contract trade. It ruled PROCEED, hallucinating that "the position size is acceptable" against a hard $8k cap. 

The deterministic Python risk gate correctly refused it. Execution authority cannot sit in an LLM. It belongs in Python.

#AgenticAI #AlgorithmicTrading #Python #OptionsTrading

---

## Post 2: Adversarial Risk Gate & Counterfactuals

To prove our risk gate works, we ran our agent against itself using an adversarial harness. It found and closed three critical holes: a buy-1/sell-2 ratio exploit, a hallucinated strike, and an active prompt injection in our arbiter model.

Yes, this gate has a cost: it refused strategies that would have returned +$1,326.64 today (15 of 21 refused pairs were profitable). But it refuses on the width of the bootstrap interval, never the sign of the latest observation. Rigor over luck. Built for the @lablabai hackathon.

#CyberSecurity #AI #TradingSystems #AlpacaAPI

---

## Post 3: Statistical Validation & The Bootstrap

Our @AlpacaHQ trading agent evaluated 21 distinct strategy/symbol pairs. The result? Exactly 0 pairs cleared for live trading. 

A SPY vertical credit spread hit a 78% win rate and 1.67 Sharpe, but failed the Sharpe CI lower bound (-0.32). A high win rate on a negatively skewed payoff is a shape parameter, not performance. 

By switching to a moving-block bootstrap, we cut our false-positive rate from 10.8% to 2.5%. Rigor over noise for the @lablabai hackathon.

#QuantFinance #DataScience #Backtesting #MachineLearning

---

## Post 4: Proposer, Critic, and Arbiter

Our @AlpacaHQ agent architecture ensures the LLM never computes a number that reaches an order. 

- **Proposer** researches and builds a trade.
- **Critic** evaluates it against backtest evidence.
- **Arbiter** (an open-weights model) settles disagreements. 

In live testing, the Critic actively vetoed a MSFT cash-secured put for lacking backtest evidence. Total cost per cycle? $0.022. Built for the @lablabai hackathon.

#LLM #MultiAgentSystems #AgenticAI #SystemDesign

---

## Post 5: Structure-Level Risk

Evaluating risk per-leg breaks down in multi-leg options trading. 

Our deterministic risk gate evaluates capital-at-risk at the batch/structure level. Under a per-leg model, our @AlpacaHQ SPY credit spread required $75,500 in capital. Under the corrected batch model, it properly calculated the risk at roughly $420 and cleared the trade.

Undefined risk never reaches the broker. Built for the @lablabai hackathon.

#OptionsTrading #RiskManagement #QuantitativeFinance #FinTech

---

## Post 6: The 100% Divergence Finding

Is agentic AI non-determinism caused by shifting market data? We proved executably that it isn't.

Our replay harness fed 108,012 characters of *frozen* market data to our @AlpacaHQ trading agent. We used `verify_replay_isolation.py` to block DNS for every host except the model provider, confirming zero API re-fetches. 

The result? Evaluating `gpt-4o-mini` (free tool choice, temp=0, fixed seed, byte-identical inputs): 100% of decision turns changed on replay (40 of 40). 

Divergence concentrates exactly where authority sits. The variance is the LLM. Execution authority belongs in deterministic Python. Built for the @lablabai hackathon.

#AgenticAI #MachineLearning #SystemDesign #QuantFinance
