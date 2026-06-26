# 02_ROADMAP — MOEX AI LAB

## Статус релизов

- `v1.0 Foundation` — завершено.
- `v1.1 Intraday Data Layer` — завершено.
- `v1.2 Feature Factory` — завершено.
- `v1.3 Intraday Dataset Builder / Replay Integration` — следующий этап.
- `v1.4 Strategy Engine Upgrade` — план.
- `v1.5 Paper Trading Integration` — план.
- `v1.6 Portfolio Manager` — план.
- `v1.7 AI Learning Loop` — план.
- `v2.0 Autonomous Trader` — целевой крупный релиз.

## v1.2 Feature Factory — результат

Создан слой подготовки признаков из OHLCV-свечей:

- SMA;
- EMA;
- RSI;
- ATR;
- close return;
- volume change;
- intrabar return;
- range percentage;
- rolling volatility;
- относительное положение close к SMA/EMA.

## v1.3 — следующий релиз

Задачи:

1. Создать builder датасетов из `candles_intraday`.
2. Подключить Feature Factory к intraday-репозиторию.
3. Подготовить формат обучающего датасета для AI.
4. Добавить smoke-тест pipeline: DB → Repository → FeatureFactory → Dataset.
5. Обновить `CONTROL_CENTER`.
