# 04_CHANGELOG — MOEX AI LAB

## v1.3 Replay Engine

Добавлено:

- `core/replay/replay_engine.py`.
- `ReplayConfig`.
- `ReplayEvent`.
- `ReplayState`.
- `ReplayEngine.step()`.
- `ReplayEngine.run()`.
- `ReplayEngine.window()`.
- Интеграция с `FeatureFactory` через callback.
- `tests/test_replay_engine.py`.
- `pytest.ini`.
- `requirements.txt`.
- `requirements-dev.txt`.
- `requirements-lock.txt`.

Изменено:

- Старый T-Invest integration check больше не блокирует общий pytest.
- Основной запуск тестов ограничен папкой `tests/`.

## v1.2 Feature Factory

Добавлен слой генерации технических признаков.

## v1.1 Intraday Data Layer

Добавлен слой хранения и доступа к intraday-свечам.
