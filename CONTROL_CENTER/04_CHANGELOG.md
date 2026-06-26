# 04_CHANGELOG — MOEX AI LAB

## v1.2 Feature Factory

Дата: 2026-06-26

### Добавлено

- `core/features/technical_indicators.py`.
- `core/features/feature_factory.py`.
- `core/features/__init__.py`.
- `tests/test_feature_factory.py`.

### Реализовано

- SMA.
- EMA.
- RSI.
- ATR.
- Percentage change.
- Rolling volatility.
- FeatureFactory для OHLCV-свечей.
- Раздельная обработка тикеров.
- Проверка обязательных колонок.

### Проверка

- `python -m pytest tests/test_feature_factory.py`.
- Рекомендуемая регрессия: `python -m pytest tests/test_intraday_repository.py tests/test_feature_factory.py`.

## v1.1 Intraday Data Layer

- Добавлена таблица `candles_intraday`.
- Добавлен SQL-скрипт применения схемы.
- Добавлен `IntradayRepository`.
- Добавлены тесты репозитория.
