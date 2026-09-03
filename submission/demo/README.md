# Alpaca Agent Demo Dashboard

This static dashboard reads the JSON data contract outputted by the agent. 
Because Vercel's deployment respects `.gitignore` and ignores the project's root `logs/` directory, the live dashboard relies on a snapshot stored in `data/dashboard.json`.

## How to refresh and redeploy

When the agent executes a new cycle and updates `logs/dashboard.json`, you must copy the latest export into the `data/` directory and redeploy to Vercel. 

Run this single command from the repository root:

```bash
cp ../alpaca/logs/dashboard.json submission/demo/data/dashboard.json && cd submission/demo && npx vercel --prod --yes
```
