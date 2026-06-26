# 04_CHANGELOG

MOEX AI LAB — актуальное состояние после релиза **v2.0 Validation Report**.

---

## Статус релизов

* ✅ v1.0 Foundation — завершен.
* ✅ v1.1 Intraday Data Layer — завершен.
* ✅ v1.2 Feature Factory — завершен.
* ✅ v1.3 Replay Engine — завершен.
* ✅ v1.4 Strategy Engine — завершен.
* ✅ v1.5 Paper Trading Engine — завершен.
* ✅ v1.6 Position Manager — завершен.
* ✅ v1.6.1 Persistence Layer — завершен.
* ✅ v1.7 Risk Engine — завершен.
* ✅ v1.8 Minimal Portfolio Allocation Engine — завершен.
* ✅ v1.9.1 Execution Cost Model — завершен.
* ✅ v1.9.2 WalkForward Window Generator — завершен.
* ✅ v1.9.3 WalkForward Engine — завершен.
* ✅ v1.9.4 Architecture Cleanup — завершен.
* ✅ v2.0 Validation Report — завершен.

---

# v1.6 Position Manager

Добавлен промышлененный модуль управления позициями.

Реализовано:

* поддержка LONG и SHORT;
* открытие позиции;
* увеличение существующей позиции;
* частичное закрытие;
* полное закрытие;
* расчет средней цены;
* расчет realized PnL;
* расчет unrealized PnL;
* обновление рыночной цены;
* управление открытыми позициями;
* модульные тесты Position Manager.

---

# v1.6.1 Persistence Layer

Начато построение единого слоя хранения данных проекта.

Реализовано:

* выделен отдельный слой `core/persistence`;
* реализован интерфейс `PositionRepository`;
* реализована in-memory реализация `MemoryPositionRepository`;
* реализована фабрика `PersistenceFactory`;
* добавлены специализированные исключения Persistence Layer;
* подготовлен каркас PostgreSQL Repository;
* PositionManager переведен на dependency injection репозитория;
* сохранена обратная совместимость с текущей in-memory реализацией;
* добавлены модульные тесты Persistence Layer;
* добавлены интеграционные тесты PositionManager ↔ Persistence Layer.

---

# Архитектурное правило

Начиная с v1.6.1 бизнес-логика проекта не должна зависеть от конкретного способа хранения данных.

Все сервисы работают только через интерфейсы Persistence Layer.

Это позволяет использовать:

* in-memory backend;
* PostgreSQL backend;
* будущие реализации (Redis, ClickHouse и др.) без изменения бизнес-логики.

---

# v1.7 Risk Engine

Реализован независимый детерминированный слой оценки риска.

Реализовано:

* доменные модели: `RiskDecision`, `RiskDecisionType`, `RiskReason`, `RiskLimits`, `RiskCheckRequest`;
* `RiskEngine.check()` — возвращает `ALLOW` / `REJECT` + список причин;
* проверка `max_trade_value`;
* проверка `max_position_value`;
* проверка `max_position_pct`;
* проверка `max_open_positions`;
* запрет short при `allow_short=False`;
* интеграция с `PaperTradingEngine` через опциональный `risk_engine`;
* отклонения попадают в `rejected_orders` журнал;
* обратная совместимость сохранена;
* исправлен packaging тестов (`tests/persistence/__init__.py`);
* 9 новых тестов Risk Engine.

---

# Architecture Refresh

Added:

* `CONTROL_CENTER/05_SYSTEM_VISION.md`
* `CONTROL_CENTER/10_ARCHITECTURE_DECISIONS.md`

Changed:

* `CONTROL_CENTER/01_PROJECT_STATE.md`
* `CONTROL_CENTER/02_ROADMAP.md`
* `CONTROL_CENTER/03_ARCHITECTURE.md`

Result:

Platform Vision 2.0 adopted.

---

# v1.8 Minimal Portfolio Allocation Engine

Added:

* `core/allocation/` — новый детерминированный слой;
* `AllocationConfig`, `AllocationRequest`, `AllocationDecision`;
* `AllocationDecisionType`: ALLOCATE / REDUCE / REJECT;
* `PortfolioAllocationEngine.allocate()`.

---

# v1.9.1 Execution Cost Model

Added:

* `core/costs/` — детерминированная модель издержек исполнения;
* `ExecutionCostConfig`, `ExecutionRequest`, `ExecutionResult`;
* `ExecutionCostEngine.calculate()` — commission, spread, slippage, effective_price для BUY / SELL.

---

# v1.9.2 WalkForward Window Generator

Added:

* `core/walkforward/` — пакет walk-forward валидации;
* `WalkForwardConfig` с валидацией параметров;
* `WalkForwardWindow` — полуоткрытые интервалы [start, end);
* `WalkForwardWindowGenerator.generate()`.

---

# v1.9.3 WalkForward Engine

Added:

* `WalkForwardRunResult`, `WalkForwardSummary` — модели результатов;
* `WalkForwardEngine.run(data_length, runner)` — generic Callable runner.

---

# v1.9.4 Architecture Cleanup

Deleted:

* `core/execution/replay_execution_engine.py`;
* `core/risk/risk_manager.py`;
* `core/strategy/base.py`;
* `core/strategy/registry.py`;
* `core/portfolio/` (ghost layer);
* 4 скрипт-файла в `tests/` (не pytest-тесты).

Changed:

* `PositionSide` — единственная дефиниция в `core/position/models.py`;
* `OrderSide(str, Enum)` в `core/common.py` заменил `side: str` в `RiskCheckRequest` и `ExecutionRequest`;
* demo-стратегии переписаны на `on_event` API.

---

# v2.0 Validation Report

Added:

* `ValidationStatus` (PASS / FAIL)
* `ValidationMetric`
* `ValidationReport`
* `ValidationReportBuilder`

Result:

Validation Foundation completed.

---

# Следующий релиз

## v2.1 — Market Regime Engine

Планируется реализовать:

* `RegimeType` — перечень рыночных режимов;
* `RegimeClassifier` — детерминированный классификатор без AI и ML;
* `RegimeReport` — результат классификации;
* без доступа к БД, независимый deterministic engine.

---

# Правило проекта

После завершения каждого релиза:

1. запускаются все тесты;
2. обновляется CONTROL_CENTER;
3. выполняется git commit;
4. выполняется git push;
5. проверяется состояние репозитория (`working tree clean`).

CONTROL_CENTER остается единственным источником актуального состояния проекта.
