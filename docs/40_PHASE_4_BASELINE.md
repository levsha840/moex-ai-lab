# 40_PHASE_4_BASELINE — MOEX AI LAB

> Официальный архитектурный baseline Phase 4 после завершения Capabilities 4.1–4.3.
> Создан по итогам Phase 4 Mid-Review (EWO-004).
> Дата фиксации: **2026-06-27 (v4.3)**.
>
> Этот документ не изменяется retroactively. Изменения Phase 4.4+ фиксируются
> в следующем baseline или в PHASE_4_RESEARCH_INTELLIGENCE.md.

---

## 1. Реализованные Capabilities

| Capability | Версия | Дата | Тестов | Статус |
|------------|--------|------|--------|--------|
| 4.1 Research Orchestrator | v4.1 | 2026-06-27 | 47 | ✅ Completed |
| 4.2 Knowledge-Guided Generation | v4.2 | 2026-06-27 | 39 | ✅ Completed |
| 4.3 Multi-Hypothesis Research Session | v4.3 | 2026-06-27 | 43 | ✅ Completed |
| **Итого Phase 4.1–4.3** | | | **129** | |

Суммарный тест-счёт платформы на момент baseline: **487 / 487 pass**.

### 4.1 — Research Orchestrator

**Новая способность:** выполнение упорядоченной последовательности исследовательских задач
по готовому плану с управлением lifecycle гипотез и policy-driven остановкой.

Ключевые компоненты:
- `ResearchTask` — unit of work: hypothesis_id + ExperimentConfig + lifecycle
- `ResearchTaskSummary` — lightweight pointer на результат в KB
- `ResearchPlan` — frozen ordered list задач
- `OrchestrationResult` — immutable snapshot завершённой сессии
- `ResearchPolicy` Protocol — `should_continue()` + `on_task_failure()`
- `DefaultResearchPolicy` — abort after N consecutive pipeline failures
- `ResearchOrchestrator.run(plan, registry, pipeline, *, policy)`

### 4.2 — Knowledge-Guided Generation

**Новая способность:** ранжирование кандидатов с учётом накопленной истории KB;
boost для высоко-проходимых шаблонов; penalty за частое использование.

Ключевые компоненты:
- `TemplateStats` — frozen: pass_count, fail_count, experiment_count, pass_rate, has_history
- `TemplateStatisticsProvider` Protocol — `get_stats() → dict[str, TemplateStats]`
- `KBTemplateStatisticsProvider` — KB + Registry → TemplateStats
- `KnowledgeRanker` — `CandidateRanker` impl без зависимости на KB/Registry

### 4.3 — Multi-Hypothesis Research Session

**Новая способность:** полный исследовательский цикл за один вызов:
генерация → bulk acceptance → построение плана → выполнение → агрегация статистики.

Ключевые компоненты:
- `ResearchSessionConfig` — frozen: GenerationConfig + ExperimentConfig + description
- `ResearchSessionStatus` — CREATED / RUNNING / COMPLETED / ABORTED / FAILED
- `SessionStatistics` — агрегат с `validation_pass_rate` (property)
- `ResearchSessionResult` — frozen snapshot
- `PlanExecutor` Protocol — stateless executor (ADR-0014)
- `ResearchSession.run()` — coordination facade (ADR-0013)
- `HypothesisGenerator.accept_all()` — bulk acceptance

---

## 2. Core Module Registry (Phase 4)

### Новые модули Phase 4

| Модуль | Путь | Версия | Capability |
|--------|------|--------|------------|
| Research Orchestrator | `core/research_orchestrator/` | v4.1 | 4.1 |
| Research Session | `core/research_session/` | v4.3 | 4.3 |

### Расширенные модули Phase 4

| Модуль | Путь | Изменение | Capability |
|--------|------|-----------|------------|
| Hypothesis Generator Module | `core/hypothesis_generator/` | + TemplateStats, TemplateStatisticsProvider, KBTemplateStatisticsProvider, KnowledgeRanker, accept_all() | 4.2, 4.3 |

### Полный реестр Research Core на момент baseline

| Модуль | Путь | Версия |
|--------|------|--------|
| MarketRegimeEngine | `core/regime/` | v2.1 |
| ExperimentRunner | `core/experiment/` | v2.2 |
| HypothesisRegistry | `core/hypothesis/` | v2.3 |
| KnowledgeBase | `core/knowledge/` | v2.4 |
| ResearchPipeline | `core/research_pipeline/` | v3.1 |
| Hypothesis Generator Module | `core/hypothesis_generator/` | v3.3 + Phase 4.2 ext |
| Research Orchestrator | `core/research_orchestrator/` | v4.1 |
| Research Session | `core/research_session/` | v4.3 |

---

## 3. Protocol Registry (Phase 4)

### Новые Protocols Phase 4

| Protocol | Путь | Реализации | Capability |
|----------|------|------------|------------|
| `ResearchPolicy` | `core/research_orchestrator/protocols.py` | `DefaultResearchPolicy` | 4.1 |
| `TemplateStatisticsProvider` | `core/hypothesis_generator/protocols.py` | `KBTemplateStatisticsProvider` | 4.2 |
| `PlanExecutor` | `core/research_session/protocols.py` | `ResearchOrchestrator` (duck typing) | 4.3 |

### Унаследованные Protocols (Foundation Era, используются в Phase 4)

| Protocol | Путь | Используется в |
|----------|------|----------------|
| `CandidateRanker` | `core/hypothesis_generator/protocols.py` | `KnowledgeRanker`, `PriorityRanker` |
| `TemplateRepository` | `core/hypothesis_generator/protocols.py` | `MemoryTemplateRepository` |

---

## 4. ADR Index (Phase 4)

| ADR | Заголовок | Capability | Статус |
|-----|-----------|------------|--------|
| ADR-0008 | Research Orchestrator — sequence executor, not decision maker | 4.1 | Active |
| ADR-0009 | OrchestrationResult — неизменяемый итоговый снимок | 4.1 | Active |
| ADR-0010 | KnowledgeBase — не зависимость ResearchOrchestrator | 4.1 | Active |
| ADR-0011 | TemplateStatisticsProvider Protocol | 4.2 | Active |
| ADR-0012 | KB-корректировка score ограничена [0.5, 1.5] | 4.2 | Active |
| ADR-0013 | ResearchSession — orchestration facade | 4.3 | Active |
| ADR-0014 | PlanExecutor Protocol stateless | 4.3 | Active |

Полный текст: `docs/30_ARCHITECTURE_DECISION_LOG.md`.

---

## 5. Архитектурные инварианты

Инварианты — это ограничения, нарушение которых требует нового ADR и архитектурного ревью.

### INV-001: Core детерминирован (ADR-0002)

`core/` использует только stdlib Python. `pandas`, `numpy`, `scikit-learn` запрещены.
Время инжектируется через `_clock: Callable[[], datetime]`.
Одинаковый вход → одинаковый вычисленный выход.

### INV-002: Четыре контура независимы (ADR-0001)

Research Core не имеет прямого доступа к Production Core. Обратное тоже запрещено.
Код Research не может исполнять реальные ордера.

### INV-003: ResearchOrchestrator — sequence executor, не decision maker (ADR-0008)

Оркестратор выполняет задачи строго в порядке `ResearchPlan.tasks`.
Он не принимает решений о том, какие задачи запускать или в каком порядке.
Любая логика выбора принадлежит caller'у (через `ResearchPlan`) или
`ResearchPolicy` (через policy gate).

### INV-004: KnowledgeBase не является зависимостью ResearchOrchestrator (ADR-0010)

Оркестратор не знает о KnowledgeBase. KB пишется внутри ResearchPipeline.
Любая KB-dependent логика принадлежит уровню Policy или Research Session.

### INV-005: KnowledgeRanker не знает источника статистики (ADR-0011)

`KnowledgeRanker` зависит только от `TemplateStatisticsProvider` Protocol.
Никаких прямых импортов из `core/knowledge/` или `core/hypothesis/` в `ranker.py`.

### INV-006: PlanExecutor является stateless-компонентом (ADR-0014)

Реализации `PlanExecutor` не хранят изменяемое состояние между вызовами `run()`.
Один экземпляр может быть вызван многократно с разными параметрами — результат
каждый раз определяется только параметрами вызова.

### INV-007: ResearchSession — coordination facade (ADR-0013)

Session не содержит бизнес-логики принятия решений.
100% генерации → HypothesisGenerator. 100% выполнения → PlanExecutor.
Единственные обязанности Session: координация шагов 1–4 и агрегация статистики.

### INV-008: Порог валидации 80% захардкодирован (ADR-0007)

`_PASS_THRESHOLD = 0.80` в ValidationReportBuilder не конфигурируется через
внешние параметры. Изменение — архитектурное событие, требующее ADR.

### INV-009: Новые шаблоны никогда не получают starvation (ADR-0012)

`knowledge_multiplier = 1.0` при отсутствии истории KB (experiment_count = 0).
Приоритет-A гипотеза без истории всегда опережает Приоритет-C с максимальным boost.

### INV-010: OrchestrationResult — неизменяемый snapshot (ADR-0009)

`OrchestrationResult` возвращается только после завершения всей сессии.
Caller не может изменить его после получения.

### INV-011: Validation FAIL — не pipeline failure

Эксперимент с `pass_rate < 0.80` завершается как `ResearchTaskStatus.COMPLETED`.
Только исключение из `ResearchPipeline.run()` → `ResearchTaskStatus.FAILED`.
Policy-abort применяется только к FAILED, не к низко-проходимым экспериментам.

### INV-012: core/ не импортирует из experiments/

Любой Core Module не знает о конкретных экспериментах.
Шаблоны хранятся в `experiments/<name>/template.py` (ADR-0005).

---

## 6. Схема зависимостей Phase 4

```
╔══════════════════════════════════════════════════════════════════════════╗
║  RESEARCH INTELLIGENCE (Phase 4)                                        ║
║                                                                          ║
║  ┌─────────────────────────────────────────────────────────────┐        ║
║  │  core/research_session/                                      │        ║
║  │  ResearchSession.run(config, registry, pipeline, *, policy)  │        ║
║  │    │                                                          │        ║
║  │    ├── HypothesisGenerator.generate() + accept_all()         │        ║
║  │    ├── ResearchPlan(tasks)                                    │        ║
║  │    └── PlanExecutor.run(plan, registry, pipeline, policy)     │        ║
║  └──────────────────────────┬────────────────────────────────────┘       ║
║                             │ depends on                                  ║
║  ┌──────────────────────────▼───────────────────────┐                    ║
║  │  core/research_orchestrator/                      │                    ║
║  │  ResearchOrchestrator.run(plan, registry, pipeline│                    ║
║  │    [satisfies PlanExecutor structurally]          │                    ║
║  └──────────────────────────┬───────────────────────┘                    ║
║                             │                                             ║
║  ┌──────────────────────────▼────────────────────────────────────┐       ║
║  │  core/hypothesis_generator/                                    │       ║
║  │  HypothesisGenerator(repo: TemplateRepository,                 │       ║
║  │                       ranker: CandidateRanker)                 │       ║
║  │  KnowledgeRanker(provider: TemplateStatisticsProvider)         │       ║
║  │  KBTemplateStatisticsProvider(kb, registry) ← stats only      │       ║
║  └───────────────────────────────────────────────────────────────┘       ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║  RESEARCH CORE (Foundation Era v3.x)                                    ║
║                                                                          ║
║  core/research_pipeline/  →  core/experiment/                           ║
║                           →  core/hypothesis/                           ║
║                           →  core/knowledge/                            ║
║                           →  core/validation/  (status read)            ║
║  core/knowledge/                                                         ║
║  core/hypothesis/                                                        ║
║  core/experiment/  →  core/strategy/ (via ExperimentRunner)             ║
║  core/regime/        (independent)                                       ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║  VALIDATION CORE (v2.x)                                                 ║
║  core/validation/  →  core/walkforward/                                 ║
║  core/walkforward/   (independent)                                      ║
║  core/costs/         (independent)                                      ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║  PRODUCTION CORE (v1.x)                                                 ║
║  strategy → features, replay                                            ║
║  paper    → position, risk, allocation                                  ║
║  position → persistence (Protocol)                                      ║
╚══════════════════════════════════════════════════════════════════════════╝

ЗАПРЕЩЕНО: Research Core → Production Core (любое направление)
ЗАПРЕЩЕНО: core/ → experiments/
ЗАПРЕЩЕНО: циклические зависимости любого рода
```

---

## 7. Точки расширения (Extension Points)

| EP | Protocol | Текущая реализация | Планируемое расширение |
|----|----------|-------------------|------------------------|
| EP-01 | `CandidateRanker` | `PriorityRanker`, `KnowledgeRanker` | `RegimeAwareRanker` (4.5) |
| EP-02 | `TemplateStatisticsProvider` | `KBTemplateStatisticsProvider` | `RegimeFilteredStatsProvider` (4.5) |
| EP-03 | `ResearchPolicy` | `DefaultResearchPolicy` | `BudgetPolicy`, `TimeboxPolicy` (future) |
| EP-04 | `PlanExecutor` | `ResearchOrchestrator` (duck typing) | `ParallelPlanExecutor` (Phase 5) |
| EP-05 | `TemplateRepository` | `MemoryTemplateRepository` | `SQLTemplateRepository` (future) |
| EP-06 | `OrchestrationObserver` | — не реализован — | Progress monitoring (Phase 5) |
| EP-07 | `Pipeline` Protocol | — не введён — | Абстракция над `ResearchPipeline` (Phase 5) |

EP-06 и EP-07 задокументированы в ADR-0009 и ADR-0014 как planned extension points;
реализации не существуют на момент baseline.

---

## 8. Technical Debt Register

### Active — требует решения до ближайших Capability

| ID | Описание | Приоритет | Планируемая фаза |
|----|----------|-----------|------------------|
| **TD-001** | `_VALIDATION_PASS_THRESHOLD = 0.80` продублирован в `session.py` и `ValidationReportBuilder`; синхронизируется только комментарием | Высокий | **4.4** |
| **TD-002** | `ResearchSessionStatus.CREATED` и `RUNNING` никогда не устанавливаются в `ResearchSession.run()`; статусы объявлены, но мертвы | Средний | **4.4** |
| **TD-003** | Нет end-to-end теста, запускающего `ResearchSession` с реальными (non-stub) компонентами | Средний | **4.4** |

**TD-001** — детали:
`core/research_session/session.py` строка 27 и `ValidationReportBuilder._PASS_THRESHOLD`
содержат одно и то же значение 0.80 без механизма синхронизации.
`ResearchReportBuilder` (4.4) также потребует это значение.
Реализация OQ-007 устраняет TD-001.

**TD-002** — детали:
`ResearchSession.run()` возвращает `COMPLETED` или `ABORTED`.
`FAILED` декларирован в enum-комментарии, но никогда не устанавливается:
при исключении оно пробрасывается, `ResearchSessionResult` не создаётся.
Это корректное поведение, но делает enum misleading для consumers (в т.ч. 4.4 ReportBuilder).

**TD-003** — детали:
Все 129 тестов Phase 4 используют stubs/mocks для изоляции компонентов.
Нет теста, проходящего реальный путь `ResearchSession` → `ResearchOrchestrator`
→ `ResearchPipeline` → `ExperimentRunner` → `ValidationReportBuilder` end-to-end.

### Deferred — осознанно перенесено на будущие фазы

| ID | Описание | Приоритет | Планируемая фаза |
|----|----------|-----------|------------------|
| **TD-004** | `ResearchPipeline` — конкретный класс в `PlanExecutor.run()` сигнатуре; блокирует Phase 5 параллельное выполнение | Средний | **Phase 5** |
| **TD-005** | `ResearchTask` мутабелен; `OrchestrationResult.completed_tasks` хранит ссылки на те же объекты, мутация которых после `run()` возможна | Низкий | **Phase 5** |
| **TD-006** | `OrchestrationObserver` Protocol задокументирован в ADR-0009, не реализован; прогресс в реальном времени недоступен | Низкий | **Phase 5** |
| **TD-007** | `KBTemplateStatisticsProvider.get_stats()` агрегирует по всем `dataset_id`; нет фильтрации по режиму/датасету | Средний | **4.5** |
| **TD-008** | `CandidateRanker.rank(candidates)` не принимает `regime_context`; требует изменения Protocol для Regime-Aware Selection | Средний | **4.5** |
| **TD-009** | `ResearchSessionResult` не сохраняется; нет audit trail для серии сессий | Низкий | **Phase 6+** |
| **TD-010** | `QueueOrderPolicy` упомянут в ADR-0008 как extension point; концепция реализована иначе (через `KnowledgeRanker` на уровне генерации, не очереди) — ADR требует пометки | Низкий | **Now (документирование)** |

---

## 9. Open Questions (OQ)

Полный реестр открытых вопросов с назначением Capability.

| ID | Вопрос | Целевая Capability | Статус |
|----|--------|-------------------|--------|
| **OQ-001** | PaperTradingEngine vs PositionManager: два независимых учёта позиций, связь не определена | Phase 7 | Open |
| **OQ-002** | PostgresPositionRepository: заглушка с v1.6.1, реализация не начата | Phase 6 | Open |
| **OQ-003** | Порог 80% для RANGE-режима: может ли быть другой порог для RANGE-стратегий? | **4.5** | Open |
| **OQ-005** | CandidateRanker Protocol + context: нужен ли `regime_context` keyword-only параметр? | **4.5 prerequisite** | Open |
| **OQ-006** | Агрегация KB stats по нескольким тикерам: `get_stats()` суммирует все dataset_id | **4.5 prerequisite** | Open |
| **OQ-007** | Порог 0.80 в `session.py`: дублирует ValidationReportBuilder; перенести в `ResearchSessionConfig`? | **4.4** | Open |
| **OQ-008** | Per-hypothesis ExperimentConfig: когда гипотезы требуют разных конфигов — нужен `ExperimentConfigProvider`? | Phase 5 | Open |
| **OQ-009** | Сохранение `ResearchSessionResult`: нужен ли persist для audit trail? | Phase 6+ | Open |

**Примечание:** OQ-004 не существует — нумерация пропущена намеренно при создании реестра.

---

## 10. Известные ограничения

### L-001: Один ExperimentConfig на сессию

`ResearchSessionConfig` содержит один `ExperimentConfig`, применяемый ко всем гипотезам
в сессии. Разные конфигурации для разных гипотез невозможны без изменения API.
Это design decision (OQ-008), не баг.

### L-002: Нет параллельного выполнения задач

`ResearchOrchestrator` — sequential executor. Одна задача выполняется в один момент.
`PlanExecutor` Protocol предусмотрен для будущего `ParallelPlanExecutor` (TD-004).

### L-003: Нет мониторинга прогресса в реальном времени

`ResearchSession.run()` блокирующий. Caller получает результат только после завершения.
`OrchestrationObserver` Protocol запланирован, не реализован (TD-006).

### L-004: ResearchPipeline без Pipeline Protocol

`ResearchPipeline` — конкретный класс, а не Protocol. Нельзя подменить реализацию
pipeline без изменения сигнатуры `PlanExecutor.run()` (TD-004).

### L-005: Нет фильтрации KB stats по рыночному режиму

`KBTemplateStatisticsProvider` считает все PASS/FAIL для шаблона независимо от
market regime, dataset, или тикера. Для Regime-Aware ранжирования потребуется
расширение API (OQ-006, TD-007).

### L-006: Нет audit trail для Research Sessions

`ResearchSessionResult` не сохраняется автоматически. История сессий недоступна
без внешнего кода сохранения (OQ-009).

### L-007: CREATED и RUNNING статусы декларативны

`ResearchSessionStatus.CREATED` и `RUNNING` объявлены, но `ResearchSession.run()`
никогда их не устанавливает (TD-002). Consumer не может наблюдать состояние «в процессе».

---

## 11. Baseline Signatures (Reference)

Публичные API, зафиксированные на момент baseline. Изменение этих сигнатур
является breaking change и требует ADR.

```python
# 4.1
ResearchOrchestrator.run(
    plan: ResearchPlan,
    registry: HypothesisRegistry,
    pipeline: ResearchPipeline,
    *,
    policy: ResearchPolicy | None = None,
) -> OrchestrationResult

# 4.2
KnowledgeRanker.rank(candidates: list[HypothesisCandidate]) -> list[HypothesisCandidate]
KBTemplateStatisticsProvider.get_stats() -> dict[str, TemplateStats]

# 4.3
ResearchSession.run(
    config: ResearchSessionConfig,
    registry: HypothesisRegistry,
    pipeline: ResearchPipeline,
    *,
    policy: ResearchPolicy | None = None,
) -> ResearchSessionResult

HypothesisGenerator.accept_all(
    session: GenerationSession,
    registry: HypothesisRegistry,
) -> list[Hypothesis]

PlanExecutor.run(
    plan: ResearchPlan,
    registry: HypothesisRegistry,
    pipeline: ResearchPipeline,
    *,
    policy: ResearchPolicy | None = None,
) -> OrchestrationResult
```

---

*Baseline зафиксирован: 2026-06-27, v4.3, commit be582d3, tag `v4.3-research-session`.*
