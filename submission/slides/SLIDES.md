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

## 1. The Variance Problem

Over a 3.5-session evaluation window, a strategy with a true annualised Sharpe of **1.0** produces:

- A t-statistic of **0.118**
- A **54.7%** chance of positive P&L
- A **45.3%** chance of losing money

**Skill accounts for just 1.4% of outcome variance on this horizon.**

Any 3-day paper P&L figure is statistical noise. We designed a system that acknowledges this and survives the variance by validating first.

---

## 2. Statistical Validation Gate

We evaluated 21 candidate strategies (SPY, QQQ, IWM × 7 structures).

- **All 21 candidates were refused.**
- The closest: SPY vertical credit spread (78% win rate, Sharpe 1.67).
- Refused because the Sharpe CI lower bound remained negative (-0.32).

**Moving-block bootstrap:**
We corrected our bootstrap from an independent-draw model to a moving-block model, cutting the false-positive rate from **10.8%** to a calibrated **2.5%**.

---

## 3. The Proposer / Critic Architecture

The LLM never computes a number that reaches an order.

- **Proposer Agent:** Suggests regime and parameters.
- **Critic Agent:** Evaluates the proposal against our validation graveyard.

**Live Veto:** The Critic agent actively vetoed a proposed MSFT cash-secured put for citing no backtest evidence on a symbol that never cleared the gate.

**Cost:** $0.022 per Proposer/Critic cycle.

---

## 4. Deterministic Risk Gate

Every order must pass a non-LLM Python risk gate before routing to the Alpaca MCP server.

- We implemented a batch model for structure-level capital at risk.
- **Old per-leg model:** Refused $75,500 capital-at-risk for a SPY spread.
- **New batch model:** Correctly calculated $423 risk and approved the trade.

**Enforcement:** Prevents undefined risk from reaching the broker.

---

## 5. The Demonstration Trade

Because the gate governs claims of edge, not structural safety, we executed **one** unvalidated demonstration trade.

- **Structure:** SPY defined-risk credit spread.
- **Expiry:** Friday, September 4th.
- **Exit Plan:** Closing Thursday afternoon.

Holding through Friday's nonfarm payrolls print means inflated extrinsic value and live pin risk. Managing risk is worth more than hoping for decay.

---

# Thank You
Code public. Paper Account ID submitted.
*Options quotes provided by Alpaca's free-tier Indicative Pricing Feed.*
