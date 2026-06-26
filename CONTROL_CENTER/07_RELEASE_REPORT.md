# 07_RELEASE_REPORT — MOEX AI LAB

## v1.1 Intraday Data Layer

### Objective
Create the intraday data foundation for minute/smaller timeframe OHLCV storage and access.

### Deliverables
- TimescaleDB schema for `candles_intraday`.
- Repository for batch upsert and reads.
- Unit tests.
- Operational apply script.

### Acceptance Criteria
- SQL schema applies without error.
- Table `candles_intraday` exists.
- Unit tests pass.
- Existing platform tests pass.
- Git commit created after validation.

### Status
Prepared, awaiting local validation.
