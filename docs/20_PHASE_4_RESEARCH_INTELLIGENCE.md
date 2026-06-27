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

### 4.2 — Knowledge-Guided Generation

**Что:** `HypothesisGenerator` начинает учитывать Knowledge Base при ранжировании
кандидатов.

**Детали:**
- Новый `CandidateRanker` реализация: `KnowledgeRanker`.
- Логика: шаблоны, для которых в KnowledgeBase есть записи с `validation_status=PASS`,
  получают score boost; шаблоны с повторными FAIL — penalize.
- `KnowledgeRanker` инжектируется вместо `PriorityRanker` при наличии данных в KB.
- `HypothesisGenerator.__init__` не меняется — только новая реализация Protocol.

**Зависит от:** `KnowledgeBase.find_by_type(EXPERIMENT)` — уже существует.

---

### 4.3 — Multi-Hypothesis Research Session

**Что:** запускать серию экспериментов по списку гипотез и собирать сводку.

**Детали:**
- `ResearchSession` — оркестратор над `ResearchPipeline`:
  принимает `list[Hypothesis]`, возвращает `ResearchSessionResult`.
- `ResearchSessionResult` содержит: по одному `ResearchPipelineResult` на гипотезу,
  сводные статистики (pass_count, fail_count, avg_pass_rate), список failed_experiments.
- Не является новым Core Engine — это тонкий оркестратор.

**Зависит от:** `ResearchPipeline.run()` — уже существует.

---

### 4.4 — Research Report

**Что:** человекочитаемая сводка по итогам `ResearchSession`.

**Детали:**
- `ResearchReportBuilder.build(session_result) -> ResearchReport`.
- `ResearchReport` содержит: список гипотез с их результатами, топ-N по pass_rate,
  список требующих повторного исследования (FAIL с pass_rate > 0.5), summary string.
- Формат вывода: структурированный dataclass, не Markdown/HTML
  (рендеринг — забота вызывающего кода).

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

### Реализованные (4.1)

| Компонент | Тип | Путь | Статус |
|-----------|-----|------|--------|
| `ResearchTask` | Model | `core/research_orchestrator/models.py` | ✅ |
| `ResearchTaskSummary` | Model | `core/research_orchestrator/models.py` | ✅ |
| `ResearchPlan` | Model | `core/research_orchestrator/models.py` | ✅ |
| `OrchestrationResult` | Model | `core/research_orchestrator/models.py` | ✅ |
| `ResearchPolicy` | Protocol | `core/research_orchestrator/protocols.py` | ✅ |
| `DefaultResearchPolicy` | impl | `core/research_orchestrator/policy.py` | ✅ |
| `ResearchOrchestrator` | Orchestrator | `core/research_orchestrator/orchestrator.py` | ✅ |

### Планируемые (4.2–4.5)

| Компонент | Тип | Путь | Capability |
|-----------|-----|------|------------|
| `KnowledgeRanker` | Ranker impl | `core/hypothesis_generator/ranker.py` | 4.2 |
| `ResearchSession` | Orchestrator | `core/research_pipeline/session.py` | 4.3 |
| `ResearchSessionResult` | Model | `core/research_pipeline/models.py` | 4.3 |
| `ResearchReportBuilder` | Builder | `core/research_pipeline/report.py` | 4.4 |
| `ResearchReport` | Model | `core/research_pipeline/models.py` | 4.4 |
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
| `KnowledgeRanker` | ⏳ Phase 4.2 |
| `ResearchSession` | ⏳ Phase 4.3 |
