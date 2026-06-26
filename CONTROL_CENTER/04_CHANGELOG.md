# 04_CHANGELOG — MOEX AI LAB

## v1.1 Intraday Data Layer
Status: prepared as patch.

### Added
- `infrastructure/intraday_schema.sql`
- `core/db/intraday_repository.py`
- `tests/test_intraday_repository.py`
- `scripts/apply_intraday_schema.ps1`
- CONTROL_CENTER documentation set.

### Changed
- `.gitignore` normalized for Python, virtual environments, environment files, logs, reports and VS Code.

### Validation
Run:
```powershell
.\scripts\apply_intraday_schema.ps1
python -m pytest tests/test_intraday_repository.py
```
