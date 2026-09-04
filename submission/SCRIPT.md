# Video Presentation Script: Alpaca Options Agent

**Target Length:** 4 minutes 30 seconds
**Tone:** Direct, engineering-focused, authoritative. No hype. Read by a human on camera.

---

## 0:00 - 0:30 | The Problem (30 seconds)

**[Visual: Speaker on camera, plain background or home office. No green screen.]**

**Speaker:**
"Hi, I'm Abhi. The central problem in agentic options trading isn't generating signals—it's execution, state management, and structural risk. When an LLM sizes a trade, the output isn't deterministic. The variance over a three-day window means any raw P&L number we generate this week is statistical noise. 

So instead of building a prompt that guesses strikes, we built a deterministic risk gate that enforces safety, and a Proposer/Critic pipeline that has to prove an edge before it's allowed to touch the Alpaca MCP server."

## 0:30 - 1:45 | The Arbiter & Council Attack C01 (75 seconds)

**[Visual: Screen recording. Terminal on the left running the agent, browser on the right showing the Risk Gate dashboard.]**

**Speaker:**
"Here is the agent running live. Our pipeline uses a Proposer, a Critic, and an independent third-seat Arbiter running on Featherless.

We ran an adversarial attack we call C01. We asked the Arbiter—a Qwen 2.5 7B model—to bless a 400-contract order. 

The Arbiter confidently ruled 'PROCEED', rationalizing: 'The strategy is validated and the position size is acceptable.' This was completely false. The trade put $172,000 at risk against a hard $8,000 cap. 

But the order never reached Alpaca. Our deterministic Python Risk Gate caught the LLM hallucination and blocked it. This is the thesis demonstrated instead of asserted: you can have a third-party AI confidently authorize a catastrophic trade, and your deterministic Python layer must be the thing that stops it."

## 1:45 - 2:45 | The Validation Finding (60 seconds)

**[Visual: Switch screen recording to the Validation Graveyard section of the UI. Scroll slowly through the 21 FAIL entries.]**

**Speaker:**
"Our validation gate ran a moving-block bootstrap against 21 distinct strategy/symbol pairs. 

It generated 24 total validation records including extended-history and sub-period re-runs. 

0 pairs cleared for live trading. 

The closest was a SPY vertical credit spread. It had a 78% win rate and a simulated Sharpe of 1.67. But the gate refused it because the lower bound of its Sharpe confidence interval remained negative. A high win rate on a negatively-skewed payoff is a shape parameter, not a performance metric. 

When we corrected our bootstrap from an independent-draw model to a moving-block model, the false-positive rate dropped from 10.8% down to 2.5%. The gate works. And it told us we have no statistical edge."

## 2:45 - 3:45 | What That Means & The Demonstration Trade (60 seconds)

**[Visual: Transition to the Alpaca CLI or dashboard showing the single SPY spread order.]**

**Speaker:**
"Because the gate governs whether we can claim an edge, and not whether an order is structurally safe, we authorized exactly one explicitly labelled unvalidated demonstration trade. 

We used the Alpaca MCP server to natively route a defined-risk SPY credit spread pinned to the Friday, September 4th expiry. 

We are deliberately closing this position on Thursday afternoon, ahead of Friday's nonfarm payrolls print. Holding through Friday means facing inflated extrinsic value and live pin risk on a zero-DTE options expiration—relying on paper assignment simulations that our research couldn't verify. We are taking the early exit because managing risk is worth more than hoping for decay."

## 3:45 - 4:30 | Conclusion (45 seconds)

**[Visual: Back to speaker on camera.]**

**Speaker:**
"We also fixed the multi-leg capital risk model. A per-leg calculation would have required [FINAL_PER_LEG_RISK] in estimated capital-at-risk for this SPY spread. Our batch model correctly calculated the structure-level risk at [FINAL_BATCH_RISK], which allowed the MCP order to clear.

Over a three-and-a-half session window, outcome variance dominates skill. Even a genuinely elite strategy loses money over this window more than a third of the time. We built a system that survives that variance by saying no.

Thank you to Alpaca and lablab for the infrastructure. The code is public."
