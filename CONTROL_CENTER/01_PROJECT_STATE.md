# 01_PROJECT_STATE — MOEX AI LAB

## Текущий релиз

**v1.3 Replay Engine — завершен после проверки.**

## Состояние платформы

- v1.0 Foundation — завершено.
- v1.1 Intraday Data Layer — завершено.
- v1.2 Feature Factory — завершено.
- v1.3 Replay Engine — добавлен патчем.

## Реализованные компоненты

- PostgreSQL / TimescaleDB infrastructure.
- `candles_intraday` для хранения intraday OHLCV.
- `IntradayRepository` для доступа к intraday-данным.
- `FeatureFactory` для технических признаков.
- `ReplayEngine` для детерминированного проигрывания свечей.
- Unit-тесты для ключевых модулей.

## Рабочее окружение

- Python: 3.12.x.
- Режим запуска: `.venv`.
- Основная команда проверки: `python -m pytest`.
- GitHub: основной источник кода.

## Правило

`CONTROL_CENTER` — единственный источник актуального состояния проекта. После каждого завершенного этапа документы проверяются и обновляются.
