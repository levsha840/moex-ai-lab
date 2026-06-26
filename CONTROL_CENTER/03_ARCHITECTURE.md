# 03_ARCHITECTURE — MOEX AI LAB

## Слои системы

```text
configs/
infrastructure/
core/db/
core/features/
core/replay/
core/strategy/
core/execution/
core/analytics/
services/
tests/
CONTROL_CENTER/
```

## v1.3 Replay Engine

Добавлен слой:

```text
core/replay/
├── __init__.py
└── replay_engine.py
```

Назначение:

- принимает список свечей;
- сортирует данные по `ticker`, `ts`;
- проигрывает историю шаг за шагом;
- хранит позицию replay;
- возвращает `ReplayEvent`;
- поддерживает warmup history;
- опционально подключает `FeatureFactory`.

## Поток данных

```text
candles_intraday
    ↓
IntradayRepository
    ↓
FeatureFactory
    ↓
ReplayEngine
    ↓
Strategy Runtime / Backtest / AI Learning
```

## Принцип

Replay должен быть детерминированным: одинаковые входные свечи дают одинаковую последовательность событий.
