# 05_TODO

MOEX AI LAB — актуальное состояние после релиза v1.7 Risk Engine.

## Выполнено в v1.7

- [x] `core/risk/models.py` — доменные модели RiskEngine
- [x] `core/risk/engine.py` — RiskEngine с проверками лимитов
- [x] `core/risk/__init__.py` — публичный API пакета
- [x] Интеграция RiskEngine в PaperTradingEngine
- [x] 9 тестов Risk Engine
- [x] Исправлен packaging: `tests/persistence/__init__.py`
- [x] Обновлён CONTROL_CENTER до v1.7

## Следующий релиз: v1.8

### Обязательно

- [ ] Реализовать `PostgresPositionRepository` (заглушка с v1.6.1)
- [ ] Интеграционный тест: `ReplayEngine → StrategyEngine → RiskEngine → PaperTradingEngine`
- [ ] Дневные лимиты риска в RiskEngine

### Технический долг

- [ ] Определить судьбу `core/portfolio/` (старый слой, существует параллельно с `core/position/`)
- [ ] Связать `PaperTradingEngine.PaperPosition` с `PositionManager.Position`
- [ ] Исправить коллизию номеров миграций (два файла `002_*.sql`, два `003_*.sql`)
- [ ] Перевести `tests/test_broker_safety.py` в pytest-функции
