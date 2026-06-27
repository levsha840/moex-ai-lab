# 99_PROJECT_DASHBOARD — MOEX AI LAB

> Живая сводка состояния проекта. Обновляется после каждого релиза.
> Последнее обновление: **2026-06-27 (FC-1)**

---

## Текущий релиз

| Поле | Значение |
|------|---------|
| Релиз | v3.3 Hypothesis Generator Module |
| Era | Program Era |
| Branch | main |
| Commit | 885ff90 |
| Дата | 2026-06-27 |
| Тестов | **358 / 358 pass** |

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
| Реальные данные MOEX | ⏳ Phase 4.1 | |
| Knowledge-guided generation | ⏳ Phase 4.2 | KnowledgeRanker |
| Multi-hypothesis Research Session | ⏳ Phase 4.3 | ResearchSession |
| Research Report | ⏳ Phase 4.4 | ResearchReportBuilder |
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
| Hypothesis Generator Module | ~52 |
| **Итого** | **358** |

---

## Experiments

| ID | Название | Тикер | Статус | Тип данных |
|----|----------|-------|--------|------------|
| H-13 | ADX Trend Continuation + RSI pullback | SYNTHETIC | ✅ Proof-of-pipeline | Синтетический |

---

## Следующий релиз

**Phase 4.1 — Real Data Integration**

- `DatasetProvider` Protocol
- Загрузка реальных OHLCV MOEX (SBER, GAZP, LKOH)
- H-13 эксперимент на реальных данных
- Обновление Knowledge Base

---

## Документация

| Документ | Назначение |
|----------|------------|
| `docs/00_AI_CONSTITUTION.md` | Миссия, принципы, правила платформы |
| `docs/01_PROJECT_CONSTITUTION.md` | Модули, зависимости, правила расширения |
| `docs/10_MASTER_DEVELOPMENT_PROGRAM.md` | Программа развития, Foundation/Program Era |
| `docs/20_PHASE_4_RESEARCH_INTELLIGENCE.md` | Инженерная программа Phase 4 |
| `docs/30_ARCHITECTURE_DECISION_LOG.md` | ADR-журнал (7 записей) |
| `docs/99_PROJECT_DASHBOARD.md` | Этот документ |
| `docs/research/MOEX_RESEARCH_PROGRAM.md` | 35 гипотез, 7 категорий |
| `CONTROL_CENTER/` | Оперативное состояние проекта |
