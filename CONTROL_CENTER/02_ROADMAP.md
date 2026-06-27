# 02_ROADMAP

MOEX AI LAB — roadmap после **v0.9-intelligence-alpha** (2026-06-27).

---

## Era

| Era | Статус |
|-----|--------|
| Foundation Era | ✅ Completed |
| Program Era | ✅ Completed |
| Intelligence Era v1 | ✅ Completed — tag `v0.9-intelligence-alpha` |
| Research Organization Era | 🟡 Active — RO-1 Design |

---

## Research Organization Era — Active

Architecture: `docs/50_RESEARCH_ORGANIZATION_ARCHITECTURE.md`
Research Universe: `docs/60_RESEARCH_UNIVERSE.md`

| Phase | Deliverable | Department | Status |
|-------|-------------|------------|--------|
| RO-1 | Architecture + Governance | — | ✅ |
| RO-UNIVERSE | Research Universe v1 (28 instruments) | — | ✅ |
| RO-2 | NewsAgent | Data Intelligence | 🔜 ADR-RO-02 required |
| RO-3 | DividendsAgent | Data Intelligence | 🔜 |
| RO-4 | SectorBreadthAgent | Analysis Intelligence | 🔜 |
| RO-5 | FeatureDiscoveryAgent | Discovery Intelligence | 🔜 |
| RO-6 | NoveltyDetector | Discovery Intelligence | 🔜 |
| RO-7 | StatisticalSignificanceAgent | Analysis Intelligence | 🔜 |
| RO-8 | RiskOfficer | Validation Intelligence | 🔜 |
| RO-9 | MetaKnowledgeAgent | Knowledge Intelligence | 🔜 |
| RO-10 | PolicyEvolutionAgent | Meta Intelligence | 🔜 |

**Governance:** Each phase requires: agent code + tests + KPI baseline + ADR (if applicable).
**Freeze Policy:** No new agents until RO-1 complete. No changes to IE v1 agents.

---

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
| Multi-Hypothesis Research Session | 4.3 | ✅ Completed (v4.3) |
| Research Report | 4.4 | ✅ Completed (v4.4) |
| **Research Service Alpha** | **4.5-svc** | ✅ **Completed (v4.5-svc)** |
| Regime-Aware Data Selection | 4.5 | 🔜 (после первых реальных данных) |

**Стратегическое решение (2026-06-27):**
Следующий приоритет — реальные данные MOEX и первый полный цикл через Research Service.
Capability 4.5+ возобновляются после получения реальных результатов.

**M1 First Research Run (2026-06-27): COMPLETED** ← synthetic rehearsal
- Датасет: `data/datasets/sber_1h_2023/` (синтетический GBM, 2187 баров)
- Результат: H-13 FAIL, pass_rate=0.311 — ожидаемо для GBM

**M2 First Real Research Run (2026-06-27): COMPLETED** ← real MOEX data
- Источник: MOEX ISS API (stdlib urllib, без зависимостей)
- SBER 1H 2023: H-13 FAIL, pass_rate=0.202 (main session, 2540 bars)

**Research Program 002 (2026-06-27): COMPLETED** ← H-13 Parameter Sensitivity
- 5 controlled experiments (A: WF, B: RSI, C: ADX, D: Hold, E: Timeframe)
- 20 parameter configurations x 10 tickers
- train_size: NO EFFECT. test_size: +8%. RSI: +4%. ADX (<=25): REDUNDANT. Hold: +3%. TF: +12%.
- H-13 CLOSED: avg best=23.9% (57 windows) — 3.3x below 80% threshold
- Critical finding: ADX check in H13StrategyRunner is dead code when threshold<=25
- Report: research_programs/002/H13_PARAMETER_SENSITIVITY.md

**Research Campaign 001 (2026-06-27): COMPLETED** ← 10 instruments cross-analysis
- SBER, GAZP, LKOH, ROSN, NVTK, TATN, MAGN, GMKN, CHMF, VTBR
- 1H 2023, main session only, 2540 bars each, 124 WF windows each
- Результат: 0 / 10 PASS. avg=15.8%, median=15.3%, std=2.9%
- Best: SBER 20.2%. Worst: GAZP 9.7%.
- H-13 REJECTED на MOEX large-cap 1H 2023 (структурный FAIL)
- Артефакты: `campaigns/001/`. KB Campaign: 10 записей.
- Вывод: необходим пересмотр WalkForward-конфигурации H-13 или новая гипотеза.

Детали: `docs/20_PHASE_4_RESEARCH_INTELLIGENCE.md`

---

---

## Intelligence Era — DESIGNED (2026-06-27)

**Архитектурный документ:** `docs/30_INTELLIGENCE_ARCHITECTURE.md`

Следующая эволюция: 6-слойная мультиагентная исследовательская система.

| Слой | Агенты | Роль |
|------|--------|------|
| Layer 1 — Data Agents | Market, Macro, News, Fundamentals, OrderFlow, Correlation | Сбор и нормализация данных |
| Layer 2 — Analysis Agents | Trend, Volatility, Liquidity, Sentiment, Regime, Correlation | Аналитический контекст |
| Layer 3 — Research Agents | FeatureProposer, HypothesisSelector, ExperimentPlanner | Гипотезы и планы |
| Layer 4 — Validation Agent | (существующий Research Service — без изменений) | Валидация |
| Layer 5 — Knowledge Agent | Aggregator, PatternFinder, ConnectionTracer | Интерпретация KB |
| Layer 6 — Chief Scientist | v1 rule-based, v2 ML (Phase 8+) | Стратегическое управление |

**Принцип:** Core и Research Service не изменяются. Агенты строятся поверх платформы.

---

### Phase 5 — Research Automation / Intelligence Era Foundation

**Capability-цель:**
> Определить agent protocols (interfaces) и реализовать Data Layer (Layer 1):
> MarketAgent, MacroAgent, NewsAgent. Тонкий ValidationAgentAdapter к Research Service.

Планирование начнётся при старте Intelligence Era.

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
