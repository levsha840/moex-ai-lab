# 02_ROADMAP

MOEX AI LAB — roadmap после архитектурного обновления Platform Vision.

## Завершённые релизы

| Версия | Название | Статус |
|---|---|---|
| v1.0 | Foundation | ✅ завершён |
| v1.1 | Intraday Data Layer | ✅ завершён |
| v1.2 | Feature Factory | ✅ завершён |
| v1.3 | Replay Engine | ✅ завершён |
| v1.4 | Strategy Engine | ✅ завершён |
| v1.5 | Paper Trading Engine | ✅ завершён |
| v1.6 | Position Manager | ✅ завершён |
| v1.6.1 | Persistence Layer | ✅ завершён |
| v1.7 | Risk Engine | ✅ завершён |

Architecture Refresh — выполнен: добавлены `05_SYSTEM_VISION.md` и `10_ARCHITECTURE_DECISIONS.md`.

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

## Следующие релизы

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

Архитектурное правило: `PortfolioAllocationEngine` не исполняет сделки, не пишет в repository, не вызывает RiskEngine и не имеет доступа к БД.

---

### v1.9 — Validation Foundation

Цель: создать первичный контур честной проверки стратегий.

Scope:

- WalkForward Engine;
- Realistic Cost Model (спред, T+2, налог 13%, рыночное влияние);
- базовая Data Quality;
- OOS metrics;
- PASS / FAIL decision;
- запрет доверять стратегиям без cost-adjusted walk-forward.

Архитектурное правило: WalkForward и Cost Model являются неделимыми — walk-forward без реалистичной модели издержек не считается достаточной проверкой.

---

### v2.0 — Market Regime Engine

Цель: классифицировать рыночные режимы и проверять стратегии по режимам.

Scope:

- trend / flat / high volatility regimes;
- regime labels на дневном таймфрейме;
- strategy performance by regime;
- фильтр режима в StrategyEngine;
- запрет production-допуска стратегии без понимания, в каких режимах она работает.

---

### v2.1 — Hypothesis Lab

Цель: сделать исследование гипотез управляемым процессом.

Scope:

- hypothesis registry;
- статусы гипотез;
- связь гипотез со стратегиями и экспериментами;
- первые гипотезы: дивидендный gap-fill, momentum на отчётностях, пары Роснефть/Лукойл;
- накопление причин отказа.

---

### v2.2 — Strategy Supervisor

Цель: контролировать уже работающие стратегии.

Scope:

- performance drift;
- drawdown limits;
- degradation detection;
- scale down / disable / archive decisions;
- перевод стратегии из production в paper или archive при деградации.

---

### v2.3 — Observability & Decision Audit

Цель: обеспечить воспроизводимость и объяснимость решений платформы.

Scope:

- structured decision events;
- decision_id across pipeline;
- reasons for reject/reduce/disable;
- strategy lifecycle audit trail;
- research funnel metrics.

---

## Принцип приоритетов

```
Validation infrastructure (v1.9) > Research tools (v2.0, v2.1) > New strategies
```

Новые production-стратегии не добавляются до завершения v1.9.

Demo-стратегии (RSI/SMA) остаются в кодовой базе только как smoke-test инструмент.

## Отложенные направления

Эти направления важны, но не должны опережать validation foundation:

- AI strategy generation;
- AI allocation;
- сложные portfolio optimizers;
- broker live execution;
- production automation без человеческого approval.

## Правило

После завершения каждого релиза CONTROL_CENTER обновляется. Roadmap — живой документ, обновляется при изменении приоритетов.
