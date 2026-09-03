# Tonight — 3 Sep 2026. Read top to bottom, paste one block at a time.

`python` is NOT on PATH in this shell. Every command uses `.venv/bin/python`. Run
everything from `/home/abhi/NewProjects/alpaca`.

| IST | ET | What |
|---|---|---|
| 19:00 | 09:30 | Market opens |
| 00:30 (Fri) | 15:00 | **Entries stop.** Gate refuses all new positions |
| 01:15 (Fri) | 15:45 | **Must be flat.** Loop closes the book itself |
| 01:30 (Fri) | 16:00 | Market closes |

**Abort at any time:**
```bash
.venv/bin/python kill_switch.py on "manual abort" --cancel-all
```

---

## STEP 1 — 18:50 IST · Pre-flight

```bash
cd /home/abhi/NewProjects/alpaca && .venv/bin/python main.py --preflight
```

Want: `12 green, 0 warn, 0 red — READY`. **Any RED: stop and do not start the loop.**

---

## STEP 2 — 18:55 IST · Start the supervised loop, unattended

```bash
cd /home/abhi/NewProjects/alpaca && \
nohup .venv/bin/python main.py --loop --multi-agent --interval 15 --max-spend 5.00 \
  > logs/loop.out 2>&1 &
echo "loop PID $!" | tee logs/loop.pid
```

Confirm it is alive (wait ~1 min after starting):
```bash
cd /home/abhi/NewProjects/alpaca && tail -20 logs/loop.out
```

Want a line like `[cycle 1] ran a full cycle` or `[cycle 1] declined: market closed`.
It sleeps outside market hours, wakes itself, and writes a heartbeat every pass.
It stops itself on 3 consecutive failures and trips the kill switch.

---

## STEP 3 — 19:05 IST · Fire the demonstration order

Do this **after** the open. Not before — options are regular-hours only.

Dry run first. It changes nothing:
```bash
cd /home/abhi/NewProjects/alpaca && \
DEMONSTRATION_MODE=true .venv/bin/python main.py --demonstrate
```

Read the `decision` block. Want `"approved": true` and
`estimated_capital_at_risk` around **$415–435**. If it says `rejected`, stop and read the
reason — do not re-run hoping for a different answer.

Then submit, for real:
```bash
cd /home/abhi/NewProjects/alpaca && \
DEMONSTRATION_MODE=true .venv/bin/python main.py --demonstrate --submit
```

Want: `SUBMITTED — this is an unvalidated demonstration, not an edge claim.`
This mode places **one** order, ever. Running it twice will not place a second.

---

## STEP 4 — 19:10 IST · Confirm the fill

```bash
cd /home/abhi/NewProjects/alpaca && export PATH="$HOME/.local/bin:$PATH" && \
echo "--- POSITIONS ---" && alpaca position list && \
echo "--- ORDERS ---"   && alpaca order list --status all --limit 3
```

- **Two legs in POSITIONS** → filled. Done, move to Step 5.
- **Order present, `filled_qty: 0`** → resting, not filled yet. Re-run this block in 10 min.
- Still unfilled after ~60 min: the loop's housekeeping cancels stale orders at that age.
  That is intended. If you want it filled, cancel and re-submit at a better price rather
  than waiting.

Fill-vs-feed capture (only meaningful once filled):
```bash
cd /home/abhi/NewProjects/alpaca && .venv/bin/python -c "
import json
rows=[json.loads(l) for l in open('logs/trade_log.jsonl') if l.strip()]
fa=[r for r in rows if r['type']=='fill_analysis']
print(json.dumps(fa[-1], indent=2) if fa else 'no fill_analysis record yet')"
```

---

## STEP 5 — 01:15–01:30 IST · Flatten check

The loop closes the book itself at 15:45 ET. **You are verifying, not doing.**

```bash
cd /home/abhi/NewProjects/alpaca && export PATH="$HOME/.local/bin:$PATH" && \
echo "--- POSITIONS (want empty) ---" && alpaca position list && \
echo "--- OPEN ORDERS (want empty) ---" && alpaca order list --status open && \
echo "--- FLATTEN IN LOG ---" && \
.venv/bin/python -c "
import json
rows=[json.loads(l) for l in open('logs/trade_log.jsonl') if l.strip()]
for r in rows[-200:]:
    if r['type'] in ('session_window_flatten','order_management_cycle_complete','heartbeat'):
        if r['type']=='heartbeat' and 'flat' not in (r.get('action') or ''): continue
        print(r['ts'], r['type'], r.get('reason') or r.get('action') or '')"
```

**If positions are still open after 01:20 IST**, close them yourself:
```bash
cd /home/abhi/NewProjects/alpaca && .venv/bin/python main.py --manage-only
```
Still open after that — close by hand, do not wait:
```bash
cd /home/abhi/NewProjects/alpaca && export PATH="$HOME/.local/bin:$PATH" && \
alpaca position list && echo "^ close each of the above via the Alpaca web UI"
```

Stop the loop once flat:
```bash
cd /home/abhi/NewProjects/alpaca && kill "$(cat logs/loop.pid | grep -o '[0-9]*')" 2>/dev/null; \
echo "loop stopped"; tail -5 logs/loop.out
```

---

## STEP 6 — 01:30 IST · Final export and redeploy

```bash
cd /home/abhi/NewProjects/alpaca && \
.venv/bin/python main.py --export-dashboard && \
.venv/bin/python -c "
from agent.dashboard import export_dashboard
export_dashboard('docs/dashboard.example.json')" && \
git add docs/dashboard.example.json && \
git commit -m 'Final dashboard export after the session' && \
echo "EXPORTED AND COMMITTED"
```

Redeploy (command is from `submission/demo/README.md`, run in the **submission** worktree):
```bash
cd /home/abhi/NewProjects/alpaca-submission && \
cp ../alpaca/logs/dashboard.json submission/demo/data/dashboard.json && \
cd submission/demo && npx vercel --prod --yes
```

Verify it actually went live:
```bash
curl -s --max-time 25 https://demo-sage-seven-13.vercel.app/data/dashboard.json | \
  /home/abhi/NewProjects/alpaca/.venv/bin/python -c "
import json,sys; d=json.load(sys.stdin)
print('schema_version', d['schema_version'], '| generated', d['meta']['generated_at'])
print('trades:', len(d['trades']), '| fills measured:', d['fill_analysis']['legs_filled'])"
```

Want a `generated_at` from tonight and a non-zero `trades` count if the order filled.
