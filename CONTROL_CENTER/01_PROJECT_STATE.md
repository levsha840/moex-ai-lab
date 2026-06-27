# 01_PROJECT_STATE

MOEX AI LAB — актуальное состояние после **v0.9-intelligence-alpha** (2026-06-27).

---

## Era

| Era | Статус |
|-----|--------|
| Foundation Era | ✅ Completed |
| Program Era | ✅ Completed |
| Intelligence Era v1 | ✅ Completed (v0.9-intelligence-alpha) |
| Research Organization Era | 🟡 Active — Design Phase (RO-1) |

---

## Intelligence Era v1 — COMPLETED (v0.9-intelligence-alpha)

| Phase | Agent | Статус |
|-------|-------|--------|
| IE Phase 1 | MarketAgent + AgentProtocol | ✅ |
| IE Phase 2 | MacroAgent | ✅ |
| IE Phase 3 | CorrelationAgent | ✅ |
| IE Phase 4 | RegimeDetectionAgent | ✅ |
| IE Phase 5 | KnowledgeAgent | ✅ |
| IE Phase 6 | ExperimentPlanner | ✅ |
| IE Phase 7 | ValidationAgentAdapter | ✅ |
| IE Phase 8 | ChiefScientist v1 | ✅ |
| Milestone | Autonomous Research Alpha (10 campaigns) | ✅ |

**Tests: 1419 / 1419 passed.**
**Tag: `v0.9-intelligence-alpha`**

---

## Research Organization Era — ACTIVE (RO-1: Design)

Architecture document: `docs/50_RESEARCH_ORGANIZATION_ARCHITECTURE.md`

| Phase | Deliverable | Статус |
|-------|-------------|--------|
| RO-1 | Architecture + Governance document | ✅ Design complete |
| RO-2 | NewsAgent | 🔜 Pending ADR-RO-02 |
| RO-3 | DividendsAgent | 🔜 |
| RO-4 | SectorBreadthAgent | 🔜 |
| RO-5 | FeatureDiscoveryAgent | 🔜 |
| RO-6 | NoveltyDetector | 🔜 |
| RO-7 | StatisticalSignificanceAgent | 🔜 |
| RO-8 | RiskOfficer | 🔜 |
| RO-9 | MetaKnowledgeAgent | 🔜 |
| RO-10 | PolicyEvolutionAgent | 🔜 |

**Freeze Policy active until RO-1 approved.**

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

**782 / 782 passed.**

---

## Intelligence Era — Phase 2: MacroAgent (2026-06-27)

**Статус: COMPLETED.**

### Что реализовано

**`agents/protocols.py`** — добавлен `MacroSource` Protocol:
- `MacroSource.fetch(symbol, timeframe, date_from, date_to) → list[dict]`
- Ряд содержит: `{date, open, high, low, close, volume}`

**`agents/models.py`** — добавлены:
- `MacroSeries` — одна макро-серия: symbol, timeframe, date_from, date_to, value_count, path
- `MacroSnapshot` — результат MacroAgent: snapshot_id, period, observations, source_refs, missing_values, confidence

**`agents/data/macro.py`** — MacroAgent:
- `MoexMacroSource` — MOEX ISS API через stdlib urllib для IMOEX/USDRUB/RGBI
- `FixtureMacroSource` — инъекция тестовых данных по symbol → list[dict]
- `MacroAgent` — реализует AgentProtocol, поддерживает:
  - источники: IMOEX (SNDX engine=stock), USDRUB (USD000UTSTOM, engine=currency), RGBI (SNDX engine=stock)
  - запись CSV в `data/context/macro/{period}/{symbol}_{timeframe}.csv`
  - graceful degradation: missing_values для символов без данных
  - confidence = fetched/requested (0.0–1.0)
  - clock injection для детерминированности
  - пагинация 500 строк/страница как MarketAgent

**66 новых тестов** (tests/agents/):
- test_models.py: +15 тестов — MacroSeries, MacroSnapshot (итого 47)
- test_macro_agent.py: 51 тест — protocol, fixture source, fixture run, missing data, persistence, evidence, determinism

### Ключевые инварианты

```
MacroSnapshot — frozen dataclass, hashable (missing_values как tuple[tuple[str,int],...]).
data/context/macro/ — ОТДЕЛЬНО от data/datasets/. Не читается Research Service.
MacroSource протокол → FixtureMacroSource для тестов без HTTP.
missing_values = tuple(snapshot.missing_values) → dict(snap.missing_values) для удобства.
snapshot_id = f"macro_{period}_{timeframe}"  — детерминированный.
```

### Пример вывода MacroAgent

```python
from pathlib import Path
from agents.data.macro import MacroAgent, FixtureMacroSource, DEFAULT_SYMBOLS

agent = MacroAgent(data_dir=Path("data"))
result = agent.run("2023")
# result.agent_id    → "macro-agent"
# result.agent_type  → "DATA"
# result.output      → MacroSnapshot(
#     snapshot_id="macro_2023_1d",
#     period="2023",
#     observations=(
#         MacroSeries(symbol="IMOEX", value_count=247, path="data/context/macro/2023/IMOEX_1d.csv"),
#         MacroSeries(symbol="USDRUB", value_count=243, ...),
#         MacroSeries(symbol="RGBI",  value_count=247, ...),
#     ),
#     missing_values=(),
#     confidence=ConfidenceScore(value=1.0, reason="all symbols fetched"),
# )
```

### Файлы

```
agents/protocols.py                 ← +MacroSource
agents/models.py                    ← +MacroSeries, +MacroSnapshot
agents/data/macro.py                ← MacroAgent, MoexMacroSource, FixtureMacroSource
tests/agents/test_models.py         ← 47 тестов (+15)
tests/agents/test_macro_agent.py    ← 51 тест (новый)
```

---

## Intelligence Era — Phase 1: Agent Foundation (2026-06-27)

**Статус: COMPLETED.**

### Что реализовано

**`agents/protocols.py`** — структурные контракты:
- `AgentProtocol` — минимальный Protocol для всех агентов (agent_id, agent_type, version, run())
- `CandleSource` — Protocol источника данных для инъекции в MarketAgent

**`agents/models.py`** — доменные модели:
- `EvidenceRef` — ссылка на источник доказательств (source, reference, timestamp)
- `ConfidenceScore` — уверенность агента [0.0, 1.0] с валидацией
- `AgentResult` — универсальный конверт: agent_id, agent_type, version, input_summary, output, evidence, confidence, created_at
- `MarketSnapshot` — краткое описание доступных рыночных данных
- `DatasetManifest` — описание созданного датасета, совместимого с DatasetLoader

**`agents/data/market.py`** — первый реальный Data Agent:
- `MoexIssSource` — MOEX ISS API через stdlib urllib (тот же паттерн, что в Campaign 001)
- `FixtureSource` — инъекция фикстурных данных для детерминированных тестов
- `MarketAgent` — реализует AgentProtocol, поддерживает:
  - timeframes: "1h" (native), "2h" (×2 resample), "4h" (×4 resample), "1d" (daily resample)
  - session_filter: "main" (09:00–18:59 МСК) | "full" (весь день)
  - clock injection (_clock) для детерминированности
  - запись ohlcv.csv + metadata.json совместимо с DatasetLoader
  - auto dataset_id: `{ticker}_{timeframe}_{year}_{session}`

**87 новых тестов** (tests/agents/):
- test_models.py: 32 теста — EvidenceRef, ConfidenceScore, AgentResult, MarketSnapshot, DatasetManifest
- test_market_agent.py: 55 тестов — protocol, session filter, resample, run, DatasetLoader compat

### Ключевые инварианты

```
AgentResult — frozen dataclass. Неизменяем после создания.
ConfidenceScore.value — строго [0.0, 1.0]. ValueError при нарушении.
MoexIssSource — пагинация 500 баров/страница, автоматически полный диапазон.
DatasetLoader совместимость — ohlcv.csv (datetime, open, high, low, close, volume)
                               metadata.json (ticker, timeframe, bar_count, ...)
Core / Research Service — НЕ изменялись.
```

### Пример вывода MarketAgent

```python
from pathlib import Path
from agents.data.market import MarketAgent, FixtureSource

agent = MarketAgent(data_dir=Path("data"))
result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29", session_filter="main")
# result.agent_id    → "market-agent"
# result.agent_type  → "DATA"
# result.version     → "1.0"
# result.confidence  → ConfidenceScore(value=1.0, reason="all bars written...")
# result.output      → DatasetManifest(
#     dataset_id="sber_1h_2023_main",
#     ticker="SBER", timeframe="1h",
#     bar_count=2540, date_from="2023-01-10", date_to="2023-12-29",
#     session_filter="main", source="MOEX ISS API",
#     ohlcv_path="data/datasets/sber_1h_2023_main/ohlcv.csv",
#     ...
# )
```

### Файлы

```
agents/__init__.py
agents/protocols.py                 ← AgentProtocol, CandleSource
agents/models.py                    ← EvidenceRef, ConfidenceScore, AgentResult,
                                       MarketSnapshot, DatasetManifest
agents/data/__init__.py
agents/data/market.py               ← MarketAgent, MoexIssSource, FixtureSource
tests/agents/__init__.py
tests/agents/test_models.py         ← 32 тесты
tests/agents/test_market_agent.py   ← 55 тестов
```

---

## Research Program 002 — H-13 Parameter Sensitivity (2026-06-27)

**Статус: COMPLETED.**

### Метод

5 контролируемых экспериментов: каждый изменяет ровно один параметр.
10 инструментов × 20 конфигураций параметров. Parameterized evaluator — новый код,
ни один существующий файл не изменён.

### Experiment A — Walk-Forward Configuration

| Config | Train | Test | avg | med | delta |
|--------|-------|------|-----|-----|-------|
| A1 baseline | 60 | 20 | 15.8% | 15.3% | — |
| A2 train×2 | 120 | 20 | 15.9% | 15.7% | +0.1% |
| A3 train×4 | 240 | 20 | 16.0% | 16.1% | +0.2% |
| A4 train×2, test×2 | 120 | 40 | 23.8% | 25.0% | +8.0% |
| A5 train×4, test×2 | 240 | 40 | 23.9% | 24.6% | +8.1% |

**Вывод A:** train_size — без эффекта (+0.2%). test_size (20→40) — значимый +8%.
Причина: 20-барный тест (2 торговых дня) слишком шумный для оценки стратегии с hold=5.

### Experiment B — RSI Bounds

| Config | RSI range | avg | delta |
|--------|-----------|-----|-------|
| B1 baseline | [40-60] | 15.8% | — |
| B2 | [35-65] | 19.0% | +3.2% |
| B3 | [30-70] | 19.4% | +3.6% |
| B4 | [25-75] | 19.9% | +4.1% |

**Вывод B:** Умеренный эффект +4.1% при максимальном расширении. RSI[40-60] слишком узкий
для сильного тренда. Но расширение не приближает к 80%.

### Experiment C — ADX Threshold

| Config | Threshold | avg | delta |
|--------|-----------|-----|-------|
| C1 | > 15 | 15.8% | 0.0% |
| C2 | > 20 | 15.8% | 0.0% |
| C3 baseline | > 25 | 15.8% | — |
| C4 | > 30 | 9.2% | -6.6% |
| C5 | > 35 | 5.6% | -10.2% |

**Критическая находка C: ADX-проверка в H-13 сигнале ИЗБЫТОЧНА при threshold<=25.**
MarketRegimeEngine уже требует ADX>=25 для TREND_UP. Параметр `_ADX_THRESHOLD`
в H13StrategyRunner — dead code для любого значения <=25.

### Experiment D — Hold Bars

| Config | hold | avg | delta |
|--------|------|-----|-------|
| D1 | 2 | 14.5% | -1.3% |
| D3 baseline | 5 | 15.8% | — |
| D6 | 15 | 17.2% | +1.4% |

**Вывод D:** Слабый эффект, диапазон 2.7%. Не критичен.

### Experiment E — Timeframe

| Config | Bars | Windows | avg | delta |
|--------|------|---------|-----|-------|
| E1 1H baseline | 2540 | 124 | 15.8% | — |
| E2 2H | 1270 | 60 | 22.2% | +6.4% |
| E3 4H | 635 | 28 | 23.2% | +7.4% |
| E4 1D | 254 | 9 | 27.8% | +12.0% |

**Вывод E:** Сильное направленное влияние. 1D — только 9 окон (ненадёжно).
2H и 4H: хороший компромисс (+6-7%, достаточно окон).

### Сводная таблица влияния параметров

| Параметр | Max delta | Вердикт |
|----------|-----------|---------|
| train_size | +0.2% | НЕТ ЭФФЕКТА |
| test_size | +8.0% | ЗНАЧИМЫЙ |
| RSI bounds | +4.1% | УМЕРЕННЫЙ |
| ADX threshold (<=25) | 0.0% | ИЗБЫТОЧЕН (dead code) |
| hold_bars | +2.7% | СЛАБЫЙ |
| Timeframe | +12.0% | СИЛЬНЫЙ (но 1D статистически слаб) |

### Заключение H-13

**H-13 признана НЕСОСТОЯТЕЛЬНОЙ** в текущей формулировке на MOEX large-cap 1H 2023.

Ни один из 5 экспериментов не приближает avg к 80%. Лучший надёжный результат:
A5 avg=23.9% (57 WF-окон) — в 3.3× ниже порога.

Фундаментальная проблема: оценочная функция `total_pnl > 0` за 20-40-барное окно
при редких сигналах (14%) создаёт структурный FAIL независимо от quality стратегии.

Архитектурный дефект зафиксирован как технический долг:
`_ADX_THRESHOLD` в H13StrategyRunner — dead code при threshold ≤ 25.

Детали: `research_programs/002/H13_PARAMETER_SENSITIVITY.md`

---

## Research Campaign 001 (2026-06-27)

**Статус: COMPLETED.**

### Охват

10 инструментов: SBER, GAZP, LKOH, ROSN, NVTK, TATN, MAGN, GMKN, CHMF, VTBR.
Period: 2023-01-03 – 2023-12-29. Timeframe: 1H. Session: Main (09:00-18:00).
WalkForward: train=60, test=20, step=20. Порог PASS: 80%.

### Итоговая таблица

| # | Ticker | Bars | WF Windows | pass_rate | 2023 return | Outcome | Session ID (prefix) |
|---|--------|------|-----------|-----------|-------------|---------|---------------------|
| 1 | SBER | 2540 | 124 | 20.2% | +91.3% | FAIL | b95d58b79e6045c8 |
| 2 | GAZP | 2540 | 124 | 9.7% | -1.9% | FAIL | 936b1954cdf745c6 |
| 3 | LKOH | 2540 | 124 | 16.1% | +65.8% | FAIL | a324586d128f4d84 |
| 4 | ROSN | 2540 | 124 | 18.5% | +61.6% | FAIL | e744477d40b04ba3 |
| 5 | NVTK | 2540 | 124 | 18.5% | +35.8% | FAIL | ebc5e8b32aae4950 |
| 6 | TATN | 2540 | 124 | 15.3% | +102.9% | FAIL | 9659468697514b6f |
| 7 | MAGN | 2540 | 124 | 14.5% | +58.5% | FAIL | 05c9e909093641f9 |
| 8 | GMKN | 2540 | 124 | 15.3% | +5.4% | FAIL | 2a65b7274bc049a9 |
| 9 | CHMF | 2540 | 124 | 14.5% | +55.3% | FAIL | 9f3c3513e1654ee1 |
| 10 | VTBR | 2540 | 124 | 15.3% | +39.3% | FAIL | 687819cc4ef74371 |

### Campaign Statistics

| Метрика | Значение |
|---------|---------|
| PASS | 0 / 10 |
| Avg pass_rate | 15.8% |
| Median pass_rate | 15.3% |
| Std dev | 2.9% |
| Best | SBER 20.2% |
| Worst | GAZP 9.7% |
| Total WF windows | 1 240 |
| Total KB entries | 10 |

### Артефакты

```
campaigns/001/campaign_report.json       — полный Campaign Report
campaigns/001/campaign_results.json      — raw результаты по инструментам
campaigns/001/reports/<session_id>/      — отчёты по каждому инструменту
campaigns/001/knowledge/knowledge_base.json  — KB кампании (10 записей)
```

### Ключевые выводы

1. **H-13 REJECTED на MOEX large-cap 1H 2023.** 0 из 10 инструментов проходят 80%-порог.
2. **Структурный результат** — std_dev=2.9%. Все pass_rates в диапазоне 9.7-20.2%.
   Это не случайный шум — это системная проблема параметризации.
3. **Нет корреляции с доходностью инструмента.** TATN +103% даёт 15.3%;
   GAZP -2% даёт 9.7%. Стратегия не capture тренд.
4. **Сигнальная плотность (~14% баров) достаточна** — проблема не в отсутствии сигналов,
   а в том, что сигналы не предсказывают прибыльность следующих 20 баров.

### Инженерное заключение

**Pipeline: PRODUCTION READY.** 10 запусков без ошибок.

**H-13: ТРЕБУЕТ ПЕРЕСМОТРА параметров WalkForward.**
Root cause: train=60 баров (~6 торговых дней) недостаточно для стабилизации ADX-паттернов.
Кандидат на следующую исследовательскую кампанию — тест с train=120+ или daily timeframe.

**Данных достаточно** для открытия новой исследовательской программы по H-13 с изменёнными
параметрами WalkForward. Текущие данные (10 инструментов × 2540 баров) остаются в датасетах.

---

## M2 — First Real Research Run (2026-06-27)

**Статус: COMPLETED.**

### Источник данных

**MOEX ISS API** — `iss.moex.com`, stdlib `urllib.request`, без внешних зависимостей.

Endpoint:
```
https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER/candles.json
  ?interval=60&from=2023-01-01&till=2023-12-31&start=<offset>
```
Пагинация: 500 строк/страница, 8 страниц = 3810 баров.

### Датасеты

| ID | Описание | Баров | Период |
|----|----------|-------|--------|
| `sber_1h_2023_real` | Все сессии (09:00-23:00) | 3810 | 2023-01-03 – 2023-12-29 |
| `sber_1h_2023_main` | Только основная сессия (09:00-18:00) | 2540 | 2023-01-03 – 2023-12-29 |

Пути: `data/datasets/sber_1h_2023_real/` и `data/datasets/sber_1h_2023_main/`.
Формат совместим с `DatasetLoader` без изменений Research Service.

### Команды запуска

```bash
# Полный датасет (все сессии)
python -m services.research run --dataset sber_1h_2023_real \
    --description "First Real Research Run — SBER 1H 2023"

# Основная сессия (09:00-18:00)
python -m services.research run --dataset sber_1h_2023_main \
    --description "First Real Research Run — SBER 1H 2023 main session"
```

### Результаты всех запусков

| Запуск | Датасет | pass_rate | Окна WF | Итог |
|--------|---------|-----------|---------|------|
| M1 synthetic | sber_1h_2023 | 31.1% | 106 | FAIL |
| M2a real full | sber_1h_2023_real | 16.6% | 187 | FAIL |
| M2b real main | sber_1h_2023_main | 20.2% | 124 | FAIL |

WF-конфигурация: train=60, test=20, step=20. Порог PASS: 80%.

### Артефакты M2a (полный датасет)

```
reports/b8c1aa32aff8498d8d3796a2a5f5883b/report.json   (gitignored)
reports/b8c1aa32aff8498d8d3796a2a5f5883b/summary.txt
sessions/b8c1aa32aff8498d8d3796a2a5f5883b/session_meta.json
knowledge/knowledge_base.json  ← 3 записи (M1+M2a+M2b)
```

### Ключевые инженерные находки

1. **Вечерняя сессия MOEX (19:00-23:00)** — 33% всех баров, объём 30% от дневного.
   Включение вечерней сессии снижает pass_rate (16.6% vs. 20.2% без неё).
   Для тренд-стратегий, рассчитанных на ликвидный рынок, следует использовать
   только основную сессию.

2. **H-13 FAIL на реальных данных** — pass_rate=20.2% vs. порог 80%.
   Даже в сильный бычий год (SBER +91% в 2023) стратегия не проходит.
   ADX-условия выполняются на 57% баров, сигнальных баров — 13.7%.
   Проблема не в данных, а в текущей параметризации H-13.

3. **WalkForward окно**: train=60 1H-баров ≈ 6 торговых дней — возможно слишком короткое
   для стабилизации ADX-паттернов. Рекомендуется протестировать train=120+.

4. **Воспроизводимость pipeline**: Research Service работает на реальных данных
   без изменений. Exit code=0, все артефакты созданы корректно.

### Инженерное заключение

**Pipeline: READY.** Research Service успешно выполнил первый цикл на реальных данных MOEX.
KB накопил 3 записи. Артефакты сформированы корректно.

**H-13: требует пересмотра.** Текущая параметризация не проходит валидацию.
Следующий шаг: скорректировать параметры H-13 (train_size, RSI-диапазон, hold_bars)
или протестировать альтернативную гипотезу.

---

## M1 — First Research Run (2026-06-27)

**Статус: COMPLETED.**

### Что было сделано

1. **Создан синтетический датасет** `data/datasets/sber_1h_2023/` — 2187 баров (SBER 1H, 2023-01-10 – 2023-12-28).
   GBM с drift=37.5%/год, vol=35%/год, seed=42. Для M1 rehearsal; заменить реальными данными MOEX.

2. **Добавлен smoke-тест** `tests/research_service/test_sber_dataset.py` — 15 тестов:
   валидация metadata.json, формата CSV, ключей candle-dict, OHLC-консистентности, хронологического порядка.
   Тесты используют `skipif` если датасет не найден.

3. **Тесты:** 629 / 629 passed.

4. **Запущен Research Service:**
   ```
   python -m services.research run --dataset sber_1h_2023 --description "H-13 ADX Continuation — SBER 1H 2023 (M1 rehearsal)"
   ```

### Результат первого запуска

| Поле | Значение |
|------|---------|
| Session ID | `e4ddf7f012ab4d1e869724f432da40aa` |
| Dataset | sber_1h_2023 (SBER 1h, 2187 bars) |
| Hypothesis | H-13 ADX Continuation (`tmpl_h13_adx_continuation`) |
| Outcome | **FAIL** |
| pass_rate | 0.311 (31.1%) — порог 80% |
| WF windows | 106 (train=60, test=20, step=20) |
| Рекомендация | ARCHIVE_HYPOTHESIS (priority LOW) |
| KB entries | 1 (EXPERIMENT, tags: RESEARCH, adx_continuation, FAIL) |
| Exit code | 0 (pipeline выполнен) |
| Длительность | 0.094s |

### Артефакты

```
reports/e4ddf7f012ab4d1e869724f432da40aa/report.json      ← полный отчёт (в .gitignore)
reports/e4ddf7f012ab4d1e869724f432da40aa/summary.txt       ← краткая сводка
sessions/e4ddf7f012ab4d1e869724f432da40aa/session_meta.json
knowledge/knowledge_base.json                              ← 1 запись EXPERIMENT
runs/2026-06-27/e4ddf7f012ab4d1e869724f432da40aa/run_meta.json
```

### Интерпретация результата

**Ожидаемо.** Синтетические данные GBM не имеют автокорреляции — трендовые стратегии
не дают систематического edge на случайном блуждании. pass_rate=31% выше случайной
отметки (25%), что может указывать на слабый edge, недостаточный для прохождения порога.

**Следующий шаг M2:** заменить синтетический датасет реальными историческими данными MOEX
(SBER 1H 2023) и повторить цикл. Только тогда результат H-13 будет значим.

### Как запускать

```bash
# Первый запуск (чистый)
python -m services.research run --dataset sber_1h_2023

# С описанием и кастомными параметрами
python -m services.research run \
    --dataset sber_1h_2023 \
    --description "H-13 SBER 1H 2023" \
    --max-candidates 5 \
    --pass-threshold 0.80

# Просмотр предыдущих сессий
python -m services.research list-sessions
```

### Ограничения M1

- Данные синтетические (GBM). Результат не является исследовательским выводом о стратегии H-13.
- `reports/` исключены из git. Артефакты только локальные.
- Knowledge Base накапливается между запусками (`knowledge/knowledge_base.json`).

---

## Текущий релиз

**v4.5-svc Research Service** (2026-06-27)

Новый сервисный слой `services/research/`:
- `config.py` — `ServiceConfig` (все параметры одного запуска)
- `dataset.py` — `OhlcvDataset`, `DatasetLoader` (CSV → candles)
- `providers.py` — `AdxContinuationProviderFactory`, `RegistryInfoProviderAdapter`
- `persistence.py` — `JsonKnowledgeStorage` (KnowledgeRepository via duck typing), `ArtifactWriter`
- `runner.py` — `ResearchRunner.run(config) → RunResult` (сборка всех Core-компонентов)
- `cli.py` + `__main__.py` — `python -m services.research run --dataset <id>`
- `templates.py` — `ALPHA_TEMPLATES` (H13_TEMPLATE)

Артефакты: `reports/<session_id>/report.json`, `sessions/<session_id>/session_meta.json`,
`knowledge/knowledge_base.json`, `runs/<date>/<session_id>/run_meta.json`.

SA-ADR-001 (services/ wiring layer), SA-ADR-002 (JsonKnowledgeStorage duck typing),
SA-ADR-003 (RegistryInfoProviderAdapter). TD-003 закрыт (E2E integration test).
71 новых тестов.

**v4.4 Research Report** (2026-06-27)

Новые компоненты в `core/research_session/`:
- `report_models.py` — `ValidationOutcome`, `RecommendationKind`, `RecommendationPriority`,
  `RecommendationScope`, `HypothesisInfo`, `ResearchFinding`, `ResearchRecommendation`,
  `ReportSummary`, `ResearchReport`;
- `report.py` — `ResearchReportBuilder.build(result) → ResearchReport`;
- `protocols.py` — `HypothesisInfoProvider` Protocol добавлен;
- `models.py` — `ResearchSessionConfig.pass_threshold: float = 0.80` добавлен (ADR-0017).

ADR добавлены: ADR-0015, ADR-0016, ADR-0017, ADR-0018. TD-001 закрыт. OQ-007 закрыт.
56 новых тестов.

---

## Активная фаза

**Phase 4 — Research Intelligence**

Цель: реальные данные MOEX + Knowledge-guided generation + Multi-hypothesis session.

Детали: `docs/20_PHASE_4_RESEARCH_INTELLIGENCE.md`

---

## Services (запускаемые)

| Сервис | Путь | Команда |
|--------|------|---------|
| Research Service | `services/research/` | `python -m services.research run --dataset <id>` |

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
