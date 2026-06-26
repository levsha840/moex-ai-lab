# 07_RELEASE_REPORT — MOEX AI LAB

## v1.3 Replay Engine

### Цель

Создать детерминированный replay-движок для проигрывания исторических intraday-свечей.

### Результат

Добавлен `ReplayEngine`, который:

- принимает исторические свечи;
- сортирует их по инструменту и времени;
- проигрывает по одной свече;
- возвращает `ReplayEvent`;
- поддерживает warmup history;
- может получать признаки от `FeatureFactory`.

### Проверка

Ожидаемые команды:

```powershell
python -m pytest
python -m pytest tests/test_replay_engine.py
```

### Решение

Replay Engine становится базовым слоем для будущих Strategy Runtime, Backtest и AI Learning.
