# 99_PROJECT_DASHBOARD — MOEX AI LAB

> Живая сводка состояния проекта. Обновляется после каждого релиза.
> Последнее обновление: **2026-06-27 (v4.5-svc)**

---

## Текущий релиз

| Поле | Значение |
|------|---------|
| Релиз | v4.5-svc Research Service Alpha |
| Era | Program Era |
| Branch | main |
| Дата | 2026-06-27 |
| Тестов | **614 / 614 pass** |

---

## Era

| Era | Статус | Период |
|-----|--------|--------|
| Foundation Era | ✅ Completed (FC-1) | v1.0 – v3.3 |
| Program Era | 🟡 Active | Phase 4+ |

---

## Завершённые фазы

| Фаза | Релизы | Результат |
|------|--------|-----------|
| Production Core | v1.0 – v1.9.4 | StrategyEngine → Allocation → Risk → PaperTrading → Persistence |
| Validation Core | v2.0 | ValidationReportBuilder, PASS/FAIL, pass_rate >= 0.80 |
| Research Core | v2.1 – v3.3 | Regime, Experiment, Hypothesis, KB, Pipeline, Generator |

---

## Активная фаза

| Фаза | Статус | Документ |
|------|--------|---------|
| Phase 4: Research Intelligence | 🟡 Active | `20_PHASE_4_RESEARCH_INTELLIGENCE.md` |

Цель Phase 4: реальные данные MOEX + Knowledge-guided generation + Research Session.

---

## Состояние Core Modules

### Research Core

| Модуль | Путь | Статус | Версия |
|--------|------|--------|--------|
| MarketRegimeEngine | `core/regime/` | ✅ Stable | v2.1 |
| ExperimentRunner | `core/experiment/` | ✅ Stable | v2.2 |
| HypothesisRegistry | `core/hypothesis/` | ✅ Stable | v2.3 |
| KnowledgeBase | `core/knowledge/` | ✅ Stable | v2.4 |
| ResearchPipeline | `core/research_pipeline/` | ✅ Stable | v3.1 |
| Hypothesis Generator Module | `core/hypothesis_generator/` | ✅ Stable | v3.3 |
| Research Orchestrator | `core/research_orchestrator/` | ✅ Stable | v4.1 |
| Research Session | `core/research_session/` | ✅ Stable | v4.4 |

### Validation Core

| Модуль | Путь | Статус | Версия |
|--------|------|--------|--------|
| ExecutionCostEngine | `core/costs/` | ✅ Stable | v1.9.1 |
| WalkForwardEngine | `core/walkforward/` | ✅ Stable | v1.9.3 |
| ValidationReportBuilder | `core/validation/` | ✅ Stable | v2.0 |

### Production Core

| Модуль | Путь | Статус | Версия |
|--------|------|--------|--------|
| FeatureFactory | `core/features/` | ✅ Stable | v1.2 |
| ReplayEngine | `core/replay/` | ✅ Stable | v1.3 |
| StrategyEngine | `core/strategy/` | ✅ Stable | v1.4 |
| PaperTradingEngine | `core/paper/` | ✅ Stable | v1.5 |
| PositionManager | `core/position/` | ✅ Stable | v1.6 |
| Persistence Layer | `core/persistence/` | ✅ Stable (in-memory) | v1.6.1 |
| RiskEngine | `core/risk/` | ✅ Stable | v1.7 |
| PortfolioAllocationEngine | `core/allocation/` | ✅ Stable | v1.8 |

---

## Состояние Capabilities

| Capability | Статус | Примечание |
|------------|--------|------------|
| Детерминированная классификация режимов | ✅ | MarketRegimeEngine, 5 режимов |
| Walk-Forward валидация | ✅ | PASS >= 80% окон |
| Hypothesis lifecycle management | ✅ | 9 статусов, forward-only pipeline |
| Накопление знаний (KnowledgeBase) | ✅ | 6 типов, deepcopy изоляция |
| End-to-end Research Pipeline | ✅ | Hypothesis → Experiment → KB |
| Template-based hypothesis generation | ✅ | HypothesisGenerator Module |
| ADX индикатор (Wilder) | ✅ | `core/features/technical_indicators` |
| Синтетический H-13 эксперимент | ✅ | proof-of-pipeline |
| Research Orchestrator | ✅ v4.1 | ResearchOrchestrator, ResearchPlan, DefaultResearchPolicy |
| Knowledge-guided generation | ✅ v4.2 | KnowledgeRanker, KBTemplateStatisticsProvider, TemplateStats |
| Multi-hypothesis Research Session | ✅ v4.3 | ResearchSession, PlanExecutor, SessionStatistics |
| Research Report | ✅ v4.4 | ResearchReportBuilder, ResearchReport, ValidationOutcome |
| **Research Service** | ✅ v4.5-svc | `python -m services.research run --dataset <id>` |
| Operations Core (supervisor, drawdown) | 🔜 Phase 7 | |
| Live broker execution | 🔜 Phase 8+ | |

---

## Статистика тестов

| Модуль / группа | Тестов |
|-----------------|--------|
| Production Core (strategy, paper, risk, allocation, position, costs, walkforward) | ~160 |
| Validation Core (validation, walkforward) | ~25 |
| Research Core (regime, experiment, hypothesis, knowledge, research_pipeline) | ~100 |
| H-13 experiment + ADX | ~34 |
| Hypothesis Generator Module | ~91 |
| Research Orchestrator | 47 |
| Knowledge-Guided Generation (4.2) | 39 |
| Research Session (4.3) | 43 |
| Research Report (4.4) | 56 |
| Research Service (4.5-svc) | 71 |
| **Итого** | **614** |

---

## Experiments

| ID | Название | Тикер | Статус | Тип данных |
|----|----------|-------|--------|------------|
| H-13 | ADX Trend Continuation + RSI pullback | SYNTHETIC / SBER | ✅ | Синтетический + локальный CSV |

---

## Services

| Сервис | Команда | Статус |
|--------|---------|--------|
| Research Service | `python -m services.research run --dataset <id>` | ✅ v4.5-svc |

Артефакты: `reports/`, `sessions/`, `knowledge/knowledge_base.json`, `runs/`

---

## Следующий шаг

**Подключение реальных исторических данных MOEX + первый полный цикл.**

Разместить данные в `data/datasets/sber_1h_2023/ohlcv.csv` + `metadata.json` и запустить:
```bash
python -m services.research run --dataset sber_1h_2023 --description "H-13 SBER 2023"
```

После получения первых результатов — продолжить развитие Capability Phase 4.5+.

---

## Architecture Health

> Оценки по итогам Phase 4 Mid-Review (EWO-004, 2026-06-27).
> Шкала: 0–10.

| Измерение | Оценка | Комментарий |
|-----------|--------|-------------|
| **Core Integrity** | 10/10 | ADR-0002 (stdlib, clock injection) соблюдён во всех Capabilities; TD-001 закрыт в v4.4 (pass_threshold в config) |
| **Capability Separation** | 9/10 | Чёткие границы 4.1/4.2/4.3 без пересечений; —1 за accept_all() — два уровня абстракции на одном классе |
| **Extension Readiness** | 8/10 | PlanExecutor, CandidateRanker, TemplateStatisticsProvider, ResearchPolicy готовы; —2 за отсутствие Pipeline Protocol и OrchestrationObserver |
| **Documentation Consistency** | 8/10 | ADR актуальны; —2 за QueueOrderPolicy в ADR-0008 (исправлено); OQ-004 gap в нумерации |
| **Test Quality** | 9/10 | 487 тестов, детерминированы, cross-session determinism; —1 за отсутствие end-to-end теста (TD-003) |
| **Technical Debt** | 8/10 | 3 Active TD (001–003), 7 Deferred TD (004–010); реестр зафиксирован в baseline |

**Baseline зафиксирован:** `docs/40_PHASE_4_BASELINE.md` (2026-06-27)

---

## Документация

| Документ | Назначение |
|----------|------------|
| `docs/00_AI_CONSTITUTION.md` | Миссия, принципы, правила платформы |
| `docs/01_PROJECT_CONSTITUTION.md` | Модули, зависимости, правила расширения |
| `docs/10_MASTER_DEVELOPMENT_PROGRAM.md` | Программа развития, Foundation/Program Era |
| `docs/20_PHASE_4_RESEARCH_INTELLIGENCE.md` | Инженерная программа Phase 4 |
| `docs/30_ARCHITECTURE_DECISION_LOG.md` | ADR-журнал (18 записей) |
| `docs/40_PHASE_4_BASELINE.md` | Phase 4 Baseline Snapshot (EWO-005) |
| `docs/99_PROJECT_DASHBOARD.md` | Этот документ |
| `docs/research/MOEX_RESEARCH_PROGRAM.md` | 35 гипотез, 7 категорий |
| `CONTROL_CENTER/` | Оперативное состояние проекта |
