# 02_ROADMAP

MOEX AI LAB — roadmap после **FC-1 Foundation Closure** (2026-06-27).

---

## Era

| Era | Статус |
|-----|--------|
| Foundation Era | ✅ Completed |
| Program Era | 🟡 Active |

---

## Foundation Era — Completed

Все релизы Foundation Era завершены. Подробности в `docs/10_MASTER_DEVELOPMENT_PROGRAM.md`.

**Итог Foundation Era:**
- 4 независимых контура (Production, Validation, Research, Operations-будущее).
- Детерминированная, тестируемая база (stdlib only, Protocol DI, clock injection).
- Первый рабочий Research Pipeline (Hypothesis → Experiment → KB).
- Hypothesis Generator Module с Template-based генерацией.
- 358 тестов / 358 pass.

---

## Program Era

### Текущая фаза: Phase 4 — Research Intelligence

**Capability-цель:**
> Система способна принять гипотезу из MOEX Research Program, запустить
> Walk-Forward эксперимент на реальных данных MOEX, записать результат
> в Knowledge Base и сгенерировать следующую гипотезу на основе накопленных знаний.

**Компоненты Phase 4:**

| Capability | ID | Статус |
|------------|-----|--------|
| Research Orchestrator | 4.1 | ✅ Completed (v4.1) |
| Knowledge-Guided Generation | 4.2 | ✅ Completed (v4.2) |
| Multi-Hypothesis Research Session | 4.3 | ⏳ Следующий |
| Research Report | 4.4 | 🔜 |
| Regime-Aware Data Selection | 4.5 | 🔜 |

Детали: `docs/20_PHASE_4_RESEARCH_INTELLIGENCE.md`

---

### Phase 5 — Research Automation

**Capability-цель:**
> Автоматический запуск последовательности экспериментов без ручного шага
> для каждой гипотезы.

Планирование начнётся после завершения Phase 4.

---

### Phase 6 — Validation Hardening

**Capability-цель:**
> Многомерная валидация: несколько тикеров, несколько периодов, несколько режимов.

---

### Phase 7 — Operations Core

**Capability-цель:**
> Сопровождение работающих стратегий: deградация, drawdown, audit trail.

---

### Phase 8+ — Горизонт

- AI-guided hypothesis generation
- Live broker execution (T-Invest, MOEX API)
- Portfolio-level risk management
- Multi-asset allocation optimization

---

## Принцип приоритетов

```
Real data experiments > Knowledge accumulation > Automation > Live execution
```

Новые Production-стратегии не добавляются до прохождения Research → Validation цикла
на реальных данных.

---

## Правило

Roadmap — живой документ. После каждого релиза обновляется статус.
Детальный план следующей фазы создаётся только после завершения текущей.
