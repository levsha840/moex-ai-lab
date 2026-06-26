# 06_SESSION_START — MOEX AI LAB

## Start Procedure
1. Open VS Code in `D:\MOEX_AI`.
2. Run `git status`.
3. Confirm working tree state.
4. Read this file and `01_PROJECT_STATE.md`.
5. Continue from the active release in `02_ROADMAP.md`.

## Current Session Target
Complete v1.1 Intraday Data Layer.

## Commands
```powershell
git status
.\scripts\apply_intraday_schema.ps1
python -m pytest tests/test_intraday_repository.py
```
