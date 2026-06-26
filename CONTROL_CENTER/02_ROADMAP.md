# 02_ROADMAP

MOEX AI LAB — roadmap после архитектурного обновления Platform Vision.

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
- Architecture Refresh — выполнен частично: добавлены `05_SYSTEM_VISION.md` и `10_ARCHITECTURE_DECISIONS.md`.
- v1.8 Minimal Portfolio Allocation Engine — следующий инженерный релиз.

## Завершённые релизы

- v1.0–v1.2: фундамент, данные, фичи.
- v1.3: ReplayEngine — детерминированный посвечный replayer.
- v1.4: StrategyEngine — конвейер BUY/SELL/HOLD сигналов.
- v1.5: PaperTradingEngine — виртуальное исполнение заявок.
- v1.6: PositionManager — управление LONG/SHORT позициями.
- v1.6.1: Persistence Layer — Protocol-based абстракция хранения, MemoryRepository, каркас PostgresPositionRepository.
- v1.7: RiskEngine — pre-trade оценка риска, интеграция с PaperTradingEngine.

## Архитектурный поворот

Проект развивается как платформа исполнения и сопровождения торговых стратегий, а не как набор отдельных торговых алгоритмов.

Ключевые контуры:

- Production Core — исполнение решений.
- Validation Core — допуск стратегий к капиталу.
- Research Core — генерация и проверка гипотез.
- Operations Core — supervision, audit и сопровождение работающих стратегий.

Документы:

- `05_SYSTEM_VISION.md` — миссия и целевая архитектура платформы.
- `10_ARCHITECTURE_DECISIONS.md` — журнал ключевых архитектурных решений.

## Ближайшие релизы

### v1.8 — Minimal Portfolio Allocation Engine

Цель: добавить минимальный детерминированный слой распределения капитала перед RiskEngine.

Scope:

- `core/allocation/`;
- `AllocationConfig` / `AllocationLimits`;
- `AllocationRequest`;
- `AllocationDecision`;
- `AllocationDecisionType`: `ALLOCATE`, `REDUCE`, `REJECT`;
- базовые лимиты: `max_position_pct`, `max_strategy_pct`, `max_correlated_pct`, `cash_buffer`, `rebalance_threshold`;
- unit tests;
- без Kelly, Markowitz, Black-Litterman, AI allocation и сложной динамической ребалансировки.

Архитектурное правило:

`PortfolioAllocationEngine` не исполняет сделки, не пишет в repository, не вызывает RiskEngine и не имеет доступа к БД.

### v1.9 — Validation Foundation

Цель: создать первичный контур честной проверки стратегий.

Scope:

- WalkForward Engine;
- realistic Cost Model;
- базовая Data Quality;
- OOS metrics;
- PASS / FAIL decision;
- запрет доверять стратегиям без cost-adjusted walk-forward.

Архитектурное правило:

WalkForward и Cost Model являются неделимыми: walk-forward без реалистичной модели издержек не считается достаточной проверкой.

### v2.0 — Market Regime Engine

Цель: классифицировать рыночные режимы и проверять стратегии по режимам.

Scope:

- trend / flat / high volatility regimes;
- regime labels;
- strategy performance by regime;
- запрет production-допуска стратегии без понимания, в каких режимах она работает.

### v2.1 — Hypothesis Lab

Цель: сделать исследование гипотез управляемым процессом.

Scope:

- hypothesis registry;
- статусы гипотез;
- связь гипотез со стратегиями и экспериментами;
- накопление причин отказа.

### v2.2 — Strategy Supervisor

Цель: контролировать уже работающие стратегии.

Scope:

- performance drift;
- drawdown limits;
- degradation detection;
- scale down / disable / archive decisions;
- перевод стратегии из production в paper или archive при деградации.

### v2.3 — Observability & Decision Audit

Цель: обеспечить воспроизводимость и объяснимость решений платформы.

Scope:

- structured decision events;
- decision_id across pipeline;
- reasons for reject/reduce/disable;
- strategy lifecycle audit trail;
- research funnel metrics.

## Отложенные направления

Эти направления важны, но не должны опережать validation foundation:

- AI strategy generation;
- AI allocation;
- сложные portfolio optimizers;
- broker live execution;
- production automation без человеческого approval.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
