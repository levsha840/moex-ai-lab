# PATCH v1.3 — Replay Engine

## Что входит

- `core/replay/replay_engine.py` — deterministic replay свеча-за-свечой.
- `core/replay/__init__.py` — публичный экспорт replay-модуля.
- `tests/test_replay_engine.py` — unit-тесты Replay Engine.
- `pytest.ini` — обычный `python -m pytest` теперь запускает только `tests/`.
- `services/data_collector/app/test_tinvest.py` — старый T-Invest check больше не ломает общий тестовый прогон.
- `requirements.txt`, `requirements-dev.txt`, `requirements-lock.txt` — нормализация зависимостей.
- `CONTROL_CENTER/*` — обновление состояния проекта.

## Проверка

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pytest tests/test_replay_engine.py
python -m pytest tests/test_intraday_repository.py tests/test_feature_factory.py tests/test_replay_engine.py
```

## Если всё зелёное

```powershell
git status
git add .
git commit -m "v1.3 Replay Engine"
git push
```
