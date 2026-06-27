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

### 4.1 — Real Data Integration

**Что:** подключить реальные OHLCV-данные MOEX к Research Pipeline.

**Детали:**
- Адаптер для загрузки candle данных из существующего `data_collector`
  или плоских файлов (CSV / JSON) без зависимости от PostgreSQL в Core.
- `DatasetProvider` Protocol — абстракция источника данных для Feature Provider.
- Первые тикеры: SBER, GAZP, LKOH (А-приоритет из MOEX Research Program).

**Зависит от:** существующий `H13FeatureProvider` принимает `list[dict]` —
адаптер только готовит эти данные.

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

## Предполагаемые компоненты

| Компонент | Тип | Путь |
|-----------|-----|------|
| `DatasetProvider` Protocol | Core Protocol | `core/research_pipeline/protocols.py` |
| `FileDatasetProvider` | Adapter | `core/research_pipeline/adapters.py` |
| `KnowledgeRanker` | Ranker impl | `core/hypothesis_generator/ranker.py` |
| `ResearchSession` | Orchestrator | `core/research_pipeline/session.py` |
| `ResearchSessionResult` | Model | `core/research_pipeline/models.py` |
| `ResearchReportBuilder` | Builder | `core/research_pipeline/report.py` |
| `ResearchReport` | Model | `core/research_pipeline/models.py` |
| `RegimeAwareDataSelector` | Utility | `core/regime/selector.py` |

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

1. Минимум 3 гипотезы из MOEX Research Program прошли полный цикл
   на реальных данных MOEX (не синтетических).
2. Knowledge Base содержит минимум 5 записей типа `EXPERIMENT`.
3. `KnowledgeRanker` использует данные KB при генерации новых кандидатов
   и тест подтверждает, что порядок кандидатов меняется относительно `PriorityRanker`.
4. `ResearchSession` запускает серию из 2+ гипотез и возвращает
   корректный `ResearchSessionResult`.
5. Все существующие тесты проходят (358+).

---

## Зависимости

| Зависимость | Статус |
|-------------|--------|
| `HypothesisGenerator` (v3.3) | ✅ Готов |
| `ResearchPipeline` (v3.1) | ✅ Готов |
| `KnowledgeBase` (v2.4) | ✅ Готов |
| `MarketRegimeEngine` (v2.1) | ✅ Готов |
| `HypothesisRegistry` (v2.3) | ✅ Готов |
| Реальные данные MOEX | ⏳ Phase 4.1 |
| `KnowledgeRanker` | ⏳ Phase 4.2 |
| `ResearchSession` | ⏳ Phase 4.3 |
