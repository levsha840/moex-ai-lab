# 30_ARCHITECTURE_DECISION_LOG — MOEX AI LAB

> Журнал ключевых архитектурных решений. Каждая запись описывает контекст,
> решение, обоснование и последствия. Формат: облегчённый ADR.
>
> Записи не удаляются и не редактируются после принятия. Устаревшие решения
> помечаются [SUPERSEDED] с ссылкой на заменяющую запись.

---

## Шаблон записи

```
## ADR-NNNN: Заголовок

**Дата:** YYYY-MM-DD
**Статус:** Accepted | Superseded by ADR-XXXX | Open

**Контекст:**
Что происходило, какая проблема стояла.

**Решение:**
Что именно было решено.

**Обоснование:**
Почему именно это решение, какие альтернативы отклонены и почему.

**Последствия:**
Что стало возможным, что усложнилось, какие ограничения приняты.
```

---

## ADR-0001: Четыре независимых контура платформы

**Дата:** 2025 (Architecture Refresh)
**Статус:** Accepted

**Контекст:**
Изначально проект разрабатывался как набор торговых стратегий с общей кодовой базой.
По мере роста стало ясно, что Research-код проникает в Production, Validation
отсутствует как отдельный слой, а Operations вообще не предусмотрен.

**Решение:**
Разделить платформу на четыре независимых контура с явными границами:

1. **Production Core** — исполнение торговых решений (детерминированный, без БД).
2. **Validation Core** — обязательный шлюз PASS/FAIL перед Production.
3. **Research Core** — генерация и проверка гипотез (не имеет доступа к Production).
4. **Operations Core** — supervision работающих стратегий (будущее).

**Обоснование:**
- Без явного Validation шлюза в Production попадают непроверенные стратегии.
- Research должен иметь право "ошибаться" без риска для капитала.
- Разделение позволяет развивать контуры независимо.
- Альтернатива (монолит с флагами) создала бы неявные зависимости.

**Последствия:**
- Research Core не может напрямую исполнять ордера.
- Каждая стратегия обязана пройти Validation перед Production.
- Operations Core остался нереализованным до Phase 7.

---

## ADR-0002: Core — stdlib only, детерминированность, без БД

**Дата:** 2025 (Architecture Refresh)
**Статус:** Accepted

**Контекст:**
Core Modules первоначально имели прямые SQL-запросы, вызовы `datetime.now()`,
случайность. Это делало тесты нестабильными и воспроизводимость экспериментов невозможной.

**Решение:**
- Все Core Modules работают только на stdlib Python.
- Все Core Modules детерминированы: одинаковый вход → одинаковый выход.
- Время инжектируется через `_clock: Callable[[], datetime]`.
- База данных доступна только через Protocol-интерфейс (`PositionRepository`).
- `pandas`, `numpy`, `scikit-learn` запрещены в `core/`.

**Обоснование:**
- Детерминированность — единственный способ доверять результатам экспериментов.
- stdlib only снижает риски версионирования и ускоряет запуск тестов.
- Инъекция времени позволяет тестировать временную логику без `sleep` и `freeze`.
- Альтернатива (pandas в Core) дала бы скорость за счёт предсказуемости.

**Последствия:**
- ADX, RSI, ATR реализованы на чистом Python — это ограничение производительности
  при n > 10^6 баров (приемлемо для текущего масштаба).
- Тесты запускаются за 1-2 секунды на всём наборе.

---

## ADR-0003: ResearchPipeline как оркестратор без бизнес-логики

**Дата:** 2026 (v3.1)
**Статус:** Accepted

**Контекст:**
После реализации ExperimentRunner, KnowledgeBase и HypothesisRegistry встал вопрос:
кто соединяет эти компоненты в один поток и когда писать в KnowledgeBase?

**Решение:**
Создать `ResearchPipeline` — тонкий оркестратор, который:
1. Вызывает `ExperimentRunner.run(config)`.
2. Записывает результат в `KnowledgeBase.record()`.
3. Возвращает `ResearchPipelineResult`.

ResearchPipeline не содержит бизнес-логики: не анализирует результаты,
не принимает решений, не управляет hypothesis lifecycle.

**Обоснование:**
- ExperimentRunner и KnowledgeBase должны оставаться независимыми —
  их можно использовать по отдельности.
- Если ResearchPipeline содержит логику, её сложнее тестировать и менять.
- "Записать в KB только при успехе" — это policy; она может измениться,
  поэтому закреплена в оркестраторе, а не в движке.
- Альтернатива (KnowledgeBase внутри ExperimentRunner) нарушала бы SRP.

**Последствия:**
- Всё, что происходит "между" экспериментом и знанием, живёт в ResearchPipeline.
- Если ExperimentRunner бросает исключение — KnowledgeBase не пишется.
  Это явное design-решение (не побочный эффект).

---

## ADR-0004: HypothesisGenerator — отдельный модуль, не часть HypothesisRegistry

**Дата:** 2026 (v3.3)
**Статус:** Accepted

**Контекст:**
После реализации HypothesisRegistry встал вопрос: откуда берутся гипотезы?
`registry.create("title", "statement")` требует ручного ввода. Для масштабирования
Research Program нужна систематическая генерация.

**Решение:**
Создать отдельный модуль `core/hypothesis_generator/` с:
- `HypothesisTemplate` — параметризованный шаблон;
- `HypothesisGenerator.generate()` → `GenerationSession`;
- `HypothesisGenerator.accept()` → `Hypothesis` через `HypothesisRegistry.create()`.

**Обоснование:**
- `HypothesisRegistry` управляет lifecycle существующих гипотез.
  Добавление генерации смешало бы два разных домена.
- Отдельный модуль позволяет добавлять новые `CandidateRanker` и `TemplateRepository`
  без изменения Registry.
- Расширение `registry.create_from_template()` не покрыло бы ранжирование,
  фильтрацию и хранение шаблонов.
- Альтернатива (фабричный метод в Registry) была рассмотрена и отклонена
  из-за смешения ответственностей.

**Последствия:**
- `hypothesis_generator → hypothesis` (через `accept()`); обратной зависимости нет.
- `KnowledgeBase` не инжектируется в v3.3 — это явное ограничение, снятое в Phase 4.2.
- Термин "Engine" не используется для HypothesisGenerator — это модуль, не движок.

---

## ADR-0005: Шаблоны гипотез живут рядом с экспериментами

**Дата:** 2026 (v3.3)
**Статус:** Accepted

**Контекст:**
При создании `HypothesisTemplate` для H-13 встал вопрос: где хранить шаблоны?
Варианты: централизованный каталог, `core/hypothesis_generator/builtin_templates.py`,
или рядом с экспериментом.

**Решение:**
Шаблоны хранятся в `experiments/<name>/template.py`, рядом с соответствующим
экспериментом:

```
experiments/h13_adx_continuation/
    template.py     ← HypothesisTemplate
    dataset.py
    providers.py
    experiment.py
```

**Обоснование:**
- Шаблон описывает контракт конкретного эксперимента:
  его параметры, признаки, тикеры. Изменение эксперимента → изменение шаблона.
  Логично хранить их вместе.
- Централизованный каталог создал бы неявную зависимость между шаблонами
  разных экспериментов и усложнил бы навигацию.
- `core/hypothesis_generator/builtin_templates.py` нарушал бы принцип:
  Core не должен знать о конкретных экспериментах.

**Последствия:**
- Чтобы использовать шаблон H-13, нужно импортировать из `experiments/h13_adx_continuation/template.py`.
- `MemoryTemplateRepository` позволяет загружать шаблоны из разных мест в одном репозитории.
- Нет "глобального" реестра шаблонов в Core — это сделано намеренно.

---

## ADR-0006: Core детерминирован — GenerationSession.session_id использует uuid4

**Дата:** 2026 (v3.3)
**Статус:** Accepted

**Контекст:**
`uuid4()` не является детерминированным. ADR-0002 запрещает недетерминированность
в Core. Означает ли это, что ID нельзя генерировать в Core?

**Решение:**
`uuid4().hex` допускается в Core для генерации идентификаторов объектов:
`Hypothesis.id`, `KnowledgeEntry.id`, `HypothesisCandidate.candidate_id`,
`GenerationSession.session_id`.

**Обоснование:**
Детерминированность Core означает: при одинаковых входных данных логика
возвращает одинаковые вычисленные результаты (scores, regimes, validation, PnL).

Идентификаторы служат ссылками на объекты, а не входными данными вычислений.
Их уникальность важна; их конкретное значение — нет.

Тесты на детерминизм проверяют `title`, `statement`, `score`, `status`, `pass_rate` —
не `id`.

**Последствия:**
- `candidate_id` и `session_id` разные при каждом вызове — это ожидаемо.
- Тесты на детерминизм никогда не сравнивают ID.

---

## ADR-0007: Validation Core — порог 80% pass_rate захардкодирован

**Дата:** 2026 (v2.0)
**Статус:** Accepted

**Контекст:**
При реализации ValidationReportBuilder встал вопрос о пороге PASS/FAIL.
Варианты: конфигурируемый, захардкодированный, внешний.

**Решение:**
Порог `pass_rate >= 0.80` захардкодирован в `ValidationReportBuilder`.
Константа именована `_PASS_THRESHOLD = 0.80`.

**Обоснование:**
- Конфигурируемый порог создаёт риск манипуляции: исследователь мог бы
  занижать порог до прохождения стратегии.
- 0.80 выбран как разумный минимум для алгоритмической торговли.
- Изменение порога является архитектурным событием, требует ADR — это
  гарантирует осознанность решения.

**Последствия:**
- Стратегия не может "пройти" валидацию изменением конфигурации.
- Изменение порога требует правки Core и новой ADR-записи.
- Разные пороги для разных типов стратегий — не поддерживаются в текущей версии.

---

## ADR-0008: Research Orchestrator — sequence executor, not decision maker

**Дата:** 2026-06-27
**Статус:** Accepted
**[AMENDED 2026-06-27]:** Примечание о QueueOrderPolicy добавлено ниже.

**Контекст:**
При проектировании Research Orchestrator существует соблазн добавить «умную» логику:
выбор следующей задачи по данным KnowledgeBase, адаптацию к результатам,
исследование параметрических пространств. Каждое добавление кажется оправданным изолированно,
но в сумме создаёт God Object.

**Решение:**
`ResearchOrchestrator` выполняет задачи строго в порядке `ResearchPlan.tasks`.
Любая логика выбора задач принадлежит отдельным capability:
Knowledge-driven Prioritization, Parameter Exploration, Event Intelligence.
Они воздействуют на план до передачи в оркестратор — не на оркестратор во время выполнения.

**Обоснование:**
Единственная ответственность на уровне capability. «Умный» оркестратор становится
God Object за 2–3 релиза. Отдельные capability тестируются и развиваются независимо.
Альтернатива (KB-awareness в оркестраторе) была явно отклонена при ревью.

**Последствия:**
- Порядок задач фиксируется в `ResearchPlan` до начала выполнения.
- Динамическое переупорядочивание — extension point для будущих фаз.

**[AMENDED 2026-06-27] Уточнение о QueueOrderPolicy:**
Исходный текст ссылался на `QueueOrderPolicy` как extension point для Capability 4.2
(Knowledge-driven Prioritization). Capability 4.2 реализовала ту же цель иначе:
через `KnowledgeRanker` на уровне генерации кандидатов — до построения `ResearchPlan`.
`QueueOrderPolicy` как runtime-переупорядочивание очереди не реализован и не потребовался.
Runtime-динамическое переупорядочивание задач остаётся extension point для Phase 6+.

---

## ADR-0009: OrchestrationResult — неизменяемый итоговый снимок

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
Отслеживание выполнения сессии требует мутабельного внутреннего состояния.
При этом caller должен получить стабильный инспектируемый объект после завершения.
Вопрос: должен ли тот же объект служить обеим целям?

**Решение:**
`OrchestrationResult` — frozen dataclass, возвращается только после завершения
всей сессии. Внутреннее состояние выполнения хранится в мутабельных полях
`ResearchTask` (status, timestamps, summary) и не экспонируется как отдельный объект.

**Обоснование:**
Разделение «состояние в процессе» (мутабельные задачи) и «отчёт о завершении»
(frozen result) устраняет риск гонки за данными и неожиданной мутации извне.
Caller получает объект-снимок без возможности его изменить.

**Последствия:**
- Caller не может наблюдать прогресс сессии в реальном времени (design intent для v4.1).
- Для наблюдаемости в режиме реального времени предусмотрен extension point
  `OrchestrationObserver` Protocol.
- `ResearchTask` остаётся мутабельным внутри сессии; его состояние после
  завершения отражено в `OrchestrationResult.completed_tasks` и т.д.

---

## ADR-0010: KnowledgeBase — не зависимость ResearchOrchestrator в v4.1

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
Оркестратор мог бы использовать KnowledgeBase для пропуска уже исследованных
гипотез или ранжирования задач по накопленным знаниям. Это выглядит логично,
но добавляет зависимость к knowledge layer.

**Решение:**
`KnowledgeBase` не инжектируется в `ResearchOrchestrator` в v4.1.
KB-зависимая логика принадлежит `QueueOrderPolicy` Protocol (уровень очереди),
реализуемой в Knowledge-driven Prioritization (Capability 4.2).

Guard «гипотеза уже в RESEARCH+» реализован через `HypothesisRegistry.get()` —
без KB-запроса.

**Обоснование:**
- Граф зависимостей оркестратора минимален: только `hypothesis`, `experiment`,
  `research_pipeline`. KB не нужна для корректного выполнения v4.1.
- KB-логика развивается независимо, не блокирует тестируемость оркестратора.
- Transitiv зависимость через Policy (orchestrator → policy → KB) нарушила бы
  дух изоляции, даже если прямой импорт отсутствует.

**Последствия:**
- Оркестратор не может автоматически деградировать на основе KB-паттернов.
- `ResearchTask.summary.knowledge_entry_id` позволяет caller самостоятельно
  обратиться к KB после завершения задачи.
- Future `KnowledgeAwareQueuePolicy` инжектируется в `ResearchPlan`/`ResearchQueue`,
  не в оркестратор.

---

## ADR-0011: TemplateStatisticsProvider Protocol разделяет сбор данных и ранжирование

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
`KnowledgeRanker` требует агрегированной статистики по шаблонам (pass/fail).
Первоначальный дизайн предполагал прямые зависимости `KnowledgeRanker → KnowledgeBase`
и `KnowledgeRanker → HypothesisRegistry`. Архитектурное ревью указало: два домена
(сбор данных и ранжирование) не должны находиться в одном классе.

**Решение:**
Ввести `TemplateStatisticsProvider` Protocol в `core/hypothesis_generator/protocols.py`.
`KnowledgeRanker` зависит только от этого Protocol — не знает ни о `KnowledgeBase`,
ни о `HypothesisRegistry`.
`KBTemplateStatisticsProvider` (`core/hypothesis_generator/statistics.py`) реализует Protocol
и несёт ответственность за разрешение цепочки:
`KnowledgeEntry.reference_id → HypothesisRegistry.get() → hypothesis.metadata["template_id"]`.

**Обоснование:**
- Одна ответственность: `KnowledgeRanker` вычисляет score; `KBTemplateStatisticsProvider`
  агрегирует данные. Каждый класс меняется по своей причине.
- Расширяемость: будущий `SQLTemplateStatisticsProvider` или `RedisTemplateStatisticsProvider`
  реализует тот же Protocol без изменения логики ранжирования.
- Тестируемость: `KnowledgeRanker` тестируется со stub-провайдером, независимо от KB.
- Альтернатива (двойная зависимость прямо в `KnowledgeRanker`) была отклонена на ревью.

**Последствия:**
- `KnowledgeRanker` не имеет зависимости на `KnowledgeBase` или `HypothesisRegistry`.
- `hypothesis_generator → knowledge` и `hypothesis_generator → hypothesis`
  зависимости ограничены `statistics.py`.
- `TemplateStatisticsProvider` Protocol открыт для реализаций за пределами
  `core/hypothesis_generator/`.

---

## ADR-0012: KB-корректировка score ограничена диапазоном [0.5, 1.5]

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
Неограниченное усиление/ослабление сигнала из KB создаёт два риска:
(1) feedback loop — успешные шаблоны всё сильнее доминируют;
(2) starvation — новые шаблоны вытесняются накопленным сигналом.

**Решение:**
`knowledge_multiplier = 1.0 + (pass_rate − 0.5) × max_adjustment × confidence_factor`,
где `max_adjustment ∈ [0.0, 2.0]`, default = 1.0.
При default: диапазон `knowledge_multiplier = [0.5, 1.5]`.
Новые шаблоны (нет истории, `experiment_count = 0`): `confidence_factor = 0`,
`knowledge_multiplier = 1.0` — всегда нейтральный.
`duplicate_penalty = max(floor=0.75, 1.0 − 0.05 × experiment_count)` — использует
`experiment_count` (pass + fail), не только `pass_count`.

**Обоснование:**
- KB — один из факторов, не единственный determinant.
- Базовый приоритет (A/B/C) остаётся первичным discriminant'ом.
- Диапазон ±50% достаточен для полезного сигнала, но не переворачивает приоритетную структуру.
- `duplicate_penalty` по `experiment_count` (не `pass_count`): повторное исследование
  с FAIL-результатом имеет столь же убывающую ценность, что и с PASS-результатом.
- При `max_adjustment = 0.0` `KnowledgeRanker` ведёт себя как `PriorityRanker` —
  полная обратная совместимость.

**Последствия:**
- Система не может "научиться" полностью игнорировать низкоприоритетные шаблоны.
- Новая приоритет-A гипотеза (score=1.0) всегда опережает приоритет-C с
  максимальным PASS-бустом (0.4 × 1.5 × 0.75 = 0.45). Starvation невозможен.
- Изменение весов является архитектурным событием, требующим обновления ADR.

---

## ADR-0013: ResearchSession — orchestration facade, не новый engine

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
ResearchSession координирует HypothesisGenerator и PlanExecutor (ResearchOrchestrator).
Есть риск добавления бизнес-логики: фильтрации кандидатов, retry-правил, reporting,
отбора по критериям KB — всё это выглядит уместным "рядом" с сессией.

**Решение:**
ResearchSession делегирует 100% генерации → HypothesisGenerator (включая `accept_all`),
100% выполнения → PlanExecutor. Единственная ответственность Session — координация
(шаги 1–4) и агрегация `SessionStatistics`. Reporting → ResearchReportBuilder (4.4).
Стратегия фильтрации кандидатов → `GenerationConfig`. Retry-правила → `ResearchPolicy`.

**Обоснование:**
"Orchestration facade" — паттерн с единственной ответственностью: координировать,
а не исполнять. Если появляется соблазн добавить логику в Session — это сигнал к
созданию новой Capability или Protocol.

**Последствия:**
- Изменение бизнес-правил требует изменений в других компонентах, не в Session.
- Session не имеет параметра "принять только если...".
- Session не обрабатывает `ResearchPipelineException` — это ответственность Policy.

---

## ADR-0014: PlanExecutor Protocol абстрагирует стратегию выполнения плана

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
ResearchSession зависит от ResearchOrchestrator. В Phase 5 потребуется параллельное
или распределённое выполнение. Прямая зависимость → замена требует изменения Session.

**Решение:**
`PlanExecutor` Protocol в `core/research_session/protocols.py`.
`ResearchOrchestrator` реализует его структурно (duck typing) без изменения кода v4.1.
`ResearchSession.__init__` принимает `executor: PlanExecutor`.

**Явное требование: PlanExecutor является stateless-компонентом.**
Реализации не должны хранить изменяемое состояние между вызовами. Один и тот же
экземпляр `PlanExecutor` может быть вызван несколько раз с разными планами, registry
и pipeline — и должен вести себя идентично каждый раз. Это ограничение обеспечивает
возможность безопасной замены на `ParallelPlanExecutor`, `DistributedPlanExecutor` или
`EventAwarePlanExecutor` без изменения контракта `ResearchSession`.

`ResearchOrchestrator` удовлетворяет этому требованию: после конструктора он хранит
только `_clock` (immutable после инициализации), всё состояние выполнения находится
в параметрах `run()`.

**Обоснование:**
Structural typing (Protocol) позволяет ввести абстракцию без изменения
`ResearchOrchestrator`. Statelessness — явный architectural contract, а не предположение.

**Последствия:**
- `ResearchOrchestrator` не изменяется.
- `ParallelPlanExecutor` в Phase 5 реализует тот же Protocol без изменения Session API.
- Реализации, нарушающие statelessness (хранящие результаты между вызовами), запрещены.

---

## ADR-0015: ResearchReport — чистая модель данных с session_id reference

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
`ResearchReport` должен содержать либо полный `ResearchSessionResult` (для дальнейшего
доступа к сырым данным), либо только ссылку `session_id: str`. Хранение полного
объекта удерживает весь граф объектов в памяти (OrchestrationResult, план, все задачи).

**Решение:**
`ResearchReport` хранит `session_id: str` (легковесная ссылка).
`ResearchReport` не встраивает `ResearchSessionResult`. Потребители, которым нужны
сырые данные, должны хранить `ResearchSessionResult` независимо.
`ResearchReport` является замкнутым артефактом: `summary + findings + recommendations`
содержат все данные, необходимые потребителям отчёта.

**Обоснование:**
- Граф объектов `ResearchSessionResult` (планы, задачи, orch_result) не нужен
  большинству потребителей отчёта — им достаточны агрегаты и findings.
- Лёгкая ссылка (`session_id`) позволяет сериализовать отчёт без рекурсивного
  сохранения всего состояния сессии.
- Встраивание создаёт риск мутации shared state (несмотря на `frozen=True`
  в ResearchSessionResult, внутренние ResearchTask mutable).

**Последствия:**
- `ResearchReport` становится самодостаточным артефактом, не требующим контекста.
- Будущий renderer, dashboard или JSON-экспорт работают только с `ResearchReport`.
- Соответствие отчёта сессии определяется по `session_id`.

---

## ADR-0016: HypothesisInfoProvider Protocol — структурная типизация для метаданных

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
`ResearchReportBuilder` нуждается в названии гипотезы и `template_id` для `ResearchFinding`.
Эти данные хранятся в `HypothesisRegistry`. Прямая зависимость билдера на Registry
нарушает принцип разделения ответственностей и делает тест более сложным.

**Решение:**
`HypothesisInfoProvider` Protocol в `core/research_session/protocols.py`:
```python
def get_info(self, hypothesis_ids: list[str]) -> dict[str, HypothesisInfo]: ...
```
`HypothesisInfo` — lightweight frozen dataclass (`hypothesis_id`, `title`, `template_id`).
`ResearchReportBuilder.__init__` принимает `info_provider: HypothesisInfoProvider | None`.
`HypothesisRegistry` удовлетворяет Protocol структурно при наличии совместимого `get_info()`.
Отсутствующие `hypothesis_id` в результате не являются ошибкой — билдер использует
`"(unknown)"` как fallback-заголовок.

**Обоснование:**
- `ResearchReportBuilder` не должен зависеть от конкретного хранилища гипотез.
- Опциональная зависимость позволяет строить отчёты без Registry (например, в тестах).
- Lightweight Protocol (один метод) минимизирует coupling.

**Последствия:**
- `HypothesisRegistry` должен реализовать `get_info()` для структурного соответствия.
- Отчёты без info_provider валидны, но содержат `"(unknown)"` вместо реальных названий.

---

## ADR-0017: pass_threshold перенесён в ResearchSessionConfig (OQ-007 resolved)

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
Порог `0.80` для PASS/FAIL был продублирован: `_VALIDATION_PASS_THRESHOLD = 0.80`
в `session.py` и `_PASS_THRESHOLD = 0.80` в `ValidationReportBuilder` (TD-001, OQ-007).
При изменении порога обновление двух мест неявно — риск расхождения.

**Решение:**
`ResearchSessionConfig` получает поле `pass_threshold: float = 0.80` с валидацией
`0.0 < pass_threshold <= 1.0`. Константа `_VALIDATION_PASS_THRESHOLD` удалена из
`session.py`. `_build_statistics()` читает `config.pass_threshold`. `ResearchReportBuilder`
читает `result.config.pass_threshold`. TD-001 закрыт.

Примечание: `ValidationReportBuilder._PASS_THRESHOLD` остаётся независимым порогом для
валидации в `ValidationReport` (Validation Core). Это не тот же порог — Validation Core
порог применяется к отдельному `ExperimentResult`, Session порог — к агрегированной
`pass_rate` всех окон WalkForward. Оба порога равны 0.80 по умолчанию, но могут
быть настроены независимо.

**Обоснование:**
- Явный параметр делает threshold частью конфигурации, а не скрытой константой.
- Полная обратная совместимость: дефолт 0.80 сохраняет поведение всех существующих
  тестов и кода без изменений.
- Возможность задать другой порог per-session (OQ-003: RANGE-режим может потребовать 0.60).

**Последствия:**
- TD-001 закрыт.
- OQ-007 закрыт.
- OQ-003 становится проще: достаточно передать `pass_threshold=0.60` в конфиг сессии.

---

## ADR-0018: ValidationOutcome enum разделяет семантику отчёта и lifecycle задач

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
`ResearchTaskStatus` содержит COMPLETED/FAILED/SKIPPED/PENDING/IN_PROGRESS.
Для отчёта нужна другая классификация: PASS/FAIL/INCONCLUSIVE/ERROR/SKIPPED.
Прямое использование `ResearchTaskStatus` в report моделях создаёт coupling между
reporting и task lifecycle.

**Решение:**
`ValidationOutcome(str, Enum)` в `core/research_session/report_models.py`:
- `PASS` — `ResearchTaskStatus.COMPLETED` и `pass_rate >= pass_threshold`
- `FAIL` — `ResearchTaskStatus.COMPLETED` и `pass_rate < pass_threshold` (не None)
- `INCONCLUSIVE` — `ResearchTaskStatus.COMPLETED` и `pass_rate is None`
- `ERROR` — `ResearchTaskStatus.FAILED` (pipeline exception)
- `SKIPPED` — `ResearchTaskStatus.SKIPPED`

Маппинг выполняется строго в `ResearchReportBuilder._build_finding()`. Нигде больше.

**Обоснование:**
- Потребители отчёта не должны знать о lifecycle статусах задач.
- `INCONCLUSIVE` — важный семантический случай: эксперимент завершился успешно,
  но валидация не произвела `pass_rate` (например, нет данных). Без отдельного
  `INCONCLUSIVE` этот случай невозможно отличить от `ERROR`.
- Enum (не bool-флаги) делает добавление новых исходов backward-compatible.

**Последствия:**
- Изменение `ResearchTaskStatus` (добавление статусов) не влияет на потребителей отчёта.
- Изменение критериев маппинга требует обновления только `_build_finding()`.

---

## SA-ADR-001: services/ — слой сборки над core/ и experiments/

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
Research Service Alpha (`services/research/`) является первым запускаемым приложением
поверх Core. Необходимо зафиксировать место `services/` в dependency graph.

**Решение:**
`services/` — wiring layer: собирает Core-компоненты через их Protocol-интерфейсы
и является точкой входа для запускаемых сервисов. Разрешённые зависимости:
- `services/` → `core/` (любые модули через их Protocol-интерфейсы)
- `services/` → `experiments/` (конкретные провайдеры для конкретного сервиса)

Запрещено:
- `core/` → `services/`
- `experiments/` → `services/`

**Обоснование:**
Сервисный слой — это composition root: он знает о конкретных реализациях, но
Core об этом знать не должен. Аналог Dependency Injection Container.

**Последствия:**
- `services/research/` импортирует `H13FeatureProvider` и другие конкретные провайдеры.
- Core остаётся независимым от сервисного слоя и тестируется изолированно.
- Добавление нового сервиса = новый пакет в `services/`, Core не меняется.

---

## SA-ADR-002: JsonKnowledgeStorage — KnowledgeRepository через структурную типизацию

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
Research Service нуждается в персистентном `KnowledgeRepository`. `KnowledgeBase`
принимает любой объект, удовлетворяющий `KnowledgeRepository` Protocol (duck typing).
Вопрос именования: назвать сервисный класс `JsonKnowledgeRepository` или иначе?

**Решение:**
`JsonKnowledgeStorage` в `services/research/persistence.py`.
Имя `Storage` (не `Repository`) сигнализирует: это инфраструктурный компонент
сервисного слоя, не реализация Core-домена. Satisfies `KnowledgeRepository` Protocol
структурно (duck typing) — без наследования, без `__implements__`.

**Обоснование:**
Если назвать `JsonKnowledgeRepository`, класс визуально смешивается с Core-концептом.
`Storage` — более точное описание роли: «хранить на диск», а не «управлять domain lifecycle».

**Последствия:**
- `KnowledgeBase(repository=JsonKnowledgeStorage(...))` — стандартное использование.
- Замена на `SQLiteKnowledgeStorage` или `PostgresKnowledgeStorage` прозрачна для Core.

---

## SA-ADR-003: RegistryInfoProviderAdapter — адаптер без изменения Core

**Дата:** 2026-06-27
**Статус:** Accepted

**Контекст:**
`ResearchReportBuilder` принимает `HypothesisInfoProvider` Protocol (ADR-0016).
`HypothesisRegistry` не имеет метода `get_info()`. Варианты:
(1) добавить `get_info()` в `HypothesisRegistry` (изменение Core),
(2) создать адаптер в services/.

**Решение:**
`RegistryInfoProviderAdapter` в `services/research/providers.py`.
Оборачивает `HypothesisRegistry`, реализует `get_info()` через `registry.get()`.
Core не меняется.

**Обоснование:**
`HypothesisRegistry` — lifecycle manager, не информационный провайдер для отчётов.
Добавление `get_info()` смешало бы две ответственности. Adapter — стандартный
паттерн для несовместимых интерфейсов без изменения обоих сторон.

**Последствия:**
- `HypothesisRegistry` остаётся неизменным.
- Adapter живёт в services/ — не в Core. Core остаётся независимым.
- При необходимости `get_info()` в Core — отдельная ADR и обоснование.

---

## Открытые вопросы (не ADR)

> Реестр синхронизирован с `docs/40_PHASE_4_BASELINE.md §9` (2026-06-27, v4.3 baseline).
> Обновлён по итогам Capability 4.4 (2026-06-27) и Research Service Alpha (2026-06-27).
> Примечание: OQ-004 не существует — номер пропущен при создании реестра.

| ID | Вопрос | Целевая Capability | Статус |
|----|--------|-------------------|--------|
| OQ-001 | PaperTradingEngine vs PositionManager: два независимых учёта позиций, связь не определена | Phase 7 | Open |
| OQ-002 | PostgresPositionRepository: заглушка с v1.6.1, реализация не начата | Phase 6 | Open |
| OQ-003 | Порог 80% для RANGE-режима: может ли быть другой порог для стратегий RANGE? | **4.5** | Open |
| OQ-005 | CandidateRanker Protocol + context: нужен ли `regime_context` keyword-only параметр для Regime-Aware ранжирования? | **4.5 prerequisite** | Open |
| OQ-006 | Агрегация KB stats по нескольким тикерам: `get_stats()` суммирует по всем dataset_id, нет фильтрации по режиму | **4.5 prerequisite** | Open |
| OQ-007 | Порог 0.80 в `session.py`: дублирует `ValidationReportBuilder._PASS_THRESHOLD`; рассмотреть `pass_threshold` в `ResearchSessionConfig` | **4.4** | ✅ **Resolved** — ADR-0017 |
| OQ-008 | Per-hypothesis ExperimentConfig: нужен ли `ExperimentConfigProvider` Protocol, когда гипотезы требуют разных конфигов? | Phase 5 | Open |
| OQ-009 | Сохранение `ResearchSessionResult`: нужен ли persist для audit trail? Через какой Protocol? | Phase 6+ | Open |
| OQ-010 | Сохранение `ResearchReport`: нужен ли `ReportRepository` Protocol? Формат (JSON/DB/file)? | Phase 6+ | Open |
