# 30_INTELLIGENCE_ARCHITECTURE — Intelligence Era

> Архитектурный документ следующего поколения MOEX AI LAB.
> Статус: **ACTIVE** — реализация начата (IE Phase 1 + Phase 2 ✅).
> Дата: 2026-06-27

**Реализованные компоненты:**
| Компонент | Статус | Файл |
|-----------|--------|------|
| Agent Protocol + Domain Models | ✅ IE Phase 1 | `agents/protocols.py`, `agents/models.py` |
| MarketAgent (IMOEX ISS, 1h/2h/4h/1d, session filter) | ✅ IE Phase 1 | `agents/data/market.py` |
| MacroSource Protocol | ✅ IE Phase 2 | `agents/protocols.py` |
| MacroSeries + MacroSnapshot models | ✅ IE Phase 2 | `agents/models.py` |
| MacroAgent (IMOEX, USDRUB, RGBI, 1d) | ✅ IE Phase 2 | `agents/data/macro.py` |

---

## Контекст

### Что уже есть (Program Era — работающее ядро)

```
┌─────────────────────────────────────────────────────────────────┐
│                    СУЩЕСТВУЮЩАЯ ПЛАТФОРМА                        │
│                                                                   │
│  DatasetLoader ──► Research Service ──► WalkForwardEngine         │
│       ▲                   │                     │                 │
│  MOEX ISS API             ▼                     ▼                 │
│  (stdlib urllib)    ResearchRunner        ValidationReport        │
│                           │                     │                 │
│                           ▼                     ▼                 │
│                    JsonKnowledgeStorage   KnowledgeBase           │
│                                                                   │
│  Hypothesis Registry (lifecycle: IDEA → DRAFT → BACKTEST → PROD) │
│  35 гипотез в каталоге (7 категорий)                              │
│  629 детерминированных тестов                                     │
└─────────────────────────────────────────────────────────────────┘
```

**Платформа доказала работоспособность.** Ограничение текущей эры: каждый шаг цикла
требует ручного вмешательства инженера. Intelligence Era автоматизирует этот цикл.

---

## Цель Intelligence Era

Превратить MOEX AI LAB из **ручного исследовательского инструмента** в
**автономную исследовательскую систему**, где:

- данные собираются агентами автоматически;
- анализ ситуации на рынке выполняется непрерывно;
- гипотезы отбираются и планируются на основе накопленных знаний;
- валидация запускается через существующий Research Service без вмешательства;
- Knowledge Base агрегируется и интерпретируется;
- Chief Scientist управляет всем циклом и принимает стратегические решения.

---

## Архитектурная схема — полный обзор

```
╔══════════════════════════════════════════════════════════════════════╗
║                    INTELLIGENCE ERA — OVERVIEW                       ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │             LAYER 6 — CHIEF SCIENTIST                        │    ║
║  │   Читает всю KB. Выбирает направления. Управляет кампаниями. │    ║
║  └──────────────────────┬──────────────────────────────────────┘    ║
║                         │  ResearchDirective                         ║
║          ┌──────────────┘                                            ║
║          ▼                                                            ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │             LAYER 5 — KNOWLEDGE AGENT                        │    ║
║  │   Aggregator │ PatternFinder │ ConnectionTracer              │    ║
║  └──────────────────────┬──────────────────────────────────────┘    ║
║                         │  KnowledgeDigest                           ║
║          ┌──────────────┘                                            ║
║          ▼                                                            ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │             LAYER 4 — VALIDATION AGENT                       │    ║
║  │         (существующий Research Service — без изменений)      │    ║
║  └──────────────────────┬──────────────────────────────────────┘    ║
║                         │  RunResult → Knowledge Base                ║
║          ┌──────────────┘                                            ║
║          ▼                                                            ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │             LAYER 3 — RESEARCH AGENTS                        │    ║
║  │   FeatureProposer │ HypothesisSelector │ ExperimentPlanner   │    ║
║  └───────────────┬─────────────────────────────────────────────┘    ║
║                  │  AnalysisContext                                   ║
║          ┌───────┘                                                   ║
║          ▼                                                            ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │             LAYER 2 — ANALYSIS AGENTS                        │    ║
║  │  TrendAnalyst │ VolatilityAnalyst │ LiquidityAnalyst         │    ║
║  │  SentimentAnalyst │ RegimeDetector │ CorrelationAnalyst      │    ║
║  └───────────────┬─────────────────────────────────────────────┘    ║
║                  │  RawData                                          ║
║          ┌───────┘                                                   ║
║          ▼                                                            ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │             LAYER 1 — DATA AGENTS                            │    ║
║  │  MarketAgent │ MacroAgent │ NewsAgent                         │    ║
║  │  FundamentalsAgent │ OrderFlowAgent │ CorrelationAgent        │    ║
║  └───────────────┬─────────────────────────────────────────────┘    ║
║                  │                                                    ║
║          ┌───────┘                                                   ║
║          ▼                                                            ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │             ВНЕШНИЕ ИСТОЧНИКИ ДАННЫХ                         │    ║
║  │   MOEX ISS API │ Brent/ICE │ USD/RUB │ RGBI │ RUONIA        │    ║
║  │   Корпоративный календарь │ Новости │ Консенсус-оценки       │    ║
║  └─────────────────────────────────────────────────────────────┘    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Layer 1 — Data Agents

Отвечают исключительно за сбор и нормализацию данных из внешних источников.
Не выполняют анализа. Выходные данные — структурированные, версионированные датасеты.

---

### Market Agent

**Назначение:** получить OHLCV-данные по инструментам MOEX и сформировать датасеты,
совместимые с существующим `DatasetLoader`.

**Источники:**
- MOEX ISS API (уже интегрирован): `engines/stock/markets/shares/boards/TQBR`
- Параметры: interval=60 (1H), interval=24 (1D), пагинация по 500 баров
- Фильтрация сессии: main (09:00–18:00 МСК) или full (09:00–23:00 МСК)

**Выходные данные:**
```
OhlcvDataset:
  dataset_id: str                  # e.g. "sber_4h_2023_main"
  ticker: str
  timeframe: str                   # "1h" | "4h" | "1d"
  candles: tuple[dict]             # {ticker, ts, open, high, low, close, volume}
  bar_count: int
  date_from: str
  date_to: str
  session_filter: str              # "main" | "full"
```

**Ответственность:** запрос данных, пагинация, фильтрация по сессии, запись в
`data/datasets/<id>/ohlcv.csv + metadata.json`.

---

### Macro Agent

**Назначение:** получить макроэкономические индикаторы, влияющие на MOEX.

**Источники:**
- MOEX ISS: `engines/currency/markets/selt/boards/CETS/` → USD/RUB (USDRUB_TOM)
- MOEX ISS: `engines/bond/markets/bonds/boards/TQOB/` → RGBI (Russian Govt Bond Index)
- MOEX ISS: `engines/stock/markets/index/boards/SNDX/` → IMOEX
- CBR API: RUONIA (ставка однодневного РЕПО), ставка ЦБ РФ
- ICE/EIA: Brent (через публичные агрегаторы — требует оценки источника)

**Выходные данные:**
```
MacroSnapshot:
  date: str
  usd_rub_close: float
  usd_rub_return_1d: float
  rgbi_close: float
  rgbi_return_5d: float
  imoex_close: float
  imoex_return_1d: float
  brent_usd: float | None          # если источник подключён
  ruonia_rate: float | None        # если ЦБ API доступен
  cbr_key_rate: float | None
```

**Ответственность:** ежедневное обновление макро-слоя, расчёт rolling-изменений,
хранение в `data/macro/<date>.json`.

---

### News Agent

**Назначение:** формировать событийный календарь — даты корпоративных событий,
влияющих на цену.

**Источники:**
- MOEX ISS корпоративный календарь: `/iss/securities/<ticker>/dividends.json`
- MOEX ISS: даты закрытия реестра, SPO-объявления
- Публичные раскрытия (ЦБ/ФСФР disclosure.ru — HTML-парсинг)

**Выходные данные:**
```
EventCalendar:
  events: list[MarketEvent]

MarketEvent:
  ticker: str
  date: str
  event_type: str    # DIVIDEND_EX | DIVIDEND_RECORD | EARNINGS |
                     # BUYBACK_START | BUYBACK_END | SPO_ANNOUNCE | SPO_CLOSE
  payload: dict      # event-specific: {dividend_rub, yield_pct} | {earnings_surprise_pct}
```

**Ответственность:** агрегация событий, дедупликация, хранение в
`data/events/<ticker>/<year>.json`. Нет анализа — только факты.

---

### Fundamentals Agent

**Назначение:** получить фундаментальные метрики по инструментам.

**Источники:**
- MOEX ISS: `/iss/securities/<ticker>/` → дивидендная доходность, free-float
- MOEX ISS: buyback-раскрытия
- Публичные годовые отчёты (для P/E, долговой нагрузки — ограниченная автоматизация)

**Выходные данные:**
```
FundamentalSnapshot:
  ticker: str
  date: str
  annual_dividend_yield_pct: float | None
  free_float_pct: float | None
  buyback_active: bool
  buyback_volume_pct: float | None    # % от free float
  market_cap_bln_rub: float | None
```

**Ответственность:** обновление при выходе корпоративных событий, хранение в
`data/fundamentals/<ticker>.json`.

---

### Order Flow Agent

**Назначение:** анализировать структуру торгового потока — относительный объём,
паттерны активности по времени суток.

**Источники:**
- MOEX ISS: volume данные из OHLCV (достаточно для первой версии)
- MOEX ISS Trade Statistics: `/iss/engines/stock/markets/shares/trades/` (опционально)

**Выходные данные:**
```
OrderFlowStats:
  ticker: str
  date: str
  session_hour: int               # час торгов (10, 11, ..., 18)
  volume_abs: float
  relative_volume: float          # volume / avg_volume_same_hour_20d
  volume_ratio_vs_day: float      # объём часа / дневной объём
  is_opening_surge: bool          # relative_volume > 2.0 в первый час
  is_closing_surge: bool          # relative_volume > 2.0 в последний час
```

**Ответственность:** статистика активности по часам. Хранение агрегатов в
`data/orderflow/<ticker>/<year>.json`.

---

### Correlation Agent

**Назначение:** вычислять кросс-рыночные и кросс-инструментальные корреляции.

**Источники:** выходные данные Market Agent + Macro Agent (производный агент — работает
поверх Layer 1, но является частью Data Layer как данные-результаты, не анализ).

**Выходные данные:**
```
CorrelationMatrix:
  date: str
  window_days: int               # 20 | 60 | 252
  pairs: list[CorrelationPair]

CorrelationPair:
  asset_a: str                   # "LKOH" | "BRENT" | "USDRUB"
  asset_b: str
  pearson_r: float
  lag_days: int                  # 0 = синхронная, 1 = A предсказывает B через 1 день
  rolling_window: int
```

**Ответственность:** поддержание актуальной матрицы корреляций для Cross Market гипотез
(H-26 – H-30). Хранение в `data/correlations/<date>.json`.

---

## Layer 2 — Analysis Agents

Трансформируют сырые данные Layer 1 в структурированное понимание рыночного контекста.
Каждый агент независим: анализирует только свою аналитическую ось.

---

### Trend Analyst

**Вход:** `OhlcvDataset` от Market Agent

**Выход:**
```
TrendReport:
  ticker: str
  date: str
  timeframe: str
  adx_14: float
  sma20: float
  sma50: float
  trend_direction: str          # "UP" | "DOWN" | "FLAT"
  trend_strength: str           # "STRONG" (ADX>35) | "MODERATE" (25-35) | "WEAK" (<25)
  trend_duration_bars: int      # сколько баров текущий тренд не менялся
  key_resistance: float | None
  key_support: float | None
  rsi_14: float
```

**Ответственность:** определить направление и силу тренда. Использует существующие
Core-индикаторы (ADX, SMA, RSI из `core/features/technical_indicators`).
Вызывает `MarketRegimeEngine` — не дублирует, а расширяет его выход временнóй информацией.

---

### Volatility Analyst

**Вход:** `OhlcvDataset` от Market Agent

**Выход:**
```
VolatilityReport:
  ticker: str
  date: str
  atr_14: float
  atr_pct: float                 # ATR / close
  realized_vol_20d: float        # std(returns) × sqrt(252)
  vol_percentile_126d: float     # [0, 1] — текущий ранг HV среди полугода
  bb_width: float                # (BB_upper - BB_lower) / BB_middle
  atr_contraction: bool          # atr_5d < 0.5 × atr_20d
  vol_regime: str                # "SQUEEZE" | "NORMAL" | "ELEVATED" | "SPIKE"
  atr_ratio: float               # atr_today / atr_20d_avg
```

**Ответственность:** режим волатильности, сигналы сжатия и экспансии. Критично для
H-17 (Volatility Squeeze), H-11 (ATR Expansion), H-20 (ATR Contraction).

---

### Liquidity Analyst

**Вход:** `OrderFlowStats` от Order Flow Agent + `OhlcvDataset`

**Выход:**
```
LiquidityReport:
  ticker: str
  date: str
  avg_hourly_volume: dict[int, float]    # средний объём по часам
  peak_hour: int                         # час с максимальным avg volume
  trough_hour: int                       # час с минимальным avg volume
  opening_volume_ratio: float            # объём 10-11ч / дневной avg
  closing_volume_ratio: float            # объём 17-18ч / дневной avg
  lunch_volume_ratio: float              # объём 12-14ч / дневной avg
  spread_proxy_pct: float                # avg(high-low)/close за последние 20д
  tradeable_hours: list[int]             # часы с relative_volume > 0.8
```

**Ответственность:** профиль ликвидности инструмента по часам. Критично для
H-01 (Opening Drive), H-02 (Closing Pressure), H-06 (Lunch Effect).

---

### Sentiment Analyst

**Вход:** `EventCalendar` от News Agent + `OrderFlowStats`

**Выход:**
```
SentimentReport:
  ticker: str
  date: str
  event_proximity: dict[str, int]    # event_type → days_to_event (отрицательный = прошёл)
  pre_event_pressure: str | None     # "BUY" | "SELL" — накопленный поток за 5д до события
  post_event_drift: str | None       # "UP" | "DOWN" — направление после события
  dividend_yield_pct: float | None
  days_to_record_date: int | None
  is_ex_dividend_day: bool
  is_earnings_window: bool           # ±3 дня от даты отчётности
```

**Ответственность:** событийный контекст и его влияние на потоки. Критично для
H-21 (Dividend Gap), H-22 (Pre-Dividend Run-Up), H-23 (PED).

---

### Regime Detector

**Вход:** `TrendReport` + `VolatilityReport` (использует существующий MarketRegimeEngine)

**Выход:**
```
RegimeReport:
  ticker: str
  date: str
  regime: str                   # TREND_UP | TREND_DOWN | RANGE | HIGH_VOLATILITY
  regime_reasons: list[str]     # из MarketRegimeEngine.classify().reasons
  regime_duration_bars: int     # сколько баров не менялся текущий режим
  regime_change_detected: bool  # True, если режим изменился за последние N баров
  prev_regime: str | None
  stability_score: float        # [0, 1] — насколько устойчив режим (ADX + vol)
```

**Ответственность:** расширить выход MarketRegimeEngine временнóй историей режима.
Критично для ВСЕХ гипотез, использующих regime-фильтр (H-07, H-09, H-12, H-13...).

---

### Correlation Analyst

**Вход:** `CorrelationMatrix` от Correlation Agent

**Выход:**
```
CorrelationReport:
  date: str
  active_pairs: list[ActivePair]

ActivePair:
  asset_a: str
  asset_b: str
  lag_days: int
  pearson_r: float
  signal_strength: str          # "STRONG" (|r|>0.7) | "MODERATE" (0.5-0.7) | "WEAK"
  stable_30d: bool              # корреляция не изменилась ±0.2 за 30 дней
  hypothesis_ids: list[str]     # H-26, H-27, H-28, H-29, H-30
```

**Ответственность:** выявить активные и стабильные кросс-рыночные зависимости.
Направляет Research Agents к Cross Market гипотезам при обнаружении сильных связей.

---

## Layer 3 — Research Agents

Принимают аналитический контекст (Layer 2) и директивы Chief Scientist (Layer 6),
формируют конкретные задачи для Research Service (Layer 4).

---

### Feature Proposer

**Назначение:** определить, каких признаков не хватает для тестирования приоритетных
гипотез из каталога.

**Вход:**
- `AnalysisBundle` (все выходы Layer 2)
- Каталог гипотез: `docs/research/MOEX_RESEARCH_PROGRAM.md` (35 гипотез)
- Текущий FeatureSet (известные Core-индикаторы)

**Выход:**
```
FeatureProposal:
  feature_name: str              # "is_opening_window", "volume_ratio_20d"
  formula: str                   # описание вычисления
  data_source: str               # Market | Macro | News | OrderFlow
  priority: str                  # "A" | "B" | "C"
  unlocks_hypotheses: list[str]  # ["H-01", "H-03", "H-08"]
  implementation_complexity: str # "LOW" | "MEDIUM" | "HIGH"
  already_computable: bool       # True если есть в Layer 2 outputs
```

**Ответственность:** мост между аналитическими данными и требованиями гипотез.
Формирует backlog новых признаков для Feature Engineering.

---

### Hypothesis Selector

**Назначение:** из 35 гипотез каталога выбрать наиболее перспективные для запуска
в следующий Research цикл.

**Вход:**
- `KnowledgeDigest` от Knowledge Agent (результаты прошлых экспериментов)
- `RegimeReport` (текущий рыночный режим)
- `CorrelationReport` (активные кросс-рыночные связи)
- `ResearchDirective` от Chief Scientist (приоритеты)
- Статус гипотез в `HypothesisRegistry`

**Выход:**
```
SelectionResult:
  selected: list[HypothesisCandidate]

HypothesisCandidate:
  hypothesis_id: str             # "H-07", "H-12"
  title: str
  rationale: str                 # почему выбрана именно эта
  priority_score: float          # [0, 1]
  required_features: list[str]   # список признаков, нужных для теста
  features_available: bool       # все ли признаки уже есть
  estimated_windows: int         # ожидаемое кол-во WF-окон
  regime_match: bool             # текущий режим подходит для гипотезы
```

**Ответственность:** не угадывать, что сработает — выбирать, что имеет наилучшее
обоснование при текущих данных и накопленных знаниях.

---

### Experiment Planner

**Назначение:** перевести `HypothesisCandidate` в конкретный план запуска
через существующий Research Service.

**Вход:**
- `HypothesisCandidate` от Hypothesis Selector
- `OhlcvDataset` по нужным тикерам (от Market Agent)
- `MacroSnapshot` (контекст для Cross Market гипотез)

**Выход:**
```
ExperimentPlan:
  hypothesis_id: str
  dataset_ids: list[str]         # какие датасеты использовать
  service_config: ServiceConfig  # прямой вход для ResearchRunner
  expected_signal_frequency: float  # оценка % баров с сигналом
  wf_window_rationale: str       # почему выбраны train/test/step
  success_criteria: dict         # pass_rate, sharpe, profit_factor
  fallback_config: ServiceConfig | None  # если primary не даёт статистики
```

**Ответственность:** подбор WF-конфигурации с учётом уроков Research Program 002
(test_size должен быть ≥ 40 баров; train_size ≥ 2× max hold_bars; достаточно окон).

---

## Layer 4 — Validation Agent

**Существующий Research Service — без изменений.**

```
python -m services.research run --dataset <id>
```

**Роль в общей архитектуре:**

Validation Agent — это тонкий адаптер, который:
1. принимает `ExperimentPlan` от Experiment Planner
2. переводит его в вызов `ResearchRunner.run(ServiceConfig)`
3. запускает WalkForwardEngine → ValidationReport → JsonKnowledgeStorage
4. возвращает `RunResult` со ссылкой на сессию и исходом

```
ExperimentPlan
     │
     ▼
ValidationAgentAdapter.execute(plan) → ResearchRunner.run(config)
     │
     ├─► reports/<session_id>/report.json
     ├─► sessions/<session_id>/session_meta.json
     ├─► knowledge/knowledge_base.json   ◄── Layer 5 читает отсюда
     └─► RunResult {session_id, outcome, pass_rate, windows}
```

**Ограничение:** не добавлять логику в Research Service.
Вся конфигурация передаётся через `ServiceConfig`. Адаптер — строго wiring-код.

---

## Layer 5 — Knowledge Agent

Трансформирует сырую базу знаний в структурированное понимание того,
что работает, что не работает и почему.

---

### Aggregator

**Вход:** `knowledge/knowledge_base.json` (все `RunResult` за всё время)

**Выход:**
```
KnowledgeDigest:
  total_experiments: int
  total_pass: int
  total_fail: int
  pass_rate_overall: float

  by_hypothesis: dict[str, HypothesisSummary]
  by_regime: dict[str, float]          # pass_rate при каждом режиме
  by_timeframe: dict[str, float]       # pass_rate по таймфреймам
  by_ticker: dict[str, float]          # pass_rate по инструментам
  by_category: dict[str, float]        # pass_rate по категориям гипотез

  top_performers: list[str]            # hypothesis_id с pass_rate > 50%
  confirmed_fails: list[str]           # hypothesis_id с pass_rate < 10% на 3+ кампаниях
  open_questions: list[str]            # гипотезы с высокой дисперсией результатов
```

---

### Pattern Finder

**Вход:** `KnowledgeDigest`

**Выход:**
```
PatternReport:
  cross_hypothesis_patterns: list[Pattern]
  feature_correlations: list[FeatureCorrelation]
  regime_sensitivity: dict[str, dict]  # hypothesis_id → {regime → pass_rate}
  timeframe_sensitivity: dict[str, dict]

Pattern:
  description: str
  affected_hypotheses: list[str]
  evidence: str                 # "H-13: ADX redundant (C1=C2=C3). Mechanism: MarketRegimeEngine"
  confidence: str               # "HIGH" | "MEDIUM" | "LOW"
  implication: str              # что делать с этим знанием
```

**Примеры паттернов, которые будут найдены автоматически:**
- "Стратегии с hold < 5 баров на 1H показывают < 15% pass_rate — недостаточно времени"
- "Cross Market гипотезы требуют vol > 0.5 корреляции для наличия edge"
- "Calendar эффекты устойчивее в начале квартала (Q1-start) чем в конце"

---

### Connection Tracer

**Вход:** `KnowledgeDigest` + каталог гипотез (35 гипотез, 7 категорий)

**Выход:**
```
ConnectionMap:
  connections: list[HypothesisConnection]

HypothesisConnection:
  from_id: str
  to_id: str
  connection_type: str     # "SAME_MECHANISM" | "SHARED_FEATURE" | "COMPLEMENTARY"
                           # "CONTRADICTS" | "PREREQUISITE"
  description: str
  action_suggestion: str   # "если H-07 PASS, попробовать H-09 (общий механизм)"
```

**Примеры связей:**
- H-07 (RSI Oversold) — SAME_MECHANISM → H-09 (Bollinger Reversion): оба mean reversion
- H-26 (Brent→LKOH) — COMPLEMENTARY → H-28 (USD/RUB→Exporters): общий фактор
- H-12 (N-Day Breakout) — PREREQUISITE → H-17 (Volatility Squeeze): squeeze часто предшествует breakout
- H-21 (Dividend Gap) — SAME_MECHANISM → H-10 (Overnight Gap Fill): оба gap recovery

---

## Layer 6 — Chief Scientist

Главный агент системы. Единственный, кто принимает стратегические решения.
Читает весь Knowledge Agent output и формирует директивы для следующего цикла.

---

### Входные данные

```
ChiefScientistContext:
  knowledge_digest: KnowledgeDigest       # от Aggregator
  pattern_report: PatternReport            # от Pattern Finder
  connection_map: ConnectionMap            # от Connection Tracer
  current_regime: RegimeReport             # от Layer 2
  available_hypotheses: list[str]          # из каталога, не запущенные
  active_experiments: list[str]            # в process
  budget_constraints: BudgetConstraints    # лимиты времени/ресурсов на кампанию
```

---

### Выходные данные

```
ResearchDirective:
  priority_hypotheses: list[str]     # что запустить в следующую кампанию
  archive_decisions: list[str]       # что архивировать с обоснованием
  new_experiment_requests: list[ExperimentRequest]
  focus_areas: list[str]             # категории с высоким потенциалом
  anti_focus: list[str]              # категории/подходы, исключённые из следующего цикла
  cross_hypothesis_tests: list[str]  # комбинации для проверки синергии
  knowledge_gaps: list[str]          # что нужно узнать для следующего шага

ExperimentRequest:
  hypothesis_id: str
  rationale: str                     # почему сейчас и почему именно эта гипотеза
  suggested_tickers: list[str]
  suggested_wf_config: dict          # train, test, step
  expected_learning: str             # что узнаем независимо от PASS/FAIL
```

---

### Логика принятия решений

```
1. ЧИТАЕТ весь Knowledge Base через Knowledge Agent
        │
        ▼
2. ОЦЕНИВАЕТ каждую гипотезу из каталога:
   ├─ Уже тестировалась? → Сколько экспериментов? Какой итог?
   ├─ Режим подходит для этой гипотезы?
   ├─ Есть паттерн, связывающий её с уже подтверждёнными?
   └─ Требуемые данные доступны?
        │
        ▼
3. АРХИВИРУЕТ гипотезы при условии:
   ├─ ≥ 3 независимые кампании → pass_rate < 15% → архивировать
   ├─ Структурное объяснение FAIL подтверждено (как H-13: ADX redundancy)
   └─ Улучшение параметрами невозможно (sensitivity analysis проведён)
        │
        ▼
4. ВЫБИРАЕТ следующие гипотезы по критериям:
   ├─ Приоритет A из каталога + данные доступны
   ├─ Связь с известным успешным экспериментом (ConnectionMap)
   ├─ Максимальное обучение при любом исходе
   └─ Диверсификация: не более 2 гипотез из одной категории подряд
        │
        ▼
5. ФОРМИРУЕТ ResearchDirective и передаёт Layer 3
```

---

## Последовательность работы — полный цикл

```
┌──────────────────────────────────────────────────────────────────┐
│                    AUTONOMOUS RESEARCH CYCLE                      │
└──────────────────────────────────────────────────────────────────┘

  START / TRIGGER (расписание или событие)
          │
          ▼
  ┌── Layer 1: Data Agents ─────────────────────────────────────┐
  │   MarketAgent     → обновить датасеты (новые бары)          │
  │   MacroAgent      → обновить MacroSnapshot                  │
  │   NewsAgent       → обновить EventCalendar                  │
  │   FundamentalsAgent → проверить обновления                  │
  │   OrderFlowAgent  → обновить профиль активности             │
  │   CorrelationAgent → пересчитать корреляционную матрицу     │
  └─────────────────────────────────────────────────────────────┘
          │
          ▼
  ┌── Layer 2: Analysis Agents (параллельно) ───────────────────┐
  │   TrendAnalyst     → TrendReport per ticker                 │
  │   VolatilityAnalyst→ VolatilityReport per ticker            │
  │   LiquidityAnalyst → LiquidityReport per ticker             │
  │   SentimentAnalyst → SentimentReport per ticker             │
  │   RegimeDetector   → RegimeReport per ticker                │
  │   CorrelationAnalyst → CorrelationReport                    │
  └─────────────────────────────────────────────────────────────┘
          │  AnalysisBundle
          ▼
  ┌── Layer 5: Knowledge Agent ─────────────────────────────────┐
  │   Aggregator       → KnowledgeDigest                        │
  │   PatternFinder    → PatternReport                          │
  │   ConnectionTracer → ConnectionMap                          │
  └─────────────────────────────────────────────────────────────┘
          │  KnowledgeDigest + PatternReport + ConnectionMap
          ▼
  ┌── Layer 6: Chief Scientist ─────────────────────────────────┐
  │   Анализ KB + контекста → ResearchDirective                 │
  │   Решение: запустить / архивировать / приостановить         │
  └─────────────────────────────────────────────────────────────┘
          │  ResearchDirective
          ▼
  ┌── Layer 3: Research Agents ─────────────────────────────────┐
  │   FeatureProposer  → определить нехватающие признаки        │
  │   HypothesisSelector → выбрать конкретные гипотезы         │
  │   ExperimentPlanner → сформировать ExperimentPlan           │
  └─────────────────────────────────────────────────────────────┘
          │  ExperimentPlan
          ▼
  ┌── Layer 4: Validation Agent ────────────────────────────────┐
  │   (существующий Research Service)                           │
  │   ResearchRunner.run(ServiceConfig) → RunResult             │
  │   JsonKnowledgeStorage.store(entry)                         │
  └─────────────────────────────────────────────────────────────┘
          │  RunResult → knowledge_base.json
          │
          └──────────────────────────────────── LOOP ◄──────────
```

---

## Поток данных между агентами

```
ВНЕШНИЕ ИСТОЧНИКИ
      │
      ├── MOEX ISS ──────────────►  MarketAgent  ──► OhlcvDataset
      │                         └►  MacroAgent   ──► MacroSnapshot
      │                         └►  NewsAgent    ──► EventCalendar
      │                         └►  FundamentalsAgent → FundamentalSnapshot
      │                         └►  OrderFlowAgent → OrderFlowStats
      │
      │   OhlcvDataset + MacroSnapshot
      │        │
      │        └──────────────────►  CorrelationAgent → CorrelationMatrix
      │
      │
LAYER 1 OUTPUT
      │
      ├── OhlcvDataset ──────────►  TrendAnalyst      → TrendReport
      │                         └►  VolatilityAnalyst  → VolatilityReport
      │
      ├── OrderFlowStats ────────►  LiquidityAnalyst  → LiquidityReport
      │   + OhlcvDataset
      │
      ├── EventCalendar ─────────►  SentimentAnalyst  → SentimentReport
      │   + OrderFlowStats
      │
      ├── TrendReport ───────────►  RegimeDetector    → RegimeReport
      │   + VolatilityReport
      │
      └── CorrelationMatrix ─────►  CorrelationAnalyst → CorrelationReport
      │
      │
LAYER 2 OUTPUT (AnalysisBundle)
      │
      ├──────────────────────────►  Knowledge Agent
      │                              └── KnowledgeDigest
      │                              └── PatternReport
      │                              └── ConnectionMap
      │
      │                              Chief Scientist
      │                              └── ResearchDirective
      │
      └──────────────────────────►  FeatureProposer   → FeatureProposal
                                 └►  HypothesisSelector → SelectionResult
                                 └►  ExperimentPlanner → ExperimentPlan
                                        │
                                        ▼
                                  Research Service (Layer 4)
                                        │
                                        ▼
                                  knowledge_base.json
```

---

## Roadmap внедрения

### Этап 1 — Agent Infrastructure (Phase 5)

**Цель:** определить контракты агентов без реализации логики.

```
agents/
    __init__.py
    protocols.py     ← Protocol для каждого агента (DataAgent, AnalysisAgent, etc.)
    models.py        ← OhlcvDataset (уже есть в services/research/),
                       MacroSnapshot, EventCalendar, TrendReport, ...
```

**Что сделать:**
- Определить все `Protocol` интерфейсы агентов
- Определить все `dataclass` выходных моделей
- Написать тесты на протоколы (нет реализации — только интерфейс)
- Добавить ADR о структуре `agents/` layer

**Срок:** 1 цикл разработки. Ни один существующий файл не изменяется.

---

### Этап 2 — Data Layer (Phase 5 продолжение)

**Цель:** реализовать Data Agents поверх существующей MOEX ISS интеграции.

**Приоритет реализации:**
1. `MarketAgent` — оборачивает уже работающую MOEX ISS интеграцию
2. `MacroAgent` — USD/RUB и RGBI через MOEX ISS (данные уже доступны)
3. `NewsAgent` — дивидендный календарь MOEX ISS (`/dividends.json`)
4. `CorrelationAgent` — производный, строится на 1 и 2

**Что НЕ включается в Этап 2:**
- FundamentalsAgent (требует дополнительные источники)
- OrderFlowAgent (низкий приоритет для первых гипотез)
- Brent/ICE integration (внешний источник, требует отдельного решения)

---

### Этап 3 — Analysis Layer (Phase 6)

**Цель:** реализовать Analysis Agents поверх существующих Core индикаторов.

**Приоритет реализации:**
1. `RegimeDetector` — оборачивает `MarketRegimeEngine` + добавляет временнóй контекст
2. `TrendAnalyst` — ADX/SMA/RSI из `core/features/technical_indicators`
3. `VolatilityAnalyst` — ATR/BB из Core
4. `CorrelationAnalyst` — потребляет CorrelationMatrix

**Ключевой принцип:** Analysis Agents не пишут новые индикаторы.
Они используют `core/features/` и `core/regime/` через их публичные интерфейсы.

---

### Этап 4 — Knowledge Agent (Phase 6 продолжение)

**Цель:** автоматическая агрегация и интерпретация Knowledge Base.

**Реализация:**
1. `Aggregator` — читает `knowledge_base.json`, строит статистику
2. `PatternFinder` — детерминированные правила поиска паттернов
3. `ConnectionTracer` — граф связей из статического каталога гипотез

**Принцип:** Knowledge Agent на Этапе 4 — детерминированный, не ML.
Правила поиска паттернов фиксированы и понятны.

---

### Этап 5 — Research Agents (Phase 7)

**Цель:** автоматический выбор и планирование экспериментов.

**Реализация:**
1. `HypothesisSelector` — правила приоритизации на основе KnowledgeDigest + RegimeReport
2. `ExperimentPlanner` — перевод гипотезы в ServiceConfig с учётом уроков RP-002
3. `ValidationAgentAdapter` — тонкий wiring к Research Service

**Этот этап делает цикл полуавтономным:** Chief Scientist нужна только для
архивных решений и выбора направления, не для каждого запуска.

---

### Этап 6 — Chief Scientist v1 (Phase 7 продолжение)

**Цель:** правило-ориентированный Chief Scientist без ML.

**v1 логика (детерминированная):**
```python
if hypothesis.campaign_count >= 3 and hypothesis.avg_pass_rate < 0.10:
    archive(hypothesis, reason="structural_fail")
elif current_regime in hypothesis.favorable_regimes and hypothesis.features_available:
    prioritize(hypothesis)
elif connection_map.has_confirmed_predecessor(hypothesis):
    boost_priority(hypothesis)
```

**ML Chief Scientist** (v2) — Phase 8+, только после накопления ≥ 50 экспериментов
в Knowledge Base для обучения.

---

### Этап 7 — Full Autonomy Loop (Phase 8)

**Цель:** полный автономный цикл от сбора данных до архивации гипотез.

- Все 6 Data Agents реализованы
- Все 6 Analysis Agents реализованы
- Knowledge Agent + Chief Scientist v1 работают
- Validation Agent автоматически запускает Research Service
- Цикл запускается по расписанию или при обновлении данных
- Chief Scientist v2 — ML-based prioritization на накопленной KB

---

## Принципы архитектуры Intelligence Era

### 1. Платформа остаётся ядром

Все агенты вызывают существующий Core через его публичные интерфейсы.
Ни один агент не дублирует Core-логику. Core не изменяется под нужды агентов.

```
Агент → Protocol интерфейс → Core Module
                                   ↕
                              (без изменений)
```

### 2. Агенты — stateless трансформеры

Агент принимает входные данные, возвращает выходные данные. Не хранит состояния
между вызовами. Состояние хранится в файловой системе (датасеты, KB).

### 3. Детерминированность сохраняется

Все агенты детерминированы на одинаковых входных данных. Соответствует Принципу 2
из `00_AI_CONSTITUTION.md`. AI/ML компоненты (Chief Scientist v2) изолированы
и не влияют на Core или Validation.

### 4. Каждый агент тестируем изолированно

Protocol DI позволяет тестировать каждый агент с мок-данными.
Integration тесты используют реальные файлы из `data/datasets/`.

### 5. Постепенное внедрение

Каждый этап добавляет ценность самостоятельно. Полная автономия — не цель Этапа 1.
Система ценна уже на Этапе 3 (автоматический анализ рынка).

---

## Файловая структура Intelligence Era

```
MOEX_AI/
├── core/                    # БЕЗ ИЗМЕНЕНИЙ — Program Era foundation
├── services/
│   └── research/            # БЕЗ ИЗМЕНЕНИЙ — существующий Research Service
├── agents/                  # НОВЫЙ ВЕРХНИЙ УРОВЕНЬ
│   ├── __init__.py
│   ├── protocols.py         # Protocol interfaces for all agents
│   ├── models.py            # Shared domain models (MacroSnapshot, TrendReport, ...)
│   ├── data/                # Layer 1 implementations
│   │   ├── market.py        # MarketAgent
│   │   ├── macro.py         # MacroAgent
│   │   ├── news.py          # NewsAgent
│   │   ├── fundamentals.py  # FundamentalsAgent
│   │   ├── orderflow.py     # OrderFlowAgent
│   │   └── correlation.py   # CorrelationAgent
│   ├── analysis/            # Layer 2 implementations
│   │   ├── trend.py
│   │   ├── volatility.py
│   │   ├── liquidity.py
│   │   ├── sentiment.py
│   │   ├── regime.py
│   │   └── correlation.py
│   ├── research/            # Layer 3 implementations
│   │   ├── feature_proposer.py
│   │   ├── hypothesis_selector.py
│   │   └── experiment_planner.py
│   ├── validation/          # Layer 4 adapter
│   │   └── adapter.py       # ValidationAgentAdapter → Research Service
│   ├── knowledge/           # Layer 5 implementations
│   │   ├── aggregator.py
│   │   ├── pattern_finder.py
│   │   └── connection_tracer.py
│   └── chief_scientist/     # Layer 6
│       ├── v1_rule_based.py
│       └── v2_ml_based.py   # Phase 8+, не реализовывать раньше
├── data/                    # Хранилище данных (уже есть)
│   ├── datasets/            # OhlcvDatasets (уже заполнено)
│   ├── macro/               # MacroSnapshot per date (новое)
│   ├── events/              # EventCalendar per ticker (новое)
│   ├── fundamentals/        # FundamentalSnapshot per ticker (новое)
│   ├── orderflow/           # OrderFlowStats per ticker (новое)
│   └── correlations/        # CorrelationMatrix per date (новое)
├── campaigns/               # Campaign artifacts (уже есть)
├── research_programs/       # Research Program reports (уже есть)
└── tests/
    ├── agents/              # Unit тесты агентов (новое)
    │   ├── data/
    │   ├── analysis/
    │   ├── research/
    │   └── knowledge/
    └── ...                  # Существующие тесты — без изменений
```

---

## Граница между Program Era и Intelligence Era

| Аспект | Program Era | Intelligence Era |
|--------|-------------|-----------------|
| Запуск эксперимента | Вручную (`python -m services.research run`) | Автоматически (ExperimentPlanner → Validation Agent) |
| Выбор гипотезы | Инженером | HypothesisSelector (Chief Scientist директива) |
| Сбор данных | Вручную (MOEX ISS скрипт) | MarketAgent, MacroAgent |
| Анализ KB | Вручную (Campaign Report) | Knowledge Agent (автоматически) |
| Архивирование | Вручную | Chief Scientist (по критериям) |
| Core | Не изменяется | Не изменяется |
| Research Service | Не изменяется | Не изменяется |
| Knowledge Base | Не изменяется | Не изменяется |

**Ключевое свойство:** Intelligence Era не заменяет существующую платформу.
Она добавляет автономный контур управления исследовательским процессом поверх неё.

---

*Intelligence Architecture v1.0 — 2026-06-27*  
*Статус: DESIGN. Реализация начинается при старте Intelligence Era.*
