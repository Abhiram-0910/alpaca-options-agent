# SETUP.md — run once, then delete this file

## 1. Git

The code already exists at `github.com/Sairishwanth89/alpaca_software` with 5 commits.
Do **not** start a second repo — judges look at commit history, and splitting it halves what
they see. Get collaborator access on that repo instead.

- [ ] Collaborator access granted on `Sairishwanth89/alpaca_software`
- [ ] `git remote -v` shows that repo
- [ ] `.gitignore` covers `.env`, `logs/`, `__pycache__/`, `.code-review-graph/`

## 2. Code knowledge graph

Lets Claude read only the files a change affects. Roughly 6–7x context compression.

```bash
code-review-graph build
code-review-graph status
```

- [ ] Graph built

## 3. Alpaca skills

The sponsor's own definition of a correct agentic trading workflow. Judges wrote it.

```bash
npx skills add alpacahq/alpaca-skills
```

- [ ] Installed

## 4. Second agent (optional but recommended here)

Submission materials are entirely undone and don't touch `agent/`. Split them out:

```bash
git worktree add ../alpaca-submission -b submission-materials
```

- [ ] Worktree created, or decided single-agent

## 5. Environment

Use `uv`, not `python3 -m venv` — on this box (WSL Ubuntu, Python 3.14.4) the stdlib venv's
`ensurepip` step fails and leaves a venv with no `pip` in it.

```bash
uv venv --python 3.14 .venv
uv pip install -r requirements.txt
uv tool install alpaca-mcp-server   # warms the cache; otherwise the first
                                     # uvx spawn downloads mid-cycle
```

Then run everything through `.venv/bin/python` (or activate the venv).

```bash
cp .env.example .env
```

- [ ] `.env` has the **fresh** paper account's keys, not the old one's
- [ ] `ALPACA_PAPER_TRADE=true`
- [ ] `.env` is gitignored, no key in any tracked file

## 6. Fresh paper account

At **app.alpaca.markets** → Paper Trading → account dropdown → **Create New Account**.
Set the starting balance to exactly **$100,000**. Generate new API keys for it (creating an
account invalidates old ones). Record the account ID — it goes on the submission form.

- [ ] Fresh account created, funded at $100,000
- [ ] New keys in `.env`
- [ ] Account ID recorded in `TODO.md`

## 7. Docs

- [ ] `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `TODO.md`, `SESSION-LOG.md` in the repo root
- [ ] `RESEARCH.md` and `COMPETITION-BRIEF.md` in `docs/`

## Alpaca CLI (read path)

The dashboard export reads account and positions through Alpaca's CLI
(`alpacahq/cli`), falling back to alpaca-py when the binary is absent. Order
placement does not use it — that stays on the MCP server.

Prebuilt binary, no Go toolchain:

```bash
V=0.0.14
curl -sLO https://github.com/alpacahq/cli/releases/download/v$V/cli_${V}_linux_amd64.tar.gz
curl -sLO https://github.com/alpacahq/cli/releases/download/v$V/checksums.txt
grep linux_amd64 checksums.txt | sha256sum -c -
tar xzf cli_${V}_linux_amd64.tar.gz alpaca && install -m755 alpaca ~/.local/bin/alpaca

alpaca profile login --api-key --paper --key "$ALPACA_API_KEY" --secret "$ALPACA_SECRET_KEY"
alpaca doctor                    # should report both APIs connected
python agent/alpaca_cli.py       # self-check
```

Note: `ALPACA_API_KEY` in the environment overrides the stored profile on every
command. That is fine here — same paper credentials either way — but it means a
live key in the environment would be used, so keep `.env` paper-only.
