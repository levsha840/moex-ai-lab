# 01_PROJECT_STATE

MOEX AI LAB — актуальное состояние после Architecture Refresh.

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
- Architecture Refresh — завершен.

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

## Architecture Refresh

Принята Platform Vision 2.0. Платформа переориентирована с набора стратегий на четыре инженерных контура:

- **Production Core** — детерминированное исполнение: StrategyEngine → PortfolioAllocationEngine → RiskEngine → PaperTradingEngine.
- **Validation Core** — обязательный шлюз перед допуском стратегии: WalkForward + Cost Model + PASS/FAIL.
- **Research Core** — генерация и проверка гипотез (не имеет доступа к Production).
- **Operations Core** — supervision работающих стратегий: деградация, drawdown, audit trail.

Новые документы: `05_SYSTEM_VISION.md`, `10_ARCHITECTURE_DECISIONS.md`.

Текущие стратегии (RSI/SMA) признаны демонстрационными — не кандидаты для торговли.

## Архитектурное правило

Все core engines (`ReplayEngine`, `StrategyEngine`, `RiskEngine`, `PaperTradingEngine`) — детерминированные объекты без доступа к БД. Бизнес-логика работает только через интерфейсы Persistence Layer.

## Следующий релиз

v1.8 — Minimal Portfolio Allocation Engine:

- `core/allocation/` — новый детерминированный слой;
- `AllocationConfig`, `AllocationLimits`, `AllocationRequest`, `AllocationDecision`;
- `AllocationDecisionType`: `ALLOCATE`, `REDUCE`, `REJECT`;
- базовые лимиты: `max_position_pct`, `max_strategy_pct`, `max_correlated_pct`, `cash_buffer`, `rebalance_threshold`;
- unit tests;
- без Kelly, Markowitz, AI allocation.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
