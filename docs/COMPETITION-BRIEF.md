# COMPETITION-BRIEF.md — Alpaca AI Trading Agents Hackathon

Extracted from all 15 project documents. This is the durable record. Any claim I make
later that isn't in here should be treated as soft until re-checked against source.

**Source files:** `Complete_Hackathon_Details.md` (primary, 1276 lines),
`Lablab_ai_Hackathon_Rule_Book.md`, `Submission_Guidelines.md`, `FAQ.md`,
`Getting_Started_With_lablab.md`, `Overview_of_the_Hackathon_Journey.md`,
`Video_Guide.md`, `How_to_Win_an_AI_Hackathon.md`,
`AI_Hackathons_The_Complete_Guide.md`, `How_To_Be_Successful_At_The_Hackathon.md`,
`AI_Hackathon_Project_Ideas.md`, `Best_AI_APIs_for_Hackathons.md`,
`Discover_AI_Technologies.md`, `01SetupTheory.pdf`, `03SkillsAndPlugins.pdf`

---

## 1. The event

lablab.ai × Alpaca. "Alpaca AI Trading Agents Hackathon — Code the next generation of
algorithmic trading." Fully online, 7 days, 28 Aug – 4 Sept 2026.

**Submissions close: Sep 4, 8:30 PM India Standard Time.**
That is 15:00 UTC = 11:00 AM US Eastern, i.e. roughly 90 minutes after the US market
opens on Friday.

Prize pool stated inconsistently in source: header says $6,000, body says $6,300, prize
terms say "AlpacaDB, Inc. pays the $6,000 pool directly in USD." Itemised prizes below
sum to $6,000 cash + non-cash extras. Treat $6,000 as the cash figure.

---

## 2. Hard requirements — fail any of these and the entry is not judged

1. **Autonomous AI trading agent** built on Alpaca's Trading API.
2. **Must use Alpaca's MCP server OR its CLI tools.** Either satisfies it.
3. **All strategies must incorporate options trading.** Not optional, not partial.
4. **Final submission must run on a brand-new Alpaca paper trading account created
   specifically for this hackathon.** Verbatim: "Projects run on an existing or reused
   account will not be eligible for judging."
5. **That account's starting balance must be set to $100,000.**
6. **One-page write-up** covering AI logic, risk gates, and Alpaca infrastructure
   implementation.
7. **The Alpaca paper trading account ID must be included in the submission** — judges
   use it to pull trading activity and evaluate P&L.
8. Submissions must be **original and MIT-compliant** (from prize terms).
9. Team must exist on lablab.ai — required even for solo. Every member registers
   individually. Discord must be connected before a team can be created. Teams are 1–6.

---

## 3. Judging criteria — the Alpaca-specific set

These override lablab's generic four. Order as printed; no weights published.

1. **P&L Performance** — trading performance of the submitted agent in the paper
   environment. Judges consider P&L and how effectively the strategy performs through its
   trading activity.
2. **Technology Implementation** — how effectively the project uses Alpaca's Trading API,
   MCP server, CLI and other required technologies to build an autonomous agent.
3. **Creativity & Originality** — of concept, trading strategy, agent behaviour, overall
   approach.
4. **Presentation & Execution** — how clearly it communicates the idea, demonstrates the
   agent in action, and presents the reasoning behind strategy and results.
5. **Social engagement** (separate prize track) — quality of content *and* engagement it
   generates. Likes/comments/shares count, so does usefulness and creativity.

**Noise to ignore:** `Lablab_ai_Hackathon_Rule_Book.md` and `Submission_Guidelines.md`
list the platform-default criteria (Presentation / Business value / Application of
technology / Originality). Those are the generic lablab rubric, not this event's.
`Submission_Guidelines.md` also demands an "IBM Bob Report" — that's residue from an IBM
event template and does not apply here.

---

## 4. Submission checklist

**Basic:** project title · short description (≤255 chars) · long description (≥100 words)
· technology & category tags · track selection if the event has tracks

**Assets:** cover image PNG/JPG 16:9 · video presentation as an **uploaded MP4 file, not
a link**, under 5 minutes and under 300 MB · slide presentation as PDF

**App:** public GitHub repository · demo application platform (lablab names Streamlit,
Replit, Vercel) · application URL that judges can interact with

**Alpaca-specific:** paper trading account ID · one-page write-up (AI logic, risk gates,
infrastructure)

**Optional:** up to 5 links to X/LinkedIn posts made during the hackathon, tagging both
lablab.ai and Alpaca. Tags: X `@lablabai`, `@AlpacaHQ`; LinkedIn `lablab.ai`, `Alpaca`.

Manual submission is available for 6 hours post-deadline only with a valid reason **and
prior approval** from organizers or mentors. Not a fallback to plan around.

Private repo → judges can't review → lower score. Stated explicitly.

---

## 5. Prizes and terms

| Place | Prize |
|---|---|
| 1st | $2,500 + $300 Featherless credits |
| 2nd | $1,500 |
| 3rd | $1,000 |
| Social engagement (2 teams) | $500 per team + 1-month Algo Trader Plus per member |

Terms: 18+. Excludes Alpaca employees/contractors/family/household and sanctioned
countries. **Prizes paid to individuals, not teams** — one member is designated to
receive the full amount, or a split is confirmed with Finance in advance. Requires W-9
(US) or W-8BEN (non-US), government photo ID, bank details. Paid within 90 days of event
end after documents clear and sanctions screening. **Non-US payments generally subject to
30% US withholding unless a valid treaty claim is made on the W-8BEN** — India has a US
tax treaty, so the W-8BEN matters. Winners must complete documentation within 90 days or
forfeit. Judging is final. Alpaca may use winner name, likeness and project for publicity.

---

## 6. Judges, mentors, speakers

| Name | Role |
|---|---|
| Pawel Czech | CEO, NativelyAI |
| Chiranjeev Shah | Technical Content Marketing Associate, Alpaca |
| Tony Lee | Chief Brokerage Officer, Alpaca |
| Grace Gao | Product Manager, Alpaca |
| Brandon Meyerowitz | Team Lead, Trading API, Alpaca |

Composition reads as three people who will judge whether the API was used well and
whether the trading logic is sane (Meyerowitz, Lee, Gao), one who will judge the story
and its shareability (Shah), one outside-partner CEO (Czech). Interpretation, not fact.

---

## 7. Alpaca technical surface

### Trading API
Paper base URL `https://paper-api.alpaca.markets`. Market data `https://data.alpaca.markets`.
Every response carries an `X-Request-ID` header — persist recent ones for support.

### MCP server
`uvx alpaca-mcp-server`. Requires Python 3.10+ and `uv`. 65 tools across Trading and
Market Data APIs. Config is env vars in the MCP client block.

| Variable | Required | Default |
|---|---|---|
| `ALPACA_API_KEY` | yes | — |
| `ALPACA_SECRET_KEY` | yes | — |
| `ALPACA_PAPER_TRADE` | no | `true` |
| `ALPACA_TOOLSETS` | no | all |

Toolsets: `account`, `trading`, `watchlists`, `assets`, `stock-data`, `crypto-data`,
`options-data`, `corporate-actions`, `news`, `fixed-income-data`, `index-data`.

Options tools specifically: `get_option_chain`, `get_option_snapshot` (Greeks and IV),
`get_option_bars`, `get_option_trades`, `get_option_latest_quote`,
`get_option_latest_trade`, `get_option_exchange_codes`, `place_option_order`
(single-leg or multi-leg), `get_option_contracts`, `get_option_contract`,
`exercise_options_position`, `do_not_exercise_options_position`.

Claude Code install line from the docs:
```
claude mcp add alpaca --scope user --transport stdio uvx alpaca-mcp-server \
  --env ALPACA_API_KEY=your_alpaca_api_key \
  --env ALPACA_SECRET_KEY=your_alpaca_secret_key
```
V2 is **not** a drop-in replacement for V1 — tool names and parameters changed.

### CLI — `alpacahq/cli`, Apache 2.0, labelled **Alpha Preview** (flags and output formats
may change between releases)
Install: `go install github.com/alpacahq/cli/cmd/alpaca@latest` or
`brew install alpacahq/tap/cli`. Verify with `alpaca version` / `alpaca doctor`.
Auth: `alpaca profile login` (OAuth, paper) or `--api-key`; env vars `ALPACA_API_KEY`,
`ALPACA_SECRET_KEY`, `ALPACA_LIVE_TRADE`, `ALPACA_PROFILE`, `ALPACA_OUTPUT`,
`ALPACA_CONFIG_DIR`. Credentials stored at `~/.config/alpaca/profiles/` mode 0600.

Agent-relevant features: no confirmation prompts, structured JSON errors on stderr, exit
codes 0 success / 1 error / 2 auth failure, automatic retry on 429/5xx (max 3, respects
`Retry-After`), `--dry-run` order preview, `--schema` to inspect response shapes without
an API call, `--quiet`, built-in `--jq`, `--client-order-id` for idempotent orders (≤128
chars; API rejects duplicates, which prevents double-fills in retry logic).

Options commands: `alpaca option contracts --underlying-symbol AAPL`,
`alpaca option get --symbol-or-id ...`, `alpaca option exercise`,
`alpaca option do-not-exercise`, `alpaca data option chain --underlying-symbol AAPL`,
`alpaca data option snapshot --symbol ...`, `alpaca data option latest-quotes --symbol ...`.

### CLI vs MCP — Alpaca's own framing
CLI: one command per call then exits, minimal context cost, pipes into scripts/cron/CI,
no AI host needed. Best for scripts, cron, CI, focused agent actions.
MCP: background process for a whole session, full tool schemas in the context window,
returns through MCP to the model. Best for long-lived AI sessions and multi-tool
orchestration.

### SDKs
Python `alpaca-py` (`pip install alpaca-py`), Node
`@alpacahq/alpaca-trade-api`, Go `alpaca-trade-api-go/v3`, C# `Alpaca.Markets`, Java
`alpaca-java`. OpenAPI specs at `docs.alpaca.markets/openapi/{broker,trading,market-data}-api.json`.

### Doc navigation
Full index at `https://docs.alpaca.markets/us/llms.txt`. **Append `.md` to any docs page
URL to get markdown** — cheap way to read docs without burning tokens on HTML.

### Repos given as developer tools
- `https://github.com/alpacahq/alpaca-skills.git` ← Alpaca-authored Claude skills
- `https://github.com/alpacahq/alpaca-mcp-server.git`
- `https://github.com/alpacahq/cli.git`
- `https://github.com/alpacahq/alpaca-py.git`
- `https://github.com/alpacahq/alpaca-trade-api-js.git`

### Stated constraints from Alpaca's own docs
- Rate limits per account; high-frequency querying may trigger limiting.
- **"Some real-time data may require an Algo Trader Plus subscription."** ← unresolved,
  see §9.
- Orders execute directly against the Trading API; no confirmation dialogs in CLI.

---

## 8. Partners and credits

**Featherless AI** — serverless inference for open-source models. $25 per participant,
first-come first-served, pay-per-request until credits run out. **Abhi has already
claimed these.**

**NativelyAI** — partner; its CEO Pawel Czech is on the speakers/mentors/judges list.
Brief says "another partner is Natively.ai — if useful do use it properly."

**Alpaca** — lead partner. Securities via Alpaca Securities LLC, crypto via Alpaca Crypto
LLC.

---

## 9. Open risks and unverified items

- **Options market data on a free paper account.** The MCP docs advertise Greeks and IV
  via `get_option_snapshot`, but Alpaca also warns some real-time data needs Algo Trader
  Plus. Whether free-tier options quotes are real-time, delayed, or restricted is **not
  established from these documents** and directly determines what strategies are even
  possible. Must be verified against live API before strategy is fixed.
- **P&L window is tiny.** With the deadline at 11:00 AM ET Friday Sep 4, live trading
  days remaining are Tue Sep 1, Wed Sep 2, Thu Sep 3 and ~90 minutes of Fri Sep 4. Three
  and a half sessions of options P&L is dominated by variance, not skill.
- **The fresh-account rule interacts badly with the short window.** The judged account
  must be new, so trading history can only start once it exists.
- **CLI is Alpha Preview** — behaviour may change without notice.
- **Abhi's existing paper account** (created, 2FA set up, unused) is almost certainly not
  usable as the judged account under the fresh-account rule. Fine for development.
- **Team structure unresolved.** Abhi and a friend, friend pursuing his own approach.
  Whether that is one lablab team with two projects' worth of effort, or two separate
  teams, changes what gets submitted and under whose account.
- **Options level / approval on paper accounts.** Multi-leg strategies may require a
  higher options trading level even in paper. Not covered in the supplied docs.

---

## 10. lablab platform mechanics (from the guidance docs)

Enroll → screening form → approval email within 24h → connect Discord (mandatory before
team creation) → create or join team → build → submit from the team page.

Mentors: "Calling for help" button on the team page, or `#ineedhelp` on Discord tagging
`@Mentor`. Team Discord channel is private to the team and the mentor team. There is a
Labs section with mentors from partner companies for technology-specific questions.

Generic lablab advice worth keeping (the rest of those five documents is boilerplate):
judges check that GitHub commits are spread across the event window rather than one final
push; a demo that only runs locally scores as if it doesn't work; keep the demo path to
three screens or fewer; suggested video shape is problem → live demo → business case →
team/roadmap.

---

## 11. Abhi's environment (from the two PDFs)

Windows + WSL Ubuntu, projects in `~/NewProjects/`. Claude Code default, Antigravity
free/parallel, OpenCode for disconnect-proof sessions. Coordination is git + SESSION-LOG.md,
one agent per worktree.

Claude Code skills that will matter here: `office-hours`, `research-round`,
`competition-mode`, `demo-ready`, `ship-safely`, `genai-project`, `frontend-work`,
`hallmark`, `writing-not-slop`, `playwright-cli`, `engineering-standards`,
`loop-engineering`, `token-discipline`, `context-compression`.

Free-tier traps flagged in the setup docs that apply here: Supabase free projects
auto-pause after 7 days idle; Routines capped at 5 runs/day on Pro with a 1-hour minimum
interval; Gemini free tier ~20 req/day on some models.

Routines are the natural fit for an agent that must trade unattended across three days —
but 5 runs/day and a 1-hour floor is a hard ceiling on how often an Anthropic-hosted
routine can act. Local scheduling (cron in WSL) has no such cap but requires the machine
to be on.
