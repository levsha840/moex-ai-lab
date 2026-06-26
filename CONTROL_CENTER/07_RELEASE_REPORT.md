# 07_RELEASE_REPORT

MOEX AI LAB — релиз v1.7 Risk Engine.

## Статус релизов

- v1.0 Foundation — завершен.
- v1.1 Intraday Data Layer — завершен.
- v1.2 Feature Factory — завершен.
- v1.3 Replay Engine — завершен.
- v1.4 Strategy Engine — завершен.
- v1.5 Paper Trading Engine — завершен.
- v1.6 Position Manager — завершен.
- v1.6.1 Persistence Layer — завершен.
- v1.7 Risk Engine — завершен.

## v1.7 Risk Engine — что сделано

### Новые файлы

- `core/risk/models.py` — `RiskDecision`, `RiskDecisionType`, `RiskReason`, `RiskLimits`, `RiskCheckRequest`
- `core/risk/engine.py` — `RiskEngine.check()`: детерминированная оценка риска
- `core/risk/__init__.py` — публичный API пакета
- `tests/test_risk_engine.py` — 9 тестов
- `tests/persistence/__init__.py` — fix: packaging тестов

### Изменённые файлы

- `core/paper/engine.py` — интеграция `RiskEngine` (опциональный параметр `risk_engine`)

### Тесты

- Итого: 52 passed, 0 failed.
- Новых тестов: 9.
- Регрессий: 0.

## Архитектурное правило

`RiskEngine` — чистый детерминированный слой без доступа к БД. Подключается к `PaperTradingEngine` опционально. Обратная совместимость сохранена.

## Следующий релиз

v1.8:

- PostgreSQL backend для PositionRepository;
- дневные лимиты риска;
- stop-loss и take-profit;
- end-to-end интеграционный тест полного конвейера.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
