# 10_MASTER_DEVELOPMENT_PROGRAM — MOEX AI LAB

> Программа развития платформы. Детальное планирование ведётся только для текущей фазы.
> Следующие фазы описываются на уровне capability-цели без разбивки на релизы.

---

## Текущее состояние (2026-06-27)

- **Era:** Program Era (started)
- **Последний релиз:** v3.3 Hypothesis Generator Module
- **Тестов:** 358 / 358 pass
- **Foundation Era:** Completed (FC-1)

---

## Foundation Era — Completed

Цель Foundation Era: построить детерминированную, тестируемую платформу
с четырьмя независимыми контурами и первым рабочим Research Pipeline.

### Production Core (v1.x)

| Релиз | Название | Результат |
|-------|----------|-----------|
| v1.0 | Foundation | Базовая структура проекта |
| v1.1 | Intraday Data Layer | Модели свечей и хранилище |
| v1.2 | Feature Factory | Вычисление признаков из OHLCV |
| v1.3 | Replay Engine | Детерминированное воспроизведение данных |
| v1.4 | Strategy Engine | BaseStrategy + on_event API |
| v1.5 | Paper Trading Engine | Симуляция исполнения ордеров |
| v1.6 | Position Manager | Учёт позиций (LONG/SHORT, PnL) |
| v1.6.1 | Persistence Layer | PositionRepository Protocol + MemoryImpl |
| v1.7 | Risk Engine | Pre-trade лимиты (ALLOW / REJECT) |
| — | Architecture Refresh | Platform Vision 2.0, четыре контура |
| v1.8 | Portfolio Allocation Engine | Детерминированный allocation layer |
| v1.9.1 | Execution Cost Model | Комиссия, спред, слипидж |
| v1.9.2 | WalkForward Window Generator | Rolling-окна без перекрытий |
| v1.9.3 | WalkForward Engine | Generic runner по окнам |
| v1.9.4 | Architecture Cleanup | Удаление legacy, унификация OrderSide |

### Validation Core (v2.0)

| Релиз | Название | Результат |
|-------|----------|-----------|
| v2.0 | Validation Report | ValidationReportBuilder, PASS/FAIL, pass_rate >= 0.80 |

### Research Core (v2.1 – v3.3)

| Релиз | Название | Результат |
|-------|----------|-----------|
| v2.1 | Market Regime Engine | MarketRegimeEngine, 5 режимов, детерминированная классификация |
| v2.2 | Experiment Runner | ExperimentRunner, 4 Protocol-интерфейса, ExperimentResult |
| v2.3 | Hypothesis Registry | HypothesisRegistry, 9 статусов, lifecycle enforcement |
| v2.4 | Knowledge Base | KnowledgeBase, KnowledgeEntry, 6 типов знаний |
| v3.1 | First Research Pipeline | ResearchPipeline, адаптеры, end-to-end интеграция |
| v3.2 | H-13 Synthetic Experiment | adx(), H13Dataset, proof-of-pipeline |
| v3.3 | Hypothesis Generator Module | HypothesisTemplate, GenerationSession, PriorityRanker |

### Foundation Closure

| Событие | Дата |
|---------|------|
| FC-1 Documentation System | 2026-06-27 |

---

## Program Era — текущая фаза

**Цель Program Era:** превратить платформу в систему, способную самостоятельно
вести исследовательские программы — планировать, исполнять и накапливать знание
по набору гипотез.

Программа Era состоит из независимых фаз. Фазы не имеют жёстких дат — они завершаются
по capability-критериям.

---

## Phase 4 — Research Intelligence (текущая)

Детали: `20_PHASE_4_RESEARCH_INTELLIGENCE.md`

**Цель:** подключить реальные данные MOEX, запустить первые содержательные
эксперименты по гипотезам из MOEX Research Program, реализовать Knowledge-guided
генерацию.

**Capability-критерий завершения:**
> Система способна принять гипотезу из MOEX Research Program, запустить
> Walk-Forward эксперимент на реальных данных MOEX, записать результат
> в Knowledge Base и сгенерировать следующую гипотезу на основе накопленных знаний.

---

## Phase 5 — Research Automation (следующая)

**Цель capability:** запускать последовательность экспериментов по расписанию
без ручного вмешательства для каждого шага.

Ключевые вопросы фазы:
- Как автоматизировать переход IDEA → RESEARCH → результат?
- Как приоритизировать следующий эксперимент по данным Knowledge Base?
- Что является критерием «достаточного исследования» гипотезы?

---

## Phase 6 — Validation Hardening

**Цель capability:** расширить Validation Core до многомерной проверки стратегий
(несколько временных периодов, несколько тикеров, несколько режимов рынка).

---

## Phase 7 — Operations Core

**Цель capability:** сопровождать работающие стратегии: deградация, drawdown,
автоматическое снижение или отключение позиций, audit trail.

---

## Phase 8+ — Горизонт

Следующие направления важны, но не планируются детально до завершения Phase 6:

- AI-guided hypothesis generation
- Live broker execution (T-Invest, MOEX API)
- Portfolio-level risk management
- Cross-strategy correlation analysis
- Multi-asset allocation optimization

---

## Критерии пересмотра программы

Программа пересматривается при:

1. **Провале capability-критерия фазы** — если реализация показала,
   что цель недостижима в текущей архитектуре.
2. **Изменении рыночного доступа** — подключение live broker меняет
   приоритеты Operations Core.
3. **Накоплении 50+ Knowledge Base записей** — достаточно данных для
   пересмотра приоритетов Research Program.
4. **Архитектурном событии** — обнаружение принципиального ограничения
   текущей модели данных или dependency graph.

Пересмотр не означает сброс. Он означает обновление приоритетов с сохранением
достигнутого.

---

## Принцип планирования

> Детально планируется только текущая фаза.
> Следующие фазы описываются на уровне capability.
> Детальный план фазы N+1 создаётся только после завершения фазы N.
