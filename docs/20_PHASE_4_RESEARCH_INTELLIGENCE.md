# 20_PHASE_4_RESEARCH_INTELLIGENCE — MOEX AI LAB

> Инженерная программа Phase 4. Детали реализации появляются по мере движения
> через фазу — этот документ описывает цель, capability и критерии завершения.

---

## Статус

**Активна.** Начата после FC-1 (2026-06-27).

---

## Цель

Перейти от синтетических экспериментов к содержательным исследованиям
на реальных данных MOEX.

После Foundation Era платформа умеет:
- генерировать и регистрировать гипотезы;
- запускать Walk-Forward эксперименты;
- записывать результаты в Knowledge Base;
- генерировать новые кандидаты по шаблонам.

Чего не хватает для содержательной работы:
- реальных данных MOEX (не синтетических);
- механизма загрузки данных в Feature Provider;
- Knowledge-guided ранжирования генерируемых кандидатов;
- сравнительного анализа нескольких гипотез;
- Research Report — сводки по итогам серии экспериментов.

---

## Capabilities Phase 4

### 4.1 — Research Orchestrator ✅ Completed (2026-06-27)

**Что:** sequence executor для управления жизненным циклом серии экспериментов.

**Компоненты:** `core/research_orchestrator/`
- `ResearchTask` — единица работы: одна гипотеза + один `ExperimentConfig`;
  жизненный цикл PENDING → IN_PROGRESS → COMPLETED | FAILED | SKIPPED.
- `ResearchTaskSummary` — лёгкий указатель на результат: `knowledge_entry_id`,
  `pass_rate`, `windows_total` (полный результат хранится в KnowledgeBase).
- `ResearchPlan` — frozen-объект с упорядоченным `tuple[ResearchTask, ...]`.
- `OrchestrationResult` — неизменяемый итоговый снимок выполненной сессии.
- `ResearchPolicy` Protocol — `should_continue()` + `on_task_failure()`.
- `DefaultResearchPolicy` — прервать после N последовательных pipeline-ошибок.
- `ResearchOrchestrator.run(plan, registry, pipeline, *, policy)`.

**Ключевые решения:**
- Оркестратор — sequence executor, не decision maker (ADR-0008).
- `KnowledgeBase` не является зависимостью оркестратора (ADR-0010).
- `ResearchQueue` не создан: `ResearchPlan.tasks` (tuple) достаточен для v4.1;
  `QueueOrderPolicy` отложен до Knowledge-driven Prioritization.
- Validation FAIL → `ResearchTaskStatus.COMPLETED`; только исключение pipeline → FAILED.

**Тесты:** 47 новых тестов (405 итого).

---

### 4.2 — Knowledge-Guided Generation ✅ Completed (2026-06-27)

**Что:** `HypothesisGenerator` учитывает Knowledge Base при ранжировании кандидатов.

**Компоненты:** `core/hypothesis_generator/`
- `TemplateStats` — frozen dataclass: `pass_count`, `fail_count`, `experiment_count`,
  `pass_rate` (property), `has_history` (property). `experiment_count` = pass + fail (явное поле).
- `TemplateStatisticsProvider` Protocol — `get_stats() → dict[str, TemplateStats]`.
  Инкапсулирует сбор данных, изолируя `KnowledgeRanker` от источника.
- `KBTemplateStatisticsProvider` — реализация Protocol через `KnowledgeBase` + `HypothesisRegistry`.
  Разрешение: `KnowledgeEntry.reference_id → hypothesis.metadata["template_id"]`.
- `KnowledgeRanker` — реализация `CandidateRanker` Protocol. Получает готовые `TemplateStats`,
  вычисляет `final_score = base_score × knowledge_multiplier × duplicate_penalty`,
  возвращает новые объекты с обновлённым `score` и `rationale`.

**Ключевые решения:**
- `KnowledgeRanker` не зависит от `KnowledgeBase` или `HypothesisRegistry` (ADR-0011).
- `knowledge_multiplier ∈ [0.5, 1.5]` при default config (ADR-0012).
- `duplicate_penalty` использует `experiment_count` (pass + fail), а не только `pass_count`.
- Tie-breaking: `(-score, template_id, title)` — стабильные идентификаторы.
- Новые шаблоны (нет истории): `knowledge_multiplier = 1.0` — starvation невозможен.
- `HypothesisGenerator.__init__` не изменялся — только новые реализации Protocol.

**Тесты:** 39 новых тестов (444 итого).

**Зависит от:** `KnowledgeBase.find_by_type(EXPERIMENT)`, `HypothesisRegistry.get()` — существуют.

---

### 4.3 — Multi-Hypothesis Research Session ✅ Completed (2026-06-27)

**Что:** полный исследовательский цикл: генерация гипотез → ранжирование → план → оркестрация.

**Компоненты:** `core/research_session/`
- `ResearchSessionConfig` — frozen: `GenerationConfig` + `ExperimentConfig` + description.
- `ResearchSessionStatus` — CREATED / RUNNING / COMPLETED / ABORTED / FAILED.
- `SessionStatistics` — агрегат: кандидаты, принятые гипотезы, задачи (completed/failed/skipped),
  validation_pass/fail/inconclusive, `avg_pass_rate`, `validation_pass_rate` (property),
  `kb_entries_created`, `duration_seconds`.
- `ResearchSessionResult` — frozen снимок: session_id, config, orchestration_result, statistics.
- `PlanExecutor` Protocol — stateless executor; `ResearchOrchestrator` реализует структурно.
- `ResearchSession.run(config, registry, pipeline, *, policy)` — coordination facade.
- `HypothesisGenerator.accept_all(session, registry)` — инкапсулирует bulk acceptance.

**Ключевые решения:**
- ResearchSession — coordination facade, не новый engine (ADR-0013).
- PlanExecutor Protocol обеспечивает заменяемость стратегии выполнения (ADR-0014).
- PlanExecutor stateless: хранение состояния между вызовами запрещено (ADR-0014).
- `accept_all()` — одна операция уровня генерации вместо цикла в Session (Change 1).
- `validation_pass_rate` — property на SessionStatistics (Change 2).

**Тесты:** 43 новых теста (487 итого).

---

### 4.4 — Research Report ✅ Completed (2026-06-27)

**Что:** структурированный отчёт по итогам `ResearchSession` — для людей и будущих Capabilities.

**Компоненты:** `core/research_session/`
- `ValidationOutcome` — PASS / FAIL / INCONCLUSIVE / ERROR / SKIPPED (ADR-0018).
- `RecommendationKind` — REPEAT_EXPERIMENT / ARCHIVE_HYPOTHESIS / EXPLORE_VARIANT /
  REVIEW_PARAMETERS / INVESTIGATE_PIPELINE / RESCHEDULE_SKIPPED.
- `RecommendationPriority` — HIGH / MEDIUM / LOW.
- `RecommendationScope` — SESSION / HYPOTHESIS (explicit scope, не None-sentinel).
- `HypothesisInfo` — lightweight frozen dataclass для метаданных гипотезы.
- `ResearchFinding` — frozen: один finding per task в порядке плана.
- `ResearchRecommendation` — frozen: data-driven рекомендация (scope + kind + priority).
- `ReportSummary` — frozen: агрегат (counts, avg/median pass_rate, validation_pass_rate).
- `ResearchReport` — frozen: `session_id` (reference) + summary + findings + recommendations.
- `HypothesisInfoProvider` Protocol — `get_info(ids) → dict[str, HypothesisInfo]`.
- `ResearchReportBuilder.build(result) → ResearchReport` — stateless, no side effects.

**Ключевые решения:**
- `ResearchReport` хранит `session_id: str`, не полный `ResearchSessionResult` (ADR-0015).
- `HypothesisInfoProvider` — опциональная зависимость, duck typing (ADR-0016).
- `pass_threshold` перенесён из константы в `ResearchSessionConfig` (ADR-0017, TD-001 закрыт).
- `ValidationOutcome` разделяет семантику отчёта и lifecycle задач (ADR-0018).
- `median_pass_rate` добавлен в `ReportSummary` (более устойчив к выбросам, чем mean).
- Рекомендации сортируются: HIGH → MEDIUM → LOW, внутри группы — по `kind.value`.

**Тесты:** 56 новых тестов (543 итого).

---

### 4.5 — Regime-Aware Experiment Routing

**Что:** Feature Provider автоматически выбирает подходящий период данных
в зависимости от доминирующего рыночного режима.

**Детали:**
- `RegimeAwareDataSelector` — принимает полный датасет и `MarketRegimeEngine`,
  возвращает подмножество баров, соответствующих целевому режиму.
- Позволяет запускать эксперименты только на данных в TREND_UP, RANGE и т.д.
- Используется как preprocessing-шаг в H-N Feature Providers.

---

## Компоненты Phase 4

### Реализованные (4.1–4.2)

| Компонент | Тип | Путь | Статус |
|-----------|-----|------|--------|
| `ResearchTask` | Model | `core/research_orchestrator/models.py` | ✅ |
| `ResearchTaskSummary` | Model | `core/research_orchestrator/models.py` | ✅ |
| `ResearchPlan` | Model | `core/research_orchestrator/models.py` | ✅ |
| `OrchestrationResult` | Model | `core/research_orchestrator/models.py` | ✅ |
| `ResearchPolicy` | Protocol | `core/research_orchestrator/protocols.py` | ✅ |
| `DefaultResearchPolicy` | impl | `core/research_orchestrator/policy.py` | ✅ |
| `ResearchOrchestrator` | Orchestrator | `core/research_orchestrator/orchestrator.py` | ✅ |
| `TemplateStats` | Model | `core/hypothesis_generator/models.py` | ✅ |
| `TemplateStatisticsProvider` | Protocol | `core/hypothesis_generator/protocols.py` | ✅ |
| `KBTemplateStatisticsProvider` | impl | `core/hypothesis_generator/statistics.py` | ✅ |
| `KnowledgeRanker` | Ranker impl | `core/hypothesis_generator/ranker.py` | ✅ |

### Реализованные (4.3)

| Компонент | Тип | Путь | Статус |
|-----------|-----|------|--------|
| `ResearchSessionConfig` | Model | `core/research_session/models.py` | ✅ |
| `ResearchSessionStatus` | Enum | `core/research_session/models.py` | ✅ |
| `SessionStatistics` | Model | `core/research_session/models.py` | ✅ |
| `ResearchSessionResult` | Model | `core/research_session/models.py` | ✅ |
| `PlanExecutor` | Protocol | `core/research_session/protocols.py` | ✅ |
| `ResearchSession` | Facade | `core/research_session/session.py` | ✅ |
| `HypothesisGenerator.accept_all` | Method | `core/hypothesis_generator/engine.py` | ✅ |

### Реализованные (4.4)

| Компонент | Тип | Путь | Статус |
|-----------|-----|------|--------|
| `ValidationOutcome` | Enum | `core/research_session/report_models.py` | ✅ |
| `RecommendationKind` | Enum | `core/research_session/report_models.py` | ✅ |
| `RecommendationPriority` | Enum | `core/research_session/report_models.py` | ✅ |
| `RecommendationScope` | Enum | `core/research_session/report_models.py` | ✅ |
| `HypothesisInfo` | Model | `core/research_session/report_models.py` | ✅ |
| `ResearchFinding` | Model | `core/research_session/report_models.py` | ✅ |
| `ResearchRecommendation` | Model | `core/research_session/report_models.py` | ✅ |
| `ReportSummary` | Model | `core/research_session/report_models.py` | ✅ |
| `ResearchReport` | Model | `core/research_session/report_models.py` | ✅ |
| `HypothesisInfoProvider` | Protocol | `core/research_session/protocols.py` | ✅ |
| `ResearchReportBuilder` | Builder | `core/research_session/report.py` | ✅ |
| `ResearchSessionConfig.pass_threshold` | Field | `core/research_session/models.py` | ✅ |

### Планируемые (4.5)

| Компонент | Тип | Путь | Capability |
|-----------|-----|------|------------|
| `RegimeAwareDataSelector` | Utility | `core/regime/selector.py` | 4.5 |

Ни один из компонентов не нарушает существующий dependency graph.

---

## Эксперименты Phase 4

Первые содержательные эксперименты на реальных данных:

| ID | Гипотеза | Тикер | Приоритет |
|----|----------|-------|-----------|
| H-13 | ADX Trend Continuation + RSI pullback | SBER | A |
| H-14 | SMA Cross in TREND_UP regime | GAZP | A |
| H-07 | Дивидендный Gap-Fill | SBER, GAZP, LKOH | A |
| H-01 | Morning Gap Continuation | SBER | B |

Эксперименты запускаются последовательно. Каждый проходит полный цикл через
ResearchPipeline и записывается в Knowledge Base.

---

## Критерии завершения Phase 4

Phase 4 считается завершённой, когда выполнены **все** пункты:

1. ✅ `ResearchOrchestrator` реализован и покрыт тестами (Capability 4.1).
2. Минимум 3 гипотезы из MOEX Research Program прошли полный цикл
   через `ResearchOrchestrator` + `ResearchPipeline` (Capabilities 4.2–4.3).
3. Knowledge Base содержит минимум 5 записей типа `EXPERIMENT`.
4. `KnowledgeRanker` использует данные KB при генерации новых кандидатов
   и тест подтверждает, что порядок кандидатов меняется относительно `PriorityRanker` (4.2).
5. `ResearchSession` запускает серию из 2+ гипотез и возвращает
   корректный `ResearchSessionResult` (4.3).
6. Все существующие тесты проходят (405+).

---

## Зависимости

| Зависимость | Статус |
|-------------|--------|
| `HypothesisGenerator` (v3.3) | ✅ Готов |
| `ResearchPipeline` (v3.1) | ✅ Готов |
| `KnowledgeBase` (v2.4) | ✅ Готов |
| `MarketRegimeEngine` (v2.1) | ✅ Готов |
| `HypothesisRegistry` (v2.3) | ✅ Готов |
| `ResearchOrchestrator` (v4.1) | ✅ Готов |
| `KnowledgeRanker` (v4.2) | ✅ Готов |
| `ResearchSession` (v4.3) | ✅ Готов |
