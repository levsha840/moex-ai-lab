# 03_ARCHITECTURE — MOEX AI LAB

## Архитектурные слои

## Data Layer

- PostgreSQL/TimescaleDB.
- Исторические и intraday-таблицы.
- `core/db/postgres.py` — подключение к БД.
- `core/db/intraday_repository.py` — доступ к минутным свечам.

## Feature Layer

Новый слой релиза `v1.2`:

```text
core/features/
├── __init__.py
├── technical_indicators.py
└── feature_factory.py
```

Назначение:

- преобразование OHLCV-свечей в набор признаков;
- расчет технических индикаторов;
- подготовка данных для replay, стратегий и AI-моделей;
- отсутствие жесткой зависимости от pandas/numpy на раннем этапе.

## Strategy Layer

- Базовые стратегии находятся в `core/strategy`.
- Стратегии должны получать уже подготовленные данные, а не рассчитывать признаки внутри себя.

## Replay / Analytics Layer

- Replay использует исторические данные и стратегии.
- Следующий этап — подключение Feature Factory к replay/dataset pipeline.

## Принцип

Сырые данные, признаки, стратегии и исполнение должны оставаться разными слоями.
