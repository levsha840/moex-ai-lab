# 01_PROJECT_STATE

MOEX AI LAB — актуальное состояние после v2.0 Validation Report.

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
- v1.8 Minimal Portfolio Allocation Engine — завершен.
- v1.9.1 Execution Cost Model — завершен.
- v1.9.2 WalkForward Window Generator — завершен.
- v1.9.3 WalkForward Engine — завершен.
- v1.9.4 Architecture Cleanup — завершен.
- v2.0 Validation Report — завершен.

## Текущий статус тестов

122/122 passed.

## v2.0 Validation Report

Реализован первый компонент Validation Core — сборка результатов валидации в единый отчёт:

- `ValidationStatus` (PASS / FAIL);
- `ValidationMetric` — именованная числовая метрика;
- `ValidationReport` — статус, список метрик, счётчики окон, pass_rate, notes;
- `ValidationReportBuilder.build(summary, evaluator)` — итерирует `WalkForwardSummary`, применяет `evaluator` к каждому результату, вычисляет pass_rate;
- порог PASS: `pass_rate >= 0.80` (захардкодирован);
- автоматические метрики: `pass_rate`, `windows_total`, `windows_passed`, `windows_failed`;
- пояснение "Insufficient pass rate" при FAIL;
- Validation Core полностью независим: нет импортов PaperTrading, ReplayEngine, Broker, Database, PositionManager;
- 13 новых тестов (122 итого).

## v1.9.4 Architecture Cleanup

Удалены legacy-модули, не используемые pipeline:

- `core/execution/replay_execution_engine.py`;
- `core/risk/risk_manager.py`;
- `core/strategy/base.py` (старый generate_signal base);
- `core/strategy/registry.py` (старый StrategyRegistry);
- `core/portfolio/` (ghost layer, не использовался);
- 4 скрипт-файла в `tests/` (main()-паттерн, не pytest-тесты).

Унификации:

- `PositionSide` — единственная дефиниция в `core/position/models.py`, убран дубликат с FLAT из `core/strategy/signal.py`;
- `OrderSide(str, Enum)` в `core/common.py` заменил `side: str` в `RiskCheckRequest` и `ExecutionRequest`; `PaperOrderSide` стал алиасом.

Demo-стратегии (RSI/SMA) переписаны на новый `BaseStrategy` + `on_event` API.

## v1.9.3 WalkForward Engine

Реализован generic runner поверх `WalkForwardWindowGenerator`:

- `WalkForwardRunResult(window, result)` — результат одного окна;
- `WalkForwardSummary(runs)` — сводка по всем окнам;
- `WalkForwardEngine.run(data_length, runner)` — принимает `Callable[[WalkForwardWindow], Any]`, исключения propagate без подавления.

## v1.9.2 WalkForward Window Generator

Реализован детерминированный генератор rolling-окон:

- `WalkForwardConfig(train_size, test_size, step_size, min_train_size)` — валидация в `__post_init__`;
- `WalkForwardWindow` — полуоткрытые интервалы `[start, end)`;
- `WalkForwardWindowGenerator.generate(data_length)` — возвращает список окон без перекрытий.

## v1.9.1 Execution Cost Model

Реализован детерминированный движок расчёта издержек исполнения:

- `ExecutionCostConfig` — commission_rate, minimum_commission, spread_bps, slippage_bps;
- `ExecutionRequest / ExecutionResult` — модели запроса и результата;
- `ExecutionCostEngine.calculate()` — gross, commission, spread, slippage, total_cost, effective_price для BUY/SELL.

## v1.8 Minimal Portfolio Allocation Engine

Реализован детерминированный слой распределения капитала:

- `AllocationConfig` — пять лимитов: max_position_pct, max_strategy_pct, max_correlated_pct, cash_buffer, rebalance_threshold;
- `AllocationRequest / AllocationDecision` — модели;
- `AllocationDecisionType`: ALLOCATE, REDUCE, REJECT;
- `PortfolioAllocationEngine.allocate()` — детерминированный расчёт без доступа к БД.

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

v2.1 — Market Regime Engine:

- `RegimeType` — перечень рыночных режимов;
- `RegimeClassifier` — детерминированный классификатор без AI и ML;
- `RegimeReport` — результат классификации;
- без доступа к БД;
- независимый deterministic engine.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
