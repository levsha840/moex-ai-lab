# 03_ARCHITECTURE — MOEX AI LAB

## Core Principles
- CONTROL_CENTER is the project state source of truth.
- Database access is isolated inside repository modules.
- Market data storage and strategy execution must stay decoupled.
- Live trading must remain disabled unless explicitly enabled by configuration.

## Current Architecture

```text
configs/                 runtime examples and config files
core/                    platform core
  db/                    database access
  strategy/              strategy abstractions and registry
  execution/             replay execution
  analytics/             metrics and reports
infrastructure/          SQL schemas
scripts/                 PowerShell operational scripts
tests/                   automated tests
CONTROL_CENTER/          project state and governance
```

## v1.1 Intraday Data Layer

### Database
Table: `candles_intraday`
- time-series OHLCV data
- primary key: `(time, ticker, timeframe, source)`
- TimescaleDB hypertable by `time`

### Python API
Module: `core/db/intraday_repository.py`
- `IntradayCandle` dataclass
- `IntradayRepository.upsert_many()`
- `IntradayRepository.get_range()`
- `IntradayRepository.get_latest()`

## Next Architecture Step
v1.2 will add feature-building modules on top of `IntradayRepository`.
