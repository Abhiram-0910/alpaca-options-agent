# AGENTS.md

Cross-tool rules for the Alpaca options agent. Read by Antigravity, OpenCode and other
AGENTS.md-aware agents at session start. Standing rules only — session history lives in
`SESSION-LOG.md`.

---

## Stack

Python 3.10+ · alpaca-py (historical data and market clock only) · Alpaca MCP server
launched via `uvx alpaca-mcp-server` (every trading and live-data operation) · Anthropic and
OpenAI SDKs for the reasoning layer.

## Commands

```
setup:      python setup.py
backtest:   python run_backtest.py
dry run:    python main.py --deterministic
one cycle:  python main.py --once
multi:      python main.py --multi-agent --once
manage:     python main.py --manage-only
kill:       python kill_switch.py on | off | status
```

## Conventions

- Trading and live market data go through the MCP client only. `alpaca-py` is for offline
  backtest data pulls and the market clock — never for a trading action.
- Alpaca response envelopes are unwrapped through `agent/mcp_parsers.py`. Do not hand-roll
  another copy; there are already ~10 duplicates to remove, not add to.
- Strategy dispatch belongs in `agent/strategies/lifecycle.py`'s registry, not another
  hand-rolled if/elif chain.
- Every validation result, pass or fail, is appended to `docs/strategy_graveyard.md`.

## Deny rules

- Never place an order that bypasses `RiskGate.check()`.
- Never set `ALPACA_PAPER_TRADE` to anything but true.
- Never let an LLM compute a number that reaches an order.
- Never commit `.env` or any file containing a key.
- Never delete or rewrite a FAIL entry in the graveyard.
- Never add AI-attribution trailers to commit messages.
- Never present a backtest number produced before the block-bootstrap fix as validated.

## Files not to touch

- `docs/strategy_graveyard.md` — append-only, written by code.
- `logs/` — generated.

## Multi-agent

More than one agent may work this project. Before starting:

1. Read `SESSION-LOG.md` for what's in progress and who is doing it.
2. Work on a separate git worktree or branch — never share a working tree.
3. Record what you did in `SESSION-LOG.md`, including which agent you are.

Current split: Claude Code owns `agent/` (code and fixes). A second agent owns
`submission/` (video script, slides, one-page write-up). They do not overlap.

## Skills and tools

- Alpaca's own skills: `npx skills add alpacahq/alpaca-skills` — the sponsor's written
  definition of a correct agentic trading workflow. Follow its reporting format.
- Knowledge graph: `code-review-graph build` once per project, then query it to narrow scope
  before reading files.
- MCP config: `.mcp.json`
