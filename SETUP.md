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
