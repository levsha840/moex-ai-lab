# 01_PROJECT_STATE

MOEX AI LAB — актуальное состояние после **v4.4 Research Report** (2026-06-27).

---

## Era

| Era | Статус |
|-----|--------|
| Foundation Era | ✅ Completed |
| Program Era | 🟡 Active (Phase 4) |

---

## Статус релизов

### Foundation Era (Completed)

| Версия | Название | Статус |
|--------|----------|--------|
| v1.0 | Foundation | ✅ |
| v1.1 | Intraday Data Layer | ✅ |
| v1.2 | Feature Factory | ✅ |
| v1.3 | Replay Engine | ✅ |
| v1.4 | Strategy Engine | ✅ |
| v1.5 | Paper Trading Engine | ✅ |
| v1.6 | Position Manager | ✅ |
| v1.6.1 | Persistence Layer | ✅ |
| v1.7 | Risk Engine | ✅ |
| — | Architecture Refresh | ✅ |
| v1.8 | Portfolio Allocation Engine | ✅ |
| v1.9.1 | Execution Cost Model | ✅ |
| v1.9.2 | WalkForward Window Generator | ✅ |
| v1.9.3 | WalkForward Engine | ✅ |
| v1.9.4 | Architecture Cleanup | ✅ |
| v2.0 | Validation Report | ✅ |
| v2.1 | Market Regime Engine | ✅ |
| v2.2 | Experiment Runner | ✅ |
| v2.3 | Hypothesis Registry | ✅ |
| v2.4 | Knowledge Base | ✅ |
| v3.1 | First Research Pipeline | ✅ |
| v3.2 | H-13 Synthetic Research Experiment | ✅ |
| v3.3 | Hypothesis Generator Module | ✅ |
| FC-1 | Foundation Closure + Documentation System | ✅ |

---

## Текущий статус тестов

**543 / 543 passed.**

---

## Текущий релиз

**v4.4 Research Report** (2026-06-27)

Новые компоненты в `core/research_session/`:
- `report_models.py` — `ValidationOutcome`, `RecommendationKind`, `RecommendationPriority`,
  `RecommendationScope`, `HypothesisInfo`, `ResearchFinding`, `ResearchRecommendation`,
  `ReportSummary`, `ResearchReport`;
- `report.py` — `ResearchReportBuilder.build(result) → ResearchReport`;
- `protocols.py` — `HypothesisInfoProvider` Protocol добавлен;
- `models.py` — `ResearchSessionConfig.pass_threshold: float = 0.80` добавлен (ADR-0017).

ADR добавлены: ADR-0015 (ResearchReport reference), ADR-0016 (HypothesisInfoProvider),
ADR-0017 (pass_threshold в config), ADR-0018 (ValidationOutcome).
TD-001 закрыт. OQ-007 закрыт. OQ-010 добавлен (persistence деферрован в Phase 6+).
56 новых тестов.

---

## Активная фаза

**Phase 4 — Research Intelligence**

Цель: реальные данные MOEX + Knowledge-guided generation + Multi-hypothesis session.

Детали: `docs/20_PHASE_4_RESEARCH_INTELLIGENCE.md`

---

## Core Modules (стабильные)

### Research Core
- `core/regime/` — MarketRegimeEngine (v2.1)
- `core/experiment/` — ExperimentRunner (v2.2)
- `core/hypothesis/` — HypothesisRegistry (v2.3)
- `core/knowledge/` — KnowledgeBase (v2.4)
- `core/research_pipeline/` — ResearchPipeline (v3.1)
- `core/hypothesis_generator/` — Hypothesis Generator Module (v3.3)
- `core/research_orchestrator/` — Research Orchestrator (v4.1)
- `core/research_session/` — Research Session + Report (v4.4)

### Validation Core
- `core/costs/` — ExecutionCostEngine (v1.9.1)
- `core/walkforward/` — WalkForwardEngine (v1.9.3)
- `core/validation/` — ValidationReportBuilder (v2.0)

### Production Core
- `core/features/` — FeatureFactory (v1.2)
- `core/replay/` — ReplayEngine (v1.3)
- `core/strategy/` — StrategyEngine (v1.4)
- `core/paper/` — PaperTradingEngine (v1.5)
- `core/position/` — PositionManager (v1.6)
- `core/persistence/` — PositionRepository (v1.6.1)
- `core/risk/` — RiskEngine (v1.7)
- `core/allocation/` — PortfolioAllocationEngine (v1.8)

---

## Документация (создана в FC-1)

- `docs/00_AI_CONSTITUTION.md` — миссия и принципы
- `docs/01_PROJECT_CONSTITUTION.md` — модули, зависимости, правила
- `docs/10_MASTER_DEVELOPMENT_PROGRAM.md` — программа развития
- `docs/20_PHASE_4_RESEARCH_INTELLIGENCE.md` — Phase 4
- `docs/30_ARCHITECTURE_DECISION_LOG.md` — ADR (7 записей)
- `docs/99_PROJECT_DASHBOARD.md` — живая сводка

---

## Правило

После завершения каждого релиза или фазы `01_PROJECT_STATE.md` и `02_ROADMAP.md`
обновляются. `01_PROJECT_STATE` — единственный источник актуального состояния.
