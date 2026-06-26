# PATCH v1.4 — Strategy Engine

## Что добавлено

- `core/strategy/signal.py` — единая модель `Signal`, `SignalAction`, `PositionSide`, `OrderIntent`.
- `core/strategy/strategy_context.py` — контекст стратегии на один replay-шаг.
- `core/strategy/base_strategy.py` — новый интерфейс стратегий `BaseStrategy`.
- `core/strategy/strategy_engine.py` — движок запуска стратегий поверх `ReplayEngine`.
- `core/strategy/strategy_registry.py` — новый registry для Strategy Engine.
- `tests/test_strategy_engine.py` — тесты нового слоя.
- `CONTROL_CENTER/*` — документация обновлена до v1.4.

## Проверка

```powershell
python -m pytest tests
python -m pytest tests/test_strategy_engine.py
```

## Коммит

```powershell
git status
git add .
git commit -m "v1.4 Strategy Engine"
git push
```

## Важно

Старые стратегии через `generate_signal(row)` не ломаются: `StrategyEngine` умеет адаптировать их в новый формат `Signal`.
