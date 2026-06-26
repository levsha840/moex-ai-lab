# 01_PROJECT_STATE — MOEX AI LAB

## Current Release
- Active release: v1.1 Intraday Data Layer
- Status: in progress
- Source of truth: CONTROL_CENTER

## Current Baseline
- v1.0 Foundation is treated as existing baseline.
- Git working tree must be clean before applying release patches.
- PostgreSQL/TimescaleDB runs in Docker container `moex_postgres`.

## Implemented Areas
- Core package structure.
- Strategy registry and sample strategies.
- Replay scripts and analytics foundation.
- Database connection layer in `core/db/postgres.py`.

## v1.1 Scope
- Add `candles_intraday` TimescaleDB table.
- Add `IntradayRepository` for insert/update and read operations.
- Add unit tests for repository behavior.
- Add script for applying intraday schema.

## Operational Rule
After each completed release or major stage, update all CONTROL_CENTER documents if their content changed.
