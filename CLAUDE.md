# MOEX AI LAB — Claude Code Project Rules

## Automation Constraints (HARD RULES)

### Git Operations
**NEVER** run `git add`, `git commit`, `git push`, `git reset --hard`, `git checkout --` automatically.

Git write operations are **BLOCKED** at the permission level (`settings.local.json`) and must only happen when the user **explicitly asks** ("commit this", "push to remote").

Allowed without asking: `git status`, `git log`, `git diff`, `git branch` (read-only).

### Research Factory Automation
The following scripts run **fully unattended** and must never block on user input:
- `scripts/night_run.py` — overnight 42-cell research run
- `scripts/run_lab.py` — operational research + paper trading session
- `scripts/autonomous_research_alpha.py` — IE pipeline runner
- `scripts/campaign_scheduler.py` — wave plan generator

These scripts **never** do: `git add / git commit / git push / git push`.
They **only** do: read datasets, run Research Service, write JSON/MD reports, update Knowledge Base.

### Live Trading
**NEVER** set `MOEX_ENABLE_LIVE_TRADING=true` or `T_INVEST_EXECUTE=true`.
Live trading is blocked at the SafetyGuard level. Do not suggest enabling it.

## Working Directories
- Backend: `D:/MOEX_AI/` — Python, agents, services. **Never modify Research Service or Agent Protocol.**
- Frontend: `D:/MOEX_AI/terminal/frontend/` — React/TypeScript/Vite.

## What Claude Can Do Autonomously (no confirmation needed)
- Run Python research scripts: `python scripts/night_run.py`, `python scripts/run_lab.py`
- Read files, edit frontend code, run tests
- Update reports and artifacts under `docs/`, `ie_reports/`, `knowledge/`

## What Requires Explicit User Instruction
- `git commit` — only on explicit "commit this"
- `git push` — only on explicit "push"
- Any change to `services/research/`, `agents/` Python source
- Any change to backend FastAPI code
