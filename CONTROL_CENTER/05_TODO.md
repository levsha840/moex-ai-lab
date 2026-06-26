# 05_TODO — MOEX AI LAB

## Текущий статус

v1.3 готов к проверке и коммиту.

## Проверить

- `python -m pytest`
- `python -m pytest tests/test_replay_engine.py`
- `python -m pytest tests/test_intraday_repository.py tests/test_feature_factory.py tests/test_replay_engine.py`

## Следующий релиз: v1.4 Strategy Runtime Layer

- Создать runtime-интерфейс стратегии.
- Подключить стратегию к replay-event.
- Добавить strategy context.
- Добавить signal event.
- Добавить тесты runtime-цикла.

## Позже

- Реальный collector для T-Invest / MOEX ISS.
- Backtest metrics.
- Paper trading loop.
- AI dataset builder.
