# 01_PROJECT_STATE

MOEX AI LAB — актуальное состояние после релиза v1.7 Risk Engine.

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

## v1.7 Risk Engine

Реализован независимый детерминированный слой оценки риска перед исполнением заявок:

- доменные модели: `RiskDecision`, `RiskDecisionType`, `RiskReason`, `RiskLimits`, `RiskCheckRequest`;
- `RiskEngine.check()` — возвращает `ALLOW` или `REJECT` с причинами;
- проверка `max_trade_value` — лимит стоимости одной сделки;
- проверка `max_position_value` — лимит стоимости позиции по инструменту;
- проверка `max_position_pct` — лимит позиции как доля портфеля;
- проверка `max_open_positions` — лимит числа одновременно открытых позиций;
- запрет short при `allow_short=False`;
- интеграция с `PaperTradingEngine` через опциональный параметр `risk_engine`;
- отклонённые risk-заявки попадают в `rejected_orders` журнал;
- обратная совместимость: `PaperTradingEngine` без `risk_engine` работает как прежде;
- исправлен packaging тестов (`tests/persistence/__init__.py`);
- тесты Risk Engine (9 тестов).

## Архитектурное правило

`RiskEngine` является чистым детерминированным слоем без доступа к базе данных.
Бизнес-логика не зависит от способа хранения данных — все сервисы работают через интерфейсы Persistence Layer.

## Следующий релиз

v1.8 (планируется):

- PostgreSQL backend для PositionRepository;
- дневные лимиты риска;
- stop-loss и take-profit;
- end-to-end интеграционный тест: ReplayEngine → StrategyEngine → RiskEngine → PaperTradingEngine.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
