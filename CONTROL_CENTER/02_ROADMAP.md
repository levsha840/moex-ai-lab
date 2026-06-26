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
| v1.8 | Minimal Portfolio Allocation Engine | ✅ завершён |
| v1.9.1 | Execution Cost Model | ✅ завершён |
| v1.9.2 | WalkForward Window Generator | ✅ завершён |
| v1.9.3 | WalkForward Engine | ✅ завершён |
| v1.9.4 | Architecture Cleanup | ✅ завершён |
| v2.0 | Validation Report | ✅ завершён |

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

### v2.1 — Market Regime Engine

Цель: классифицировать рыночные режимы для фильтрации стратегий по условиям рынка.

Scope:

- `RegimeType` — перечень рыночных режимов;
- `RegimeClassifier` — детерминированный классификатор;
- `RegimeReport` — результат классификации;
- без AI, без ML, без доступа к БД;
- независимый deterministic engine.

---

### v2.2 — Hypothesis Lab

Цель: сделать исследование гипотез управляемым процессом.

Scope:

- hypothesis registry;
- статусы гипотез;
- связь гипотез со стратегиями и экспериментами;
- первые гипотезы: дивидендный gap-fill, momentum на отчётностях, пары Роснефть/Лукойл;
- накопление причин отказа.

---

### v2.4 — Strategy Supervisor

Цель: контролировать уже работающие стратегии.

Scope:

- performance drift;
- drawdown limits;
- degradation detection;
- scale down / disable / archive decisions;
- перевод стратегии из production в paper или archive при деградации.

---

### v2.5 — Observability & Decision Audit

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
Validation infrastructure > Research tools (v2.1+) > New strategies
```

Новые production-стратегии не добавляются до завершения Validation Core.

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
