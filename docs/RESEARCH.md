# RESEARCH.md — Alpaca AI Trading Agents Hackathon

Merged synthesis of 22 external research reports across four prompts: the competition,
Alpaca's technical reality, the problem domain, and strategy design under a 3.5-session
window. Supersedes `RESEARCH-BATCH-1.md` and `RESEARCH-BATCH-2.md`. Read alongside
`COMPETITION-BRIEF.md`, which holds the official rules verbatim.

Confidence labels used throughout: **[C]** convergent across several independent reports ·
**[X]** contradicted, unresolved · **[S]** singleton, one report only ·
**[?]** nobody could establish it.

---

# PART A — WHAT CONSTRAINS THE BUILD

## A1. Free tier has no OPRA. Options data is the "Indicative Pricing Feed" **[C]**

Five of six technical reports independently cite Alpaca's own market-data table
(`docs.alpaca.markets/us/docs/about-market-data-api`):

| | Basic (free) | Algo Trader Plus ($99/mo) |
|---|---|---|
| Options real-time | Indicative Pricing Feed | OPRA Feed |
| Options WebSocket quote subs | 200 | 1,000 |
| Historical API calls | 200/min | 10,000/min |
| Historical restriction | latest 15 min blocked | none |

"Indicative" is not "OPRA delayed 15 minutes." It is a derived feed. Alpaca staff
(forum thread 17795) describe latest-quote values as current but "randomized a bit"
versus true OPRA and explicitly "not real data." For *historical* endpoints the most
recent 15 minutes returns an outright error rather than delayed data. One report found
`/v1beta1/options/quotes` returning 404 on a free cluster
(github.com/ridopark/oh-my-tradeagent issue 191).

**Consequence:** any strategy whose edge depends on quote precision — tight spreads,
0DTE microstructure, precise IV — is not buildable here. Whatever we build must be robust
to noisy prices, and the write-up should say so rather than let a judge find it.

### Unresolved: is the fill engine seeing fresher data than we are? **[X]**

- Alpaca staff: indicative latest-quote is *current*, just modelled and randomised.
- One user's empirical test (forum 17795): the same signal scored a 45% win rate on live
  triggers versus 82% delayed 15 minutes — consistent with the agent seeing stale prices.
- One report asserts the sharper version: the agent reads 15-minute-delayed indicative
  data while paper fills match against the *current* real-time NBBO — a systematic bias,
  in some direction, in every paper P&L number we produce.

Nobody resolved this. It is directly testable: record the quote returned immediately
before submitting a marketable limit order, compare to the simulated fill price. Worth
doing on day one — if the third reading is right, the demo narrative must acknowledge it.

## A2. Paper accounts get Level 3 automatically **[C]**, with one dissent **[X]**

Stated identically on three Alpaca pages: "In the Paper environment, options trading
capability will be enabled by default — there's nothing you need to do," and "All paper
trading accounts will automatically have access to Level 3 strategies."

**Dissent:** one report claims a fresh paper account defaults to a *restrictive* level and
the agent must PATCH `max_options_trading_level` via account-configurations, or orders
fail with HTTP 403 `{"code": 40310000, "message": "account not eligible for level2
options trading"}`.

Cheap to settle: `GET /v2/account` returns `options_trading_level`. Check it in the first
ten minutes; PATCH if it isn't 3.

Level 3 covers verticals, straddles, strangles, iron condors, butterflies and calendars,
up to four legs. Naked/uncovered short legs need Level 4, and whether paper grants Level 4
is **[?]**. Sticking to defined-risk structures sidesteps this entirely — which we should
do anyway for reasons in Part C.

## A3. The MCP multi-leg bug — highest-priority technical risk **[C]**

`alpacahq/alpaca-mcp-server` **Issue #97**, opened 1 July 2026, still open. The
`place_option_order` tool's `legs` parameter — required for `order_class: "mleg"`, i.e.
every spread, condor and straddle — arrives at the server as a raw JSON **string** instead
of a parsed array and is rejected with a pydantic validation error. Single-leg orders
through the same tool work fine. The reporter proved both the REST API and the server code
are correct by POSTing the identical payload directly to
`paper-api.alpaca.markets/v2/orders`, which succeeded. The fault is in how the MCP client
transmits array parameters. Fix PR #107 open, merge status unconfirmed.

Reported independently in five of six technical reports.

Secondary finding from the same thread: the tool's docstring wrongly claims options orders
only support `time_in_force: "day"`. `"gtc"` is accepted and works.

**Consequence:** the options mandate forces multi-leg orders, and the obvious path to
placing them may be broken. Place a real two-leg paper spread through whatever order path
we choose **before building anything on top of it**. Fallback is direct REST POST or the CLI.

Working payload shape, from a community fix commit (github.com/xynkro/zerodte, b13851d):
drop the top-level `symbol`; each leg carries `ratio_qty` and `position_intent`
(`sell_to_open` / `buy_to_open`). Verified 200 against paper. **[S]**

## A4. Paper fills are optimistic in specific, documented ways **[C]**

From `docs.alpaca.markets/us/docs/paper-trading`:
- Orders fill only when marketable. Buys fill at the ask, sells at the bid, against NBBO.
- **Order quantity is not checked against available liquidity.** A 10,000-contract order
  on an illiquid strike fills completely.
- Random partial fills for a random size, 10% of the time.
- Does not model market impact, information leakage, latency slippage, queue position,
  price improvement, regulatory fees, dividends, or borrow fees.

Field reports add fill delays of 50–260 seconds after price crossed the limit (forum
18223), market buys filling 10%+ above current price (forum 17910), and deep-ITM expiry
producing no activity event at all (memon1987/options_wheel, May 2026) **[S]**.

**Consequence:** paper P&L over three days is soft evidence at best. Report a conservative
mark-to-market alongside Alpaca's number — ask-side entries, bid-side exits, spread-width
penalty — and build the demo narrative around process rather than the headline figure.

## A5. Rate limits: 200/min trading, 200/min market data, both flat on free **[C]**

Trading API 200 req/min per account; Market Data 200 req/min on Basic. Algo Trader Plus
raises the *data* limit to 10,000/min but **does not** raise the trading limit. Exceeding
returns 429 (code 42910000).

One report calculates that REST-polling 42 option symbols exhausts the limit in under five
seconds. WebSocket streaming rather than REST polling is the documented answer; the CLI and
SDKs retry 429/5xx with exponential backoff up to three attempts.

Dissent **[X]**: one report claims Alpaca doesn't publish fixed Trading API limits, but
cites the *Broker* API rate-limit page — a different product. Treat 200/min as correct.

## A6. Options lifecycle mechanics that will bite an unattended agent **[C]**

- ITM by $0.01 or more at expiry → **auto-exercised**, no opt-out except an explicit
  Do-Not-Exercise instruction. Processed by 6:00 PM ET on expiration day. Manual exercise
  requests between close and midnight are rejected.
- Insufficient buying power to cover an ITM exercise → Alpaca **liquidates the position
  itself**, up to one hour before expiry, while still ITM.
- Slightly-OTM positions can still be liquidated early if fast-market logic thinks they
  might flip ITM. "OTM does nothing" is not reliable near the money.
- **Exercise, assignment and expiry events are NOT pushed over WebSocket.** They appear
  only via REST non-trade-activity endpoints (`OPEXC`, `OPASN`, `OPEXP`, `OPTRD`), and in
  paper they surface at the start of the *following* day. An agent listening only on the
  trade-update stream will silently miss assignments.
- Options trade regular hours only. `extended_hours` must be false or omitted;
  `time_in_force` is `day` or `gtc` only. 24/5 trading covers NMS equities, not options.
- Greeks come from Black-Scholes and are **null when the contract expires today** (T=0)
  **or has no bid or no ask**. Mathematical, not a paywall — paying for OPRA doesn't fix
  it. Null-handle before parsing; don't substitute zero.
- Sell-limit orders on options are reportedly rejected as attempts to open a short even
  when the position is owned; `close_position()` is the working exit. Bracket orders
  unsupported for options. **[S]** — one report, but specific and consequential for exits.

## A7. PDT: probably no longer applies **[X]**

Three reports say PDT protection applies in paper and rejects orders with 403 under $25k
equity, citing a forum case of it firing at $30k. One report states FINRA **retired the
PDT rule on 4 June 2026**, replaced by a real-time intraday margin framework, and that
Alpaca's `pdt_check` SDK field was deprecated and removed 2026-07-06.

The retirement claim is dated, specific and post-dates the others' sources, so it is
probably correct and the others are reading stale docs. Either way $100k is well clear of
the old threshold. Not a blocker; don't design around it.

## A8. Day-one verification list

All cheap; each can invalidate a design.

1. `GET /v2/account` → confirm `options_trading_level` is 3, PATCH if not.
2. Place one real two-leg defined-risk spread through the exact order path we intend to
   use. If MCP is that path, this tests Issue #97 directly.
3. Fetch an option snapshot on a liquid symbol; check whether Greeks/IV are populated and
   compare the quote timestamp to wall clock.
4. Record a quote immediately before a marketable order, compare to the fill price.
5. Confirm whether `alpacahq/agentic` hosted MCP endpoints exist and work (see A9).
6. Confirm the option chain endpoint returns usable data; check pagination (`limit` caps
   at 1,000, default 100, `next_page_token`).
7. Confirm an exit path works — `close_position()` versus a sell limit.

## A9. Alpaca's own reference implementations — the de facto quality bar **[C]**

Every report that found these treats them as the closest thing to a published rubric for
"Technology Implementation."

- **`alpacahq/gamma-scalping`** — the most rigorous. Greeks via QuantLib using a
  Cox-Ross-Rubinstein binomial tree (correct for American-style early exercise), a
  moving-average bid-ask spread filter that **refuses to act on abnormally wide quotes**,
  and event-triggered rather than fixed-interval recalculation.
- **`alpacahq/options-wheel`** — cash-secured puts → assignment → covered calls on a cron
  loop with strict state isolation. Scores puts by annualised return discounted by
  probability of assignment, approximated via delta and DTE.
- **`alpacahq/alpaca-py/examples/options/`** — official iron condor and calendar spread
  notebooks. The condor notebook checks open-interest thresholds and enforces a
  buying-power limit before submitting.
- **`alpacahq/alpaca-skills`** (17 June 2026, `npx skills add alpacahq/alpaca-skills`) —
  Alpaca's own written definition of a trustworthy agentic workflow: formalise the strategy
  as precise rules *before* any code runs, fetch data consistently through the Market Data
  API, report benchmarks / assumptions / caveats in a standard format, and save reproducible
  run artifacts (`summary.json`, `trades.csv`, `equity.csv`, data fingerprints).
- **`alpacahq/agentic`** **[S]** — one report claims this repo provides *hosted* MCP
  endpoints (`paper-api.alpaca.markets/mcp`) over OAuth, removing the need to run the
  server locally and sidestepping the uvx/Docker/PATH bugs. Only one report mentions it.
  If real, a meaningful simplification. Verify early.

Also recommended in Alpaca's own material: `client_order_id` for idempotency, `--dry-run`
to preview orders, WebSocket trade-update streams as the source of truth rather than
polling, and paper-only environment gating.

---

# PART B — WHAT IS BEING JUDGED

## B1. The prize pool and judging criteria are disputed by a named judge **[X] — resolve first**

| Source | Says |
|---|---|
| lablab event page + our brief | $6,000; four criteria: P&L / Technology Implementation / Creativity & Originality / Presentation & Execution |
| **Tony Lee's own LinkedIn post** (named judge, describing this event) | **$5,000**; 3 cash places ($2,500/$1,500/$1,000) plus 2 Social Engagement Awards; criteria simply **"P&L and creativity or engagement"** |
| lablab's own promotional X post | **$5,000** |

Two reports found this independently. The four-criteria framing is word-for-word lablab's
*generic* template rubric, which appears verbatim on their platform-wide "How to Win"
guide — weak evidence that it is this event's actual rubric.

A "P&L and creativity" rubric and a "business value / market sizing / TAM" rubric imply
materially different builds and different videos. One Discord message settles it.

## B2. Sponsor priorities — what Alpaca wants out of this **[C]**

A tight, dated launch sequence this hackathon is clearly a showcase for:

| Date | Event |
|---|---|
| 23 Apr 2026 | Trading **CLI** launches — 108 functions, OAuth paper auth, framed explicitly for "AI agent execution workflows." Same day: Q1 API usage up ~4x QoQ, credited to AI agents. |
| 7 May 2026 | **MCP Server V2** — full rewrite on FastMCP + OpenAPI, 43 → 61 endpoints. |
| 4 Jun 2026 | NY Techweek workshop: "build your own AI-powered hedge fund with Alpaca," run by **Grace Gao and Brandon Meyerowitz** — two of the judges. Alpaca's recap claims they built and ran a working algo end-to-end with agents and the CLI in 10 minutes, no hand-written code. |
| 17 Jun 2026 | **Skills Library** launches. |
| Jul 2026 | **$135M raise** to expand AI-agent trading infrastructure, citing ~4x MAU growth as "AI agents became the new power traders." |
| Aug 2026 | CFTC FCM registration; Kalshi partnership for prediction markets. Separate business line, not required here. |

**Read:** Alpaca is mid-launch on CLI, MCP V2 and Skills, and reports agent-driven API
growth as an external business metric. An entry that visibly exercises the **newest**
surfaces — CLI and MCP V2 rather than plain `alpaca-py`/REST, ideally Skills too —
demonstrates exactly the adoption story they are telling investors. No report found an
explicit statement that this is scored higher; it is inference, but consistent inference
across five reports. The Techweek workshop is effectively an Alpaca-endorsed demo path:
paper account setup → strategy selection → live agent build → deployed running algo.

## B3. Judges, ranked by what they actually tell us **[C]**

| Judge | What research found |
|---|---|
| **Chiranjeev Shah** (Technical Content Marketing) | Highest signal. Author of Alpaca's writeups on NightWatcher V2, Agent M, and "From Quant Workflows to LLM-Assisted Trading" — which explicitly argues for separating policy from execution, deterministic constraints, and decision-trace logging. Also wrote on token efficiency, noting agentic trading bots burn 5–30x the tokens of ordinary chatbots. Note: he wrote the *articles about* NightWatcher; the repo is community-built (lnstt369). |
| **Grace Gao** + **Brandon Meyerowitz** | Co-ran the June Techweek "AI-powered hedge fund" workshop — the closest thing to an Alpaca-approved demo path. Meyerowitz leads the Trading API team and owns the CLI, whose design deliberately has zero guardrails; he will be reading error handling and programmatic safety. Little independent public writing from either. |
| **Tony Lee** (Chief Brokerage Officer) | Posted the event announcement on LinkedIn — source of the discrepancy in B1. Also fronts a YouTube walkthrough on paper-trading options with the Trading API. Broader commentary is about Alpaca as unified multi-asset infrastructure. |
| **Pawel Czech** (CEO NativelyAI, co-founder of lablab) | No trading-specific positions. Public argument is that AI-native software favours small teams solving narrow specific problems over broad platforms — consistent with the scope discipline everything else points to. |

## B4. The architectural pattern the evidence points to **[C]**

Every report examining recent trading-hackathon winners and Alpaca's own content converged
on the same shape:

> **LLM as qualitative synthesiser. Deterministic Python as the authority.** The model
> proposes; a non-LLM risk engine sizes, validates, and can veto. Orders are idempotent
> and every decision is logged so a judge can audit *why*.

Alpaca's own published pipeline (from `alpaca.markets/learn/from-quant-workflows-to-llm-assisted-trading-with-alpaca`
and the NightWatcher V2 writeup): point-in-time ingestion → specialised agents → synthesis
→ quant decision engine with calibrated probability → **independent non-LLM risk engine**
checking exposure, daily loss limits, liquidity, session → execution gate with idempotent
auditable orders.

Named failure modes worth designing against: God-Prompt Overload (one monolithic prompt
doing ingestion + analysis + execution), False Confidence from Plausible Output (fluent but
mathematically absurd rationales), Shadow Logic (unlogged routing or sizing decisions the
judge can't audit).

## B5. The live competition — this is the uncomfortable part **[C]**

As of 1 September the public dashboard showed roughly **3,394 participants, 1,120 teams,
41 submissions**, of which 31 tagged to the Options Alpha track. Named entries found
across reports:

| Entry | Approach |
|---|---|
| **Aegis / AegisAlpha** | "A trading agent you can audit." Forces the LLM to re-derive every claim; deterministic Python risk gate authorises before any order routes. Pitched as an agent that *refuses* bad trades. |
| **TradeCouncil / Debatte** | Bull and Bear LLM analysts argue; a deterministic CIO algorithm evaluates the debate; hard mathematical gates can veto execution. |
| **Vetoed** | "An agent most useful when it says no." Proposes defined-risk credit spreads; hardcoded sizing and margin gates hold final authority. |
| **IV Rank Premium Harvester** | Scans for elevated IV, bypasses the LLM entirely at execution, opens defined-risk credit spreads / iron condors. |
| **Strike Sentry** | Node/Express, Groq LLM with deterministic fallback, places orders explicitly via the **Alpaca CLI**. Cash-secured puts. Defaults to hold under uncertainty. |
| **glaz-trading-agent** (YSMsimon) | Risk gates in the README: 5% max position, −3% daily loss halt, 10 max open, 7–45 DTE, sizing on equity not buying power. |
| **OptionGuard-Ai** | 4-agent engine using Featherless models, heavy risk controls. Repo had ~1 commit — description without a working system. |
| **Team Scorpians** | Hybrid RL + Transformer forecasting with GPU-accelerated backtesting. |
| Others named | Beleth (credit-spread seller), Accountable Alpha, AlphaLoop Autonomous, Citadel Street, AgentTrade AI, Han Solo, MDS, Norman |

**The problem in one line:** the "auditable agent with a deterministic risk gate that
refuses trades" position is correct *and* already crowded. Building that and nothing else
means being the sixth-best version of something judges will have seen five times. Part D
is the answer to this.

## B6. What loses **[C]**

- Demo that only runs locally — lablab's own guidance says it "scores as if it doesn't
  work." Private repo, missing video, missing deployed URL: same effect.
- **Missing the Alpaca paper account ID on the submission form.** P&L is judged from that
  account; no ID means no P&L score.
- Single-push repositories. Multiple reports say judges look for commits spread across the
  event window; a fully-formed codebase in one final commit reads as pre-built.
- Building more than the team understands — cited by a hackathon judge as visibly
  detectable. Feature pile-up, abstraction stacking.
- **AI voiceover and over-polished template UI are reported as actively penalised** — a
  judge writing on HackerNoon says human voice and own face beat AI narration, and that
  Lovable-perfect UIs read as inauthentic. **[S]** but from a judge's own account.
- Token single-leg options as a compliance checkbox. Multiple reports read the options
  mandate as requiring options to be the reason the strategy exists.

---

# PART C — WHAT THE STRATEGY EVIDENCE SAYS

## C1. The variance arithmetic — the finding that should shape everything **[C]**

All four strategy reports derived the same result independently, from `t = Sharpe × √(T/252)`.
Over 3.5 sessions, `√T = 0.118`.

| True annualised Sharpe | t-stat over the window | P(positive P&L) | Days needed for t=1.96 |
|---|---|---|---|
| 0.0 (coin flip) | 0.000 | 50.0% | ∞ |
| 0.5 (average fund) | 0.059 | 52.4% | ~3,870 (15 yrs) |
| 1.0 (good) | 0.118 | 54.7% | ~970 (3.8 yrs) |
| 2.0 (world class) | 0.236 | 59.3% | ~242 |
| 3.0 (elite) | 0.354 | 63.8% | ~107 |

Skill accounts for `S²T/(1+S²T)` ≈ **1.4% of outcome variance at Sharpe 1.0**. A genuinely
elite strategy loses money over this window more than a third of the time. The window is
roughly 32× too short to detect even an elite edge.

### The competitive corollary **[S, but the arithmetic is checkable]**

If N entrants all have zero edge and P&L standard deviation σ, the expected *maximum* score
is approximately `σ·√(2 ln N)`. With ~100 entrants that is about 3σ. On the P&L leg alone,
the winner is with near-certainty whoever sized largest, not whoever reasoned best. Any
strategy tuned to *win* that leg is tuned to blow up roughly 40% of the time.

**This is the strategic hinge.** We cannot out-P&L a lucky lever-up, and trying means
accepting a large probability of a visible loss. What we can do is be the entry that says
this out loud, quantifies it, and designs around it.

### Expected dispersion at sane sizing on $100k **[S — one report's arithmetic]**

Calibrated to VIX ≈ 15, SPX daily σ ≈ 0.94%, 3.5-day σ ≈ 1.77%:

| Structure | 3.5-day P&L σ | 3.5-day mean |
|---|---|---|
| One 30-delta SPY CSP, 30 DTE | 0.5–0.7% of NAV | +0.10 to +0.15% |
| Defined-risk credit spread book at 5% NAV total risk | 1.5–2.5% | +0.3 to +0.6% |
| 0DTE book cycling daily at 2% risk/day | 3–5% | ≈0 after costs |
| Long straddles into the biggest implied movers | 4–8% at 1% NAV/position | negative, left-skewed |

Every one has |mean| under one-fifth of its standard deviation over the window.

## C2. The calendar — the most actionable output of the whole research round

### Economic releases, 1–4 September 2026 **[C — three reports, all citing the NY Fed calendar]**

| Date | Day | Releases (ET) |
|---|---|---|
| Sep 1 | Tue | Construction Spending 10:00 · **ISM Manufacturing PMI 10:00** · JOLTS 10:00 |
| Sep 2 | Wed | **ADP National Employment 08:15** · Mfg Shipments & Orders 10:00 |
| Sep 3 | Thu | Initial Claims 08:30 · Advance trade in goods 08:30 · Revised Productivity & Costs 08:30 · **ISM Services 10:00** |
| Sep 4 | Fri | **EMPLOYMENT SITUATION / NONFARM PAYROLLS 08:30** |
| Sep 7 | Mon | Labor Day — US markets closed |

FOMC is 16 September, CPI is 11 September. Both outside the window.

### Why NFP dominates

Payrolls prints at **08:30 ET Friday 4 September = 6:00 PM IST**. The submission deadline
is **8:30 PM IST = 11:00 AM ET**. The market opens at 09:30 ET.

Final-day sequence: NFP prints → one hour later the market opens → ninety minutes after
that, we submit. **The judged account is marked in a post-NFP session, with a three-day
weekend behind Friday's close.**

Any short-premium position carried into Thursday's close faces a gap through an 08:30 macro
print with no ability to manage it. This single scheduling fact has more effect on the
outcome distribution than any signal we could compute — and most entrants will not have
noticed it. It also means the last real trading decision is Thursday, not Friday.

### Earnings — dense, and the reports disagree **[X]**

Report A (via Benzinga, 30 Aug): MongoDB Sep 1 AMC · Brown-Forman Sep 2 BMO · Snowflake,
HPE, NetApp Sep 2 AMC · Ciena Sep 3 BMO · DocuSign, Zscaler, Samsara, Guidewire Sep 3 AMC ·
Lululemon Sep 3 BMO. Implied moves: Brown-Forman 15.98%, MongoDB 14.06%, Samsara 12.89%,
Zscaler 12.75%, Guidewire 12.22%, NetApp 11.88%, Ciena 11.65%, DocuSign 10.99%, HPE 10.79%,
Snowflake 10.76%.

Report B (via TipRanks, 1 Sep): Sep 1 — DELL, MDT, SBSW, YEXT, NIO, PANW, MDB, GTLB, CRDO.
Implied moves: YEXT ±19.65%, MDB ±15.81%, GTLB ±12.68%, SBSW ±12.07%, CRDO ±11.80%,
DELL ±10.41%, NIO ±10.40%, PANW ±9.35%, MDT ±5.42%. AVGO Sep 2 AMC. LULU Sep 3.

**Broadcom's date is disputed across three sources** (Sep 1 vs Sep 2 AMC). Two other
reports could not verify earnings at all.

Do not hard-code any of this. Pull the earnings calendar live at runtime.

### Market context on 31 August **[S — specific enough to be checkable]**

VIX closed 14.92, up 3.39%, after US–Iran strikes resumed and revived Strait of Hormuz
concerns. The prior Friday's 14.13 was the 2026 low. S&P 500 closed 7,711.76. VIX's
historical median in late August is near 16.5, rising toward 18 by mid-September. Kevin
Warsh took office as Fed chair on 22 May 2026 replacing Powell, and stocks closed lower on
28 August after his warning on sticky inflation.

If accurate: implied vol at the year's low, a hawkish new Fed chair, an active conflict
affecting oil, and the month's largest data release on the final session. We would be paid
below-average premium to carry an above-average tail, and the tail is scheduled. **Verify
live before relying on it.**

## C3. Strategy families over 3.5 sessions **[C]**

| Family | Verdict | Why |
|---|---|---|
| **Wheel / cash-secured puts / covered calls** | Wrong horizon | One SPY CSP ties up ~$76,750 of $100k (SPY ≈ $767). Holding period 21–45 days; we'd harvest 3.5/30ths of the theta. A 12-month strategy stapled into a 3-day box. |
| **Credit spreads / iron condors** | Best structural fit | Theta accelerates into expiry, so the window captures the most active part of the trade's life. Defined risk. Roughly 75–80% chance of +1 to +3%; ~15% chance of −2 to −5%; ~5% chance of −10% or worse. Negative skew, high win rate, no free lunch. |
| **Debit spreads / long directional** | Negative EV | Only family with a genuinely capped worst case, but retail weeklies carry an average **12.6% bid-ask spread** (Bryzgalova, Pavlova & Sikorskaya). Round-tripping that twice is a 20%+ hurdle before being right about direction. |
| **0DTE** | Highest variance, contested evidence | Now ~62–65% of SPX volume. Gamma goes hyperbolic in the last two hours. Literature genuinely split (see C6). Maximises independent bets and the tail simultaneously. |
| **Straddles / strangles / calendars** | Long vol pays the VRP = negative drift | But **a calendar selling the Friday 4 Sep expiry (inflated by NFP) and buying the following week** is the one structure this specific window is built for. Long vega, short front gamma, paid if the event is priced richer than it realises. |
| **Earnings / catalyst** | Real but small edge, fat left tail | Implied moves average modestly richer than realised earnings moves, so defined-risk short premium at ±1.3× implied has positive expectancy. Worst case on a 12% implied mover that gaps 25% is total loss of defined risk. |
| **Delta-neutral / gamma scalping** | Not viable | P&L is realised minus implied variance over 3.5 days — enormous standard error estimating a variance from three daily returns. Rehedging costs swamp the edge without institutional spreads. |
| **Dispersion / relative value** | Not viable | 20–50 legs, correlation modelling, P&L accrues over weeks. Execution cost of establishing and unwinding in 3.5 days exceeds any plausible edge. Scores well on originality, terribly on realism. |

## C4. Signals — one survives, six don't **[C]**

**Variance risk premium (IV − RV) — the only well-supported input.** Carr & Wu (2009) found
average variance risk premia strongly negative for the S&P 500/100 and the Dow: option
sellers are systematically paid. Roughly 25–30% of months are negative-VRP, and those
losses are concentrated and violent. Goyal & Saretto (2009) found the cross-section of
option returns is predicted by the IV−RV deviation — **but that 1.4%/month edge collapses
to 0.17%/month once the effective spread is 50% of quoted.** Transaction costs are the
whole story. Note also that the VRP supports *carrying* short vol, not *timing* it.

**IV rank / IV percentile — regime filter, not signal.** No peer-reviewed work shows
IV-rank entry timing improves risk-adjusted short-premium returns. The tastytrade "sell
above IVR 50" rule is marketing built on in-sample study. High IV predicts a larger VRP
*and* higher realised vol; the effects partly cancel. Also needs a year of daily
30-day-constant-maturity IV, which the broker API doesn't provide — you interpolate it.

**Term structure — decent filter, and relevant right now.** VIX/VIX3M or a front/back IV
ratio. Contango on most days; backwardation is a real stress signal. Specifically useful
here: front-week IV should be bid relative to the following week because of NFP, and that
spread is directly tradeable as a calendar.

**Skew — doesn't survive to this horizon.** Xing, Zhang & Zhao found steepest-smirk stocks
underperform flattest by 10.9% annually after risk adjustment — a cross-sectional,
monthly-rebalanced result. The CBOE SKEW index has poor documented predictive power for
actual tail events.

**Open interest / unusual options activity — not reconstructible from a broker API.**
Pan & Poteshman (2006) found strong predictability using open-*buy* volume ratios, but used
proprietary CBOE data flagging trade direction and open/close. Public tape gives total
volume and OI with no direction. Jiang & Strong (2024): large option trades are *in general
not predictive*; only a narrow subset (large, near-expiry, OTM) shows significant abnormal
returns. Most "unusual" flow is hedging and rolling.

**Put/call ratio — weak and unstable.** Heavily distorted by hedging flows. The volatility
spread (call IV minus put IV at matched strikes) is the better version: Cremers & Weinbaum
found relatively-expensive-call stocks outperform by 50bp/week — but the authors note the
predictability *decayed over their sample*. 50bp/week on a cross-sectional sort of thousands
of stocks is not a 3-day signal for $100k.

**Implication:** a signal stack with five inputs will have four decorations, and a competent
judge may notice. One well-defended input beats five decorative ones.

## C5. Risk controls — what the failures teach **[C]**

### Knight Capital, 1 August 2012

A deployment reused a flag previously assigned to dormant "Power Peg" code, and the new
build reached seven of eight SMARS servers. The eighth ran Power Peg, whose cumulative
quantity tracker had been detached in 2005 without retesting. In 45 minutes it sent **over
4 million orders trying to fill 212 customer orders**, traded 397 million shares, and lost
**more than $460 million**. The firm settled for $12M in the first-ever enforcement under
Rule 15c3-5.

The SEC's findings are the useful part: no written software-deployment procedures, no
adequate testing in a production-like environment, **no automated process for detecting
erroneous orders before they reached the tape**, and no documented escalation path to
senior risk management. Knight had also lost $7.5M to an erroneous-order incident in
October 2011 and did not tighten controls afterwards.

### Other reference failures

- **XIV / Volmageddon, 5 Feb 2018** — short-vol ETPs had a mechanical obligation to buy VIX
  futures at the close; a spike created a feedback loop. XIV lost >90% in one session and
  Credit Suisse liquidated it.
- **OptionSellers.com, Nov 2018** — naked short natural gas calls; a squeeze pushed margin
  past liquidation value. >$100M lost, clients left with negative balances.
- **Lobstar Wilde, 22 Feb 2026** — an autonomous crypto bot built in days by an OpenAI
  employee with $50,000, instructed to "make no mistakes," misread an instruction to send a
  small tip and transferred its entire ~$250,000 holding. The clearest documented case of an
  autonomous financial agent executing a catastrophic instruction-following error with real
  money.

### The control list, in priority order

1. **Order-rate limiter.** Max orders per minute and per session, enforced in code between
   strategy and broker client. The control that would have saved Knight; about twenty lines.
2. **Portfolio kill switch.** Hard stop at a drawdown threshold — flatten, refuse new
   orders, require manual reset. 3–5% of starting NAV is defensible over 3.5 days.
3. **Pre-trade position and notional limits.** Max contracts per symbol, max gross delta,
   max short gamma, max vega. Checked before every order, not after.
4. **Per-trade defined risk.** Never open an undefined-risk short. A single naked short SPX
   put 2 DTE at 10-delta becomes roughly a $24,400 loss per contract on a −5% gap.
5. **Liquidity filter.** Reject any leg where bid-ask exceeds a fixed fraction of mid (10%
   is generous), OI below a floor, or the bid is zero.
6. **Assignment elimination.** Cash-settled European-style index options remove early
   assignment, ex-dividend assignment on short calls, and pin risk in one decision.
   **XSP is one-tenth SPX notional (~$771), which sizes correctly for $100k.** If trading
   American-style equity options, close anything within 1% of the strike before 15:45 on
   expiry day — the OCC exercises by exception at $0.01 ITM.
7. **Reconciliation loop.** Poll broker positions every cycle, compare to internal ledger,
   halt on mismatch. Most agent failures in a build like this are state-desync bugs, not
   bad alpha.
8. **Idempotent orders.** Client-generated order IDs so a retry after a timeout can't
   double-fill.

## C6. LLM division of labour — the evidence is close to unanimous **[C]**

### What the published record says

- **FINSABER (KDD 2026)** — 20-year benchmark, 100+ S&P 500 names including delisted ones.
  Neither FINMEM nor FINAGENT generates statistically significant alpha. Buy-and-hold
  significantly outperforms both. All p-values > 0.34.
- **"The Alpha Illusion" (arXiv 2605.16895, May 2026)** — adding commission, token cost,
  spread and market impact drops TradingAgents' Sharpe from 0.43 → 0.22 and QuantAgent's
  from −0.96 → −1.15. Both end below buy-and-hold.
- **"Agentic Trading" survey (arXiv 2605.19337)** — audited 77 studies, 19 with closed-loop
  evaluation. **Only 2 of 19 report time-consistent train/test splits. 1 of 19 specifies a
  transaction-cost model. 0 of 19 reach the top reproducibility tier.** The authors call it
  "protocol incomparability."
- **KTD-Fin (arXiv 2605.28359)** — memory-controlled benchmark anonymising tickers and
  dates. Ungated, models reason in brand terms; gated, they switch to factor-based
  reasoning. Barra-style attribution on the gated results shows cumulative returns are
  **largely explained by passive exposure to market and style factors**, with one of ten
  frontier models showing near-zero true selection alpha and the rest negative.
- **PolyBench (arXiv 2604.14199)** — live prediction markets. Models with zero hallucinations
  and perfect instruction compliance still posted sub-zero returns. Five of seven lost money.
- **FinMem reversal** — a reported 23% return on MSFT became −22% under controlled
  re-evaluation.
- **TrustTrade** — given identical market conditions, different LLM agents frequently reach
  divergent decisions, with substantial variation in returns, drawdowns and risk-adjusted
  performance. Performance versus reasoning depth is stage-wise, not monotonic.
  **Non-determinism under identical inputs is disqualifying for anything that touches
  sizing or order construction.**
- **Nof1 Alpha Arena (Oct 2025)** — six LLMs, $10k of real capital each, crypto perps.
  GPT-5 down 39.73%. Aggregate roughly −35% across 96 model-days.
- The most-starred open-source "AI hedge fund" reference implementation (45,300+ stars) is
  itself a documented look-ahead-bias case study.

**Net:** no credible published result shows an LLM trading agent generating real,
reproducible, cost-adjusted alpha out of sample.

### The division that follows

**LLM owns:** parsing unstructured input (earnings text, headlines, Fed language) into
typed fields · regime *labelling* against an explicit rubric · proposing candidate
parameters offline before the session · generating the human-readable rationale attached to
each trade in the audit log · narrating an anomaly when a risk limit fires.

**Deterministic code owns:** all arithmetic (Greeks, margin, breakevens, P&L) · position
sizing · strike and expiry selection given a parameter set · every risk check · order
construction and submission · the kill switch.

**The interface** is a constrained schema. The LLM emits
`{direction, conviction ∈ [0,1], regime_label, rationale}` and nothing else, into a
deterministic policy function that maps it to a trade or to no trade. Log the full prompt,
model version, temperature, seed and response for every call so the run is replayable. That
replayability is itself a strong reasoning-quality signal, and it maps onto the reporting
standards both survey papers propose (P1–P6 in Alpha Illusion, MR-1–MR-7 in Agentic Trading).

## C7. Backtesting in three days — you can't, so don't claim to **[C]**

Every report agrees: you cannot validate an options alpha in three days, and claiming
otherwise in the write-up costs more with a competent judge than admitting it. What you
*can* do, in descending value per hour:

1. **Test the system, not the strategy.** Replay a synthetic session through the whole stack
   — order construction, margin calculation, fill simulation, risk limits, kill switch.
   Deliberately inject a bad LLM response, a broker timeout, a duplicate fill and a limit
   breach, and confirm each is caught. This is where a 3-day build actually fails.
2. **Monte Carlo the payoff instead of backtesting it.** Simulate 10,000 paths from a
   jump-diffusion calibrated to the current IV surface, with a jump component sized to the
   NFP-day tail, and read off the P&L distribution of the specific structure. Honest
   expected value and 5th-percentile outcome in about an hour, no data licensing.
3. **Event-study the last N NFP Fridays.** Needs only SPX daily OHLC (free) plus front-week
   IV before and after each print. Twenty observations is weak, but it is an estimate, and
   stating its standard error is itself a reasoning credit.

**Shortcuts that produce lies:** mid-price fills (a 12.6% spread makes mid fictional) ·
EOD-settled Greeks treated as intraday · ignoring early assignment on American-style shorts ·
assuming fills on the far side of a wide market · running many parameter variants and
reporting the best (Bailey & López de Prado's backtest-overfitting problem).

**Data:** yfinance gives only the current chain, no history. Cboe DataShop offers a free
trial of up to six months of EOD open-close data to firms and non-members who haven't
previously purchased, with the paid product at $600/month. Polygon ~$29/mo for snapshots;
ORATS from ~$99/mo. Our own broker's paper API is the fastest path to a chain snapshot.

## C8. Contrarian reads worth stating in the write-up **[C]**

- **"High win rate means the strategy works."** A 90%-win-rate credit spread with a 1:9
  payoff has exactly zero edge before costs and negative edge after. Win rate is a *shape*
  parameter, not a performance metric.
- **"Sell premium when IV rank is above 50."** No peer-reviewed support. What the literature
  does support is that *sizing*, not timing, drives put-writing outcomes.
- **"0DTE theta is free money."** Genuinely contested in both directions, which is itself
  the finding. Beckmeyer, Branger & Gayda document substantial retail 0DTE losses;
  Bogousslavsky & Muravyev's trader-level data finds naked option sales earn about 20% on
  average and argue the loss narrative is overstated; a Cboe study using exchange data with
  true trade directions finds customer single-leg-improvement trades profitable on average.
  Anyone stating either side as settled is overclaiming.
- **"Delta-neutral means market-neutral."** You remain short gamma, short vega and long
  theta. Your delta is zero for about four minutes.
- **"Options are a capital-efficient way to express a directional view."** Bryzgalova et al.
  estimate aggregate retail option losses of $2.1B from Nov 2019 to Jun 2021, with the bulk
  from indirect trading costs — the distance from trade price to midquote totalling $6.4B
  across their sample.
- **Credit spreads are "economic catastrophe bonds"** (Coval, Jurek & Stafford 2009) — a
  steady stream of trivial gains bought by exposing the seller to catastrophic loss precisely
  when the economy and market liquidity are at their worst.
- **The one retail belief the research supports but under-uses:** the variance risk premium
  is real, persistent and cross-asset. Retail traders believe it and then destroy it with
  position sizing that guarantees ruin on the fifth-percentile day.
- **Separate "AI-branded fund blows up" from "AI trading fails."** Situational Awareness went
  from ~$45B to ~$10B in July 2026 on roughly 400% leverage in a concentrated
  AI-infrastructure bet — a human PM's decision, not an autonomous agent's.

---

# PART D — THE PROBLEM DOMAIN AND OUR POSITION

## D1. The gap is execution and management, not signal generation **[C]**

The recurring refrain across builder post-mortems: *"algotrading is 5% strategy and 95%
error handling."* One widely-cited account describes seven weeks building a Python options
bot, a backtest that looked fine, then discovering on day one live that the backtest was
"garbage because I wasn't accounting for slippage," followed by weeks of patching until it
became a second job. The documented real-world failures are auth lockouts, API churn,
partial fills, missed rolls, assignment blindness — not "the AI wasn't smart enough."

## D2. The structural gap nobody has closed **[C]**

Broker-native *agent execution* is brand new as of 2026 and equity/crypto-first, with
options support trailing:
- **Robinhood** shipped a first-party MCP server on 27 May 2026 — the first major consumer
  broker allowing a third-party agent to place live trades without per-trade human
  confirmation, later extended to options.
- **Alpaca** ships an official MCP server for developers.
- **Interactive Brokers** deliberately keeps execution gated — the agent drafts, a human
  submits. A meaningfully different trust model.
- **Schwab, Fidelity, tastytrade, E*TRADE** remain read-only or unofficial-MCP-only.

Meanwhile, options-*specific* automation logic — rolling, assignment handling, wheel and
spread adjustment, real Greeks-based risk checks — lives in an older, separate, rules-only
generation of tools (Option Alpha, ThetaGang). **Nobody has merged the two.** Agent-native
infrastructure has no options risk logic; options automation isn't agent-native.

Related: every current broker-agent integration caps risk with a dollar-funded sub-account.
That bounds the *magnitude* of loss but not the *shape*. It doesn't stop an agent writing
an undefined-risk strangle, walking into assignment on an ITM short leg it didn't track, or
blowing through margin on a multi-leg adjustment. **The gap between "dollar cap" and "real
options risk control" is unclaimed.**

## D3. Trust data — users want less autonomy, not more **[C]**

- Investing.com, March 2026, 938 US retail investors: **62% already use AI** to inform
  investment decisions, but only **4% trust it completely**; 54% trust it "only somewhat."
  39% worry about incorrect recommendations, 24% about AI-driven herding.
- Betterment, April 2026, 1,000 US investors: **31% overall trust** in AI for financial
  advice — but of the minority who do trust it, 53% say it changed a decision they wouldn't
  otherwise have made. Trust is bimodal, not gradual.
- HSBC/Ipsos, June 2026, ~10,000 respondents: **31% of US investors say AI makes them feel
  *less* in control** (vs 26% globally). 38% prefer a hybrid AI-plus-human model.

Robinhood's own agentic-trading terms state it "does not control, supervise, monitor,
recommend, or audit" third-party AI agents, that data leaves its security environment once
shared with an AI provider, and that the user "assumes all risk for orders placed by your AI
agent."

## D4. Regulation is behind the shipped product **[C]**

FINRA's 2026 Annual Regulatory Oversight Report (Dec 2025) added its first dedicated GenAI
section, explicitly flagging "AI agents acting autonomously with no human in the loop" and
poorly designed reward functions, and calling for permission limits, access monitoring and
audit trails. In June 2026, Reps. Foster and Sherman wrote to SEC Chair Atkins asking who is
accountable — broker-dealer, AI developer, or the agent — when agentic trading platforms
make a costly error. No public answer as of this research.

## D5. Five things that separate us from the five competitors pitching the same architecture

The "LLM proposes, deterministic gate disposes" architecture is *correct* — everything in
Part C confirms it — and *crowded* (B5). We cannot avoid it and shouldn't try. What the
research adds are five things the auditable-agent crowd is unlikely to have:

1. **The variance argument, stated numerically.** If the P&L leaderboard winner is whoever
   sized largest (C1), then an entry reporting the t-statistic of its own result alongside
   the P&L is doing something none of them are. Auditable is not the same as statistically
   honest.
2. **The NFP scheduling decision.** Most entrants will not have worked out that payrolls
   print 2.5 hours before the deadline, on the day the account is marked, with a three-day
   weekend behind it. Being flat or long-gamma into that print is a concrete, defensible,
   dated design decision.
3. **Options-native risk gating — checking the shape of loss, not just its size.** Greeks,
   margin impact, and assignment/early-exercise exposure evaluated *before* order
   submission. This is the identified structural gap in the whole product landscape (D2),
   and it is what everyone else means by "risk gate" but doesn't implement.
4. **Replay determinism against a named published standard.** Logging prompt, model version,
   temperature, seed and response so the run reproduces, conforming explicitly to the
   reporting protocols the 2026 survey literature proposes. Hard to argue with, and nobody
   else will cite them.
5. **Honesty about the data.** Our quotes are the randomised indicative feed, not OPRA (A1).
   An entry that labels this and quantifies what it does to the results is doing something no
   competitor advertising a P&L number will do.

None of these guarantees anything. They are the parts of the outcome we control.

---

# PART E — OPEN QUESTIONS

## E1. Must be resolved before building

- **The real judging criteria and prize pool** (B1). A Discord message settles it.
- **`options_trading_level` on a fresh paper account** (A2). One API call.
- **Whether multi-leg orders work through our chosen path** (A3). One test order.

## E2. Should be verified early, may change the design

- Whether `alpacahq/agentic` hosted MCP endpoints exist and work (A9).
- Whether the paper fill engine uses fresher data than the indicative feed we see (A1).
- Whether the 31 August market context is accurate — VIX 14.92, SPX 7,711.76 (C2).
- Exact earnings dates in the window; three sources disagree, Broadcom especially (C2).

## E3. Could not be established by any report **[?]**

- Numeric judging weights, scoring scale, number of judges per submission, whether they
  score independently or deliberate, tie-break procedure.
- How the Social Engagement award is calculated for *this* event. One report found lablab
  language from other events describing a quantitative score from impressions / likes /
  shares / reach across linked accounts.
- Whether judges take P&L from account equity, `portfolio/history`, realized P&L, or an
  organiser-controlled snapshot. **Keep our own immutable trade ledger regardless.**
- Whether paper accounts get Level 4 (uncovered legs).
- Whether early (pre-expiry) assignment on a short paper leg is simulated at all — a May
  2026 forum question asking exactly this has no reply.
- Whether multi-leg paper orders fill atomically, and how fills are allocated across legs.
- Any first-hand participant account of lablab scoring mechanics.

## E4. Links worth opening manually — I can't read these

Ranked. Everything else in the reports is already extracted above.

1. **Tony Lee's LinkedIn post announcing this event** —
   `https://www.linkedin.com/in/tony-lee-cfa-5ab61189/`
   The prize-pool and criteria discrepancy. Read first.
2. **Live hackathon dashboard and submissions** —
   `https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon/live`
   Current submission count and what the visible competitors claim. Specifically
   `.../aegis-labs/aegis-a-trading-agent-you-can-audit` and
   `.../silvercrane/tradecouncil-multi-agent-options-alpha`.
3. **Alpaca Techweek "AI-powered hedge fund" workshop** —
   `https://x.com/AlpacaHQ/status/2062584379659161651`
   Two judges demonstrating their own idea of a good demo path.
4. **Tony Lee, paper-trading options with the Trading API (YouTube)** —
   `https://www.youtube.com/watch?v=B0Z7oCmr5nM`
5. **Chiranjeev Shah, "From Quant Workflows to LLM-Assisted Trading with Alpaca"** —
   `https://alpaca.markets/learn/from-quant-workflows-to-llm-assisted-trading-with-alpaca`
   Closest thing to a judge's written architecture preference. Text, so fetchable if preferred.
6. **Discord `#ineedhelp`** — confirm the prize pool and judging criteria. Cheapest possible
   resolution of B1.
