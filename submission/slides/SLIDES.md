---
marp: true
theme: default
class: invert
style: |
  section {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  h1, h2, h3 {
    color: #3b82f6;
  }
  .accent {
    color: #ef4444;
  }
---

# Alpaca Options Agent
## Deterministic Risk & Statistical Validation
*An architecture that refuses bad trades.*

---

## 1. The Determinism Problem

The central problem in agentic trading is not intelligence — it is reproducibility. 

We ran the agent 40 times on the same prompt at temperature 0 with a fixed seed. 
- **High Divergence:** A significant number of replays diverged despite fixed parameters.
- **Tool Flips:** Replays changed the *tool called entirely*, not just arguments. One original call flipped from reading an option chain to attempting an order.

**Conclusion:** The model is not reproducible under conditions meant to guarantee it. Authority must sit in deterministic Python, not the LLM.

---

## 2. Adversarial Validation of the Risk Gate

We ran the agent's risk gate against itself to prove it works under adversarial conditions. Two critical holes were found and closed:

1. **Ratio Quantity Exploit:** A buy-1/sell-2 payload was previously priced as a 1:1 vertical (second short leg treated as zero-cost). The gate now correctly parses and stops this.
2. **Hallucinated Strikes:** The gate previously approved a hallucinated OCC symbol with a non-existent strike. It now validates every leg against the live chain.

Both were found by the agent attacking itself.

---

## 3. Statistical Validation Gate

We evaluated 21 distinct strategy/symbol pairs (SPY, QQQ, IWM × 7 structures), producing 24 total validation records.

- **0 pairs cleared for live trading.**
- The closest: SPY vertical credit spread (78% win rate, Sharpe 1.67). Refused because the Sharpe CI lower bound remained negative (-0.32).
- **Moving-block bootstrap:** Correcting from an i.i.d. bootstrap to a moving-block model cut the false-positive rate from **10.8%** to a calibrated **2.5%**.

The gate governs claims of edge. The risk layer governs structural safety.

---

## 4. The Proposer / Critic Architecture

The LLM never computes a number that reaches an order.

- **Proposer Agent:** Suggests regime and parameters.
- **Critic Agent:** Evaluates the proposal against our validation graveyard.
- **Featherless Arbiter:** A third open-weights model arbitrates disagreements.

**Live Veto:** The Critic agent actively vetoed a proposed MSFT cash-secured put for citing no backtest evidence on a symbol that never cleared the gate.

**Cost:** $0.022 per Proposer/Critic cycle.

---

## 5. Deterministic Risk Gate & Execution

Every order must pass the non-LLM Python risk gate before routing to the Alpaca MCP server.

- We implemented a batch model for structure-level capital at risk.
- **Old per-leg model:** Refused $75,500 capital-at-risk for a SPY spread.
- **New batch model:** Correctly calculated $[FINAL_BATCH_RISK] risk and approved the trade.

**Demonstration Trade:** We executed **one** unvalidated SPY credit spread pinned to the Friday Sept 4th expiry, explicitly bypassing validation to demonstrate the execution path. We close Thursday to avoid Friday's NFP event risk.

---

# Thank You
Code public.
*Options quotes provided by Alpaca's free-tier Indicative Pricing Feed.*
