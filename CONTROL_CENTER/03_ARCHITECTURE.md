# 03_ARCHITECTURE

MOEX AI LAB — архитектура платформы после Architecture Refresh.

## Статус релизов

- v1.0 Foundation — завершен.
- v1.1 Intraday Data Layer — завершен.
- v1.2 Feature Factory — завершен.
- v1.3 Replay Engine — завершен.
- v1.4 Strategy Engine — завершен.
- v1.5 Paper Trading Engine — завершен.
- v1.6 Position Manager — завершен.
- v1.6.1 Persistence Layer — завершен.
- v1.7 Risk Engine — завершен.
- Architecture Refresh — завершен.

## Четыре контура платформы

```
┌─────────────────────────────────────────────────────────────────┐
│  RESEARCH CORE                                                  │
│  Hypothesis Registry → Feature Engineering → Strategy Discovery │
│  (нет прямого доступа к Production)                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ стратегия-кандидат
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  VALIDATION CORE  (обязательный шлюз)                           │
│  Backtest → Cost Model → WalkForward → OOS Metrics → PASS/FAIL  │
│  Стратегия не допускается в Production без прохождения шлюза.   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ PASS
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION CORE                                                │
│                                                                 │
│  [MOEX / T-Invest API]                                          │
│          │                                                      │
│          ▼                                                      │
│  [data_collector] ──► PostgreSQL (candles_intraday, candles)    │
│                                 │                               │
│                                 ▼                               │
│                       [FeatureFactory] ──► features_daily       │
│                                 │                               │
│                                 ▼                               │
│                       [ReplayEngine]  ← replay из БД/in-memory  │
│                                 │                               │
│                                 ▼                               │
│                       [StrategyEngine] ← стратегии (BaseStrategy)│
│                                 │  Signal: BUY / SELL / HOLD   │
│                                 ▼                               │
│                  [PortfolioAllocationEngine]  ← v1.8            │
│                                 │  ALLOCATE / REDUCE / REJECT  │
│                                 ▼                               │
│                       [RiskEngine]  ← pre-trade лимиты          │
│                                 │  ALLOW / REJECT              │
│                                 ▼                               │
│                     [PaperTradingEngine]  ← execution layer     │
│                                 │                               │
│                       [Persistence Layer]                       │
│                      ├─ MemoryPositionRepository ✓              │
│                      └─ PostgresPositionRepository (заглушка)   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  OPERATIONS CORE                                                │
│  Strategy Supervisor → Drawdown Control → Degradation Detection │
│  → Disable / Archive → Audit Trail                              │
└─────────────────────────────────────────────────────────────────┘
```

## Основной pipeline Production Core

```
Strategy
    ↓
Portfolio Allocation   ← v1.8
    ↓
Risk
    ↓
Execution
```

## Архитектурные правила

- `ReplayEngine`, `StrategyEngine`, `PortfolioAllocationEngine`, `RiskEngine`, `PaperTradingEngine` — детерминированные объекты без доступа к БД.
- Бизнес-логика не зависит от способа хранения данных: все сервисы работают через интерфейсы `Persistence Layer`.
- `RiskEngine` подключается к `PaperTradingEngine` опционально — при отсутствии поведение не меняется.
- Research Core не имеет прямого доступа к Production Core.
- Validation Core — обязательный шлюз: стратегия без PASS не допускается в Production.

## Нерешённые архитектурные вопросы

- `PaperTradingEngine` ведёт собственный учёт позиций (`PaperPosition`) независимо от `PositionManager` — связь не определена (ADR-0012, Open).
- `core/portfolio/` (старый слой) существует параллельно с `core/position/` — судьба не определена.
- `PostgresPositionRepository` — заглушка, реализация не начата.

## Следующий релиз

v1.8 — Minimal Portfolio Allocation Engine: добавление детерминированного allocation layer между StrategyEngine и RiskEngine.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
