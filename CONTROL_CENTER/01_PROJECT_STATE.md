# 01_PROJECT_STATE — MOEX AI LAB

## Текущее состояние

Текущий завершенный релиз: **v1.2 Feature Factory**.

## Готово

- Базовая платформа MOEX AI LAB.
- Strategy Catalog / Registry.
- Replay-инфраструктура.
- PostgreSQL/TimescaleDB слой.
- `v1.1 Intraday Data Layer`:
  - таблица `candles_intraday`;
  - SQL-схема `infrastructure/intraday_schema.sql`;
  - репозиторий `core/db/intraday_repository.py`;
  - тесты репозитория.
- `v1.2 Feature Factory`:
  - модуль `core/features`;
  - технические индикаторы SMA, EMA, RSI, ATR;
  - признаки доходности, объема, диапазона и волатильности;
  - фабрика признаков `FeatureFactory`;
  - тесты Feature Factory.

## Текущий фокус

Следующий релиз: **v1.3 Intraday Dataset Builder / Replay Integration**.

Цель следующего релиза — связать intraday-данные и Feature Factory с дальнейшим replay/AI pipeline.

## Правило актуальности

Папка `CONTROL_CENTER` является единственным источником актуального состояния проекта.
После каждого завершенного релиза документы должны проверяться и обновляться.
