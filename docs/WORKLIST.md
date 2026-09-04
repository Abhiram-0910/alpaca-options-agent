# WORKLIST.md — everything the research says to fix, build, or check

Derived from `MERGED-hostile-review.md`, `MERGED-alpaca-hackathon-survey.md`,
`MERGED-portfolio-evaluation.md`. Corroboration counts are out of 5 for the hostile review
and portfolio set, out of 4 for the competitor survey.

**Nothing here requires a live market.** The session is over and P&L is locked at +$8.90.
Every item below runs offline against data already on disk. A validation gate whose verdict
changes when its statistics are corrected is a better story than one that never moved.

---

## TIER 0 — could invalidate the headline. Do first.

### 0.1 Does the replay harness re-fetch tool results? `[5/5]`

Every hostile reviewer names this as the dominant confound and none could check it. If the
harness re-fetches quotes, IV or account state rather than replaying cached values, the 70%
divergence measures **market data drift, not model non-determinism**, and the entry's
central claim collapses.

Check: read the replay path in `agent/`. Does it hydrate tool results from
`logs/llm_calls.jsonl`, or does it call MCP again? If it re-fetches, freeze all tool
outputs as static fixtures and re-run with no network. Report the before/after.

### 0.2 The 70% pools three serving stacks `[1/5 — only report A noticed]`

gpt-4o-mini, gpt-4o and Qwen2.5-7B-via-Featherless are three different inference engines
with three different non-determinism mechanisms. A pooled figure across them is not
interpretable as one claim. **Report per-model divergence rates separately**, then decide
whether a combined number is defensible at all.

### 0.3 The 70% contradicts our own 17-identical-proposals finding `[1/5 — report A]`

If per-call divergence is ~70%, seventeen byte-identical proposals in a row is surprising
and needs explaining rather than noting. We hold both datasets. Likely resolution:
divergence concentrates in long multi-tool conversations and is near-zero in short
single-turn ones — which is a **sharper and more useful finding** than the raw 70%.
Measure divergence against conversation length and tool-call count.

### 0.4 Which direction does the simulation bias the result? `[4 vs 1 — unresolved]`

Four reviewers say Black-Scholes-on-underlying-history marks **flatter** short premium
(illusory edge). One says the opposite: marking with historical vol strips out the variance
risk premium that is the entire economic rationale for credit spreads, so we may be
**understating** edge — and fixing it could flip the 21/21 headline. Both invoke the same
fact and derive opposite conclusions. Neither engages the other.

**Checkable in about an hour and nobody has done it.** Pull today's real SPY option chain,
construct the same spreads the simulator would have built, and compare the credit our model
assigns against the actual market credit. Simulated credits systematically higher → the
majority is right. Lower → the dissenter is. This determines whether "21/21 failed" is a
finding about strategies or an artefact of the simulator.

---

## TIER 1 — statistically wrong, cheaply fixable

### 1.1 Percentile bootstrap on a negatively-skewed payoff `[5/5 — most corroborated claim in the set]`

Percentile intervals are first-order accurate and fail under skew. Our payoff is skewed by
construction. Reviewers split on the replacement — BCa (`scipy.stats.bootstrap`,
`method="BCa"`) versus studentized bootstrap-t — so **run both and report the difference**.

One reviewer flags something worth taking seriously: our measured 2.5% against a 2.5%
nominal is *suspiciously good* for a percentile bootstrap on skewed data, and may indicate
undercoverage rather than calibration. Re-measure the zero-edge false-positive rate under
each method.

Two reviewers expect 21/21 to survive the correction "for the right reason." One expects
the current calibration figure itself to prove wrong.

### 1.2 No multiple-testing correction across 21 pairs `[5/5]`

We ran 21 trials with no family-wise or false-discovery control. Named fixes: Deflated
Sharpe Ratio (Bailey & López de Prado 2014), Holm, or Benjamini-Hochberg. One reviewer
cites Harvey/Liu/Zhu 2016 requiring t > 3.0 rather than 1.96 for a single backtest —
single-source and unsourced, treat as a pointer not a rule.

This **raises** our bar, so the 21/21 result gets stronger. One reviewer's framing worth
stealing: every Proposer variation is a new statistical trial, so the trial count should
include LLM-generated proposals, not just backtested pairs.

### 1.3 Mean-CI + Sharpe-CI double gate `[5/5 that it's a problem, 3 positions on why]`

Three reviewers: redundant, inflates Type II error. One: "the Sharpe CI excludes zero if
and only if the mean CI does" — overstated, and denied by two others. One: not double
counting but an unprincipled intersection-union test whose **true size is unknown**. One:
correlated but distinct, adding unmeasured conservatism consistent with our 21/21.

**The resolution nobody performed:** log both bootstrap decisions across all 21 runs and
report their empirical correlation. ~20 lines, and it settles a dispute five reports
couldn't. Do that before changing the gate.

### 1.4 Sub-period stability check `[5/5 flagged, direction contradicted]`

One reviewer computes a 14% family-wise false-negative rate from requiring three
sub-periods to each clear at 95% (1 − 0.95³) — single-source, unsourced, checkable
arithmetic. Another says it invites overfitting in the opposite direction. One says it's
legitimate **if pre-specified** and needs no code change, only discipline.

Action: state in writing whether the sub-period boundaries were pre-specified or chosen
after seeing the data. If chosen after, say so — that's data snooping and admitting it is
worth more than hiding it. Consider demoting it from a binary gate to a reported stability
metric.

### 1.5 Float vs Decimal in capital-at-risk `[1/5, concrete]`

`(width − credit) × 100 × qty` in Python float accumulates rounding error. A $0.01 error
on 400 contracts is $400. Convert the capital path to `Decimal`.

---

## TIER 2 — the experiment that would make the entry unarguable

### 2.1 The control arm `[1/5 — report A, and it is the best idea in all three documents]`

Run the RiskGate and validation gate against a **dumb rules-based proposer** over the same
period and compare the trade record to the LLM council's.

- No difference → we have proved the council contributes nothing, and saying so ourselves
  with data is far stronger than a judge suspecting it.
- Difference → we have measured the LLM's actual contribution, which nobody in the field
  has done.

Both paths already share the gate. A rules proposer picking by IV rank and delta is ~80
lines. Either outcome is publishable; neither is available to any competitor.

One reviewer's qualification to preserve: none of our data distinguishes "the council
contributes nothing" from "the council contributes nothing **in this narrow,
heavily-schema-constrained decision**." Say the narrower thing.

### 2.2 Extract the determinism finding into a standalone repo `[portfolio set, ranked #1 or #2 by 4 of 5]`

Not renamed, not buried in the trading agent. A separate artifact containing:
- a one-command reproduction script
- released raw outputs (JSONL)
- exact model versions, seeds, `system_fingerprint`, hardware/batch disclosure
- a stated limitations and scope section
- a written methodology separate from the README

Five of five agree on those as what makes a measurement citable. One notes the actual
signature of credibility is *someone else building on your released artifact and reporting
a number that improves on yours*.

The hackathon submission stays a trading agent. The portfolio piece becomes a measurement
about LLM determinism. Different audiences; the second is what a Google or NVIDIA reviewer
engages with.

**Rejected alternative:** one reviewer recommends renaming the whole project to a
"determinism auditing framework." Extraction is better — it keeps both stories intact.

### 2.3 Document the divergence metric itself `[1/5]`

"Was it Levenshtein? Exact JSON equality? Semantic equivalence? If you eyeballed it, it's
an anecdote. If you measured it, it's a finding."

Reviewers contradict each other on which comparison is correct — one prescribes exact JSON
equality, one prescribes semantic equivalence, one prescribes token-by-token. **Report more
than one** and say which is the headline.

---

## TIER 3 — real gaps a judge or reviewer will find

### 3.1 Test count is visibly behind the field `[competitor survey, verified by execution]`

Verified competitors: Vetoed 303 commits / 239 passing tests. Skew 391 tests plus an
84-scenario stress test per candidate trade. Circuit Breaker 117/117. ORION 93/93.

We have roughly seven test files. Test count is one of the few things a reviewer checks in
thirty seconds, and CI badges are the single engineering signal the portfolio research
found actual evidence for.

Action: CI on GitHub Actions with a visible badge, and grow coverage where it is honest —
the risk gate, the capital arithmetic, the session window, the adversarial harness.

### 3.2 Check-time versus commit-time (TOCTOU) `[4/5]`

The gate checks pre-trade; nothing described re-checks post-fill. A check that passes on a
quote, then fills after the market moves, was computed against a structure that no longer
exists. One reviewer states the required invariant:
`state → check → lock → execute → verify → update state`, atomically.

Action: post-fill reconciliation that re-computes actual capital at risk from the fill
prices and halts on mismatch. We have the fill data from tonight to test against.

### 3.3 Portfolio cap is correlation-blind `[2/5]`

Summing per-trade max loss assumes zero correlation. In a crash, correlations go to one.
Three positions on correlated underlyings each clear the gate while joint tail exposure far
exceeds the bound.

### 3.4 Multi-leg fill atomicity `[3/5]`

One leg fills, the other pends, and a vol spike leaves a naked short. Fix named:
all-or-none / fill-or-kill contingencies. Our mleg orders are atomic at submission — verify
that atomicity holds at fill and say so explicitly rather than assuming it.

### 3.5 Capital-at-risk formula is only correct for verticals `[1/5]`

`(width − credit) × 100 × qty` does not generalise to calendars, diagonals or iron condors.
Either restrict the gate to structures the formula covers (and enforce that in code), or
extend it. Restricting is honest and cheaper.

### 3.6 Early assignment turns defined-risk into undefined-risk intraday `[5/5]`

"Defined-risk-at-expiration is not defined-risk-throughout-life." Assignment on a short put
delivers stock and eliminates the long leg's protection intraday. Our simulation models
none of it.

We sidestepped this live by being flat before expiry, which is management rather than
modelling. **Say that plainly** rather than claiming the risk is modelled.

### 3.7 State desync — local cache versus broker truth `[1/5]`

Portfolio cap reads a local position cache. Assignment, corporate action or partial fill
leaves it stale. Broker position should be the source of truth before the check.

### 3.8 Kill switch reachability `[1/5]`

If the kill switch is a boolean in memory, can a prompt injection reset it? Ours is
file-based, which is stronger — verify and state it.

---

## TIER 4 — presentation and framing

### 4.1 Honest limitations section `[5/5, portfolio set]`

Refusing to write one "robs the project of its strongest signal of seniority." Ours must
name: indicative feed not OPRA; no early-assignment modelling; single 900-day path; one
trade at n=1; the fill-analysis measurement is censored by construction; the counterfactual
is one day and one direction.

### 4.2 README is where technical builders systematically under-invest `[5/5]`

Because it feels like communication work rather than engineering. Pattern that recurs
across the exemplars: **headline claim → quantified proof → auditable link.** Open with a
falsifiable claim and a checkable number, not adjectives. An annotated directory tree so
the codebase maps in fifteen seconds.

Contradicted across reports: badge count (no limit / cap at 5–6 / badges are a marketing
anti-pattern), whether a demo video helps (#2 highest-leverage / listed under
diminishing returns), whether a live dashboard is the strongest functional evidence or
wasted polish. **Don't optimise against any of these; they cancel.**

### 4.3 Frame the negative result as method, not failure `[5/5]`

All five converge on near-identical phrasing. Ours: an adversarial validation harness that
prevents an LLM from deploying statistically unsupported strategies, which rejected 21 of
21 candidates and documented why each failed. Not "the strategies didn't work."

One reviewer's analogy is the cleanest: closer to "I built the fraud detector and it
correctly flagged every fraudulent transaction I tested it on."

### 4.4 The counterfactual stays as framed `[4/5 say it is noise]`

Four reviewers call n=1 outcome bias and rank it last or near-last; one ranks it Critical
and reads a 71% false-negative rate off it. One says delete it from the dashboard entirely
because it "encourages gambler's logic."

Keep it, keep the three bounds, do not strengthen the claim in either direction. The
existing framing — the gate refuses on the width of the interval, never on the sign of the
latest observation — already matches the majority position.

### 4.5 Say the arbiter incident is a live failure, not a hypothetical `[4/5 treat it as the strongest evidence]`

One reviewer makes it flaw #1 and its prescribed fix is uniquely non-technical: **stop
describing the arbiter's ruling as a decision and describe it as an unvalidated suggestion
the gate happens to also check.** Cost: none, it's a description change. Cost of not doing
it: eventually someone loosens the gate "because the council already checks this."

---

## TIER 5 — noted, deliberately not doing

- **ADRs.** Three of five portfolio reports rank writing them top-four at 4–6 hours; the
  one report that went looking for evidence found zero hiring-manager accounts mentioning
  them, and the citations offered are documents about *how to write* ADRs.
- **Optimising against reviewer time-on-page.** Five reports, five figures from 6 seconds
  to 10 minutes, two citing the same thread for opposite readings.
- **Rejection-history memory for the Proposer.** All five hostile reviewers prescribe it;
  only one names the cost, and the cost is decisive — the Critic reads a rationale, not the
  report, so the gradient the Proposer follows becomes "produce text this reviewer accepts."
  Memory cannot cost dollars (the gate still refuses) but it can cost the integrity of the
  audit trail, which is the more expensive currency here. Already rejected and recorded.
- **Buying real historical option data.** Cost estimates span $2k–$20k/year to "tens of
  thousands plus a C++/Rust rewrite." The §0.4 chain comparison gets most of the
  information for free.
- **Semantic versioning, dependency-audit theatre.** Three of five say ignored.

---

## Field context worth keeping in mind

From the competitor survey, all four reports independently: the field is dominated by
"LLM proposes, deterministic code disposes." One counted 17 of 39 entries. **Our
architecture is the crowded one, confirmed by four independent surveys.**

Field size: 86 submissions plus 85 drafts at time of capture (single source, unverified).

Ground nobody occupies, corroborated 3 of 4: the volatility surface — calendars, diagonals,
term structure, skew. Nobody trades term structure. Also thin: portfolio-level Greeks netted
across the book (2/4), margin and capital-efficiency modelling (2/4).

Our genuinely unoccupied position is the determinism measurement. Nothing in the surveyed
field resembles it. That is the headline, and §2.2 is how it reaches the audience that
matters beyond this weekend.
