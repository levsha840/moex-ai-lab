# 02_ROADMAP

MOEX AI LAB — актуальный roadmap после Architecture Refresh.

---

## Завершённые релизы

| Версия | Название | Статус |
|---|---|---|
| v1.0 | Foundation | ✅ завершён |
| v1.1 | Intraday Data Layer | ✅ завершён |
| v1.2 | Feature Factory | ✅ завершён |
| v1.3 | Replay Engine | ✅ завершён |
| v1.4 | Strategy Engine | ✅ завершён |
| v1.5 | Paper Trading Engine | ✅ завершён |
| v1.6 | Position Manager | ✅ завершён |
| v1.6.1 | Persistence Layer | ✅ завершён |
| v1.7 | Risk Engine | ✅ завершён |

---

## Следующие релизы

### v1.8 — Portfolio Allocation Engine

Минимальный аллокатор капитала между стратегиями.

Scope:
- `AllocationConfig`: max_position_pct, max_correlated_pct, rebalance_threshold
- Равновесное распределение как базовый режим
- Лимит на долю одной стратегии в портфеле
- Интеграция с RiskEngine

Не входит в scope: Kelly criterion, mean-variance оптимизация, динамическая ребалансировка.

---

### v1.9 — WalkForward Engine + Realistic Cost Model

**Единый релиз.** Разделение невозможно: walk-forward без честной модели издержек — это biased backtest.

WalkForward Engine:
- Скользящие окна: train / validation / OOS
- Критерии приёмки: Sharpe, max drawdown, число сделок
- Автоматическое отклонение стратегий, не прошедших OOS

Realistic Cost Model:
- Спред (ticker-specific, из исторических данных)
- T+2 settlement (заморозка денег)
- Налог 13% на прибыль
- Рыночное влияние для крупных позиций

---

### v2.0 — Data Quality Layer

Предварительное условие для всех исследовательских релизов.

Scope:
- Корректировка на дивиденды и сплиты
- Маркировка торговых приостановок (февраль 2022 и др.)
- Survivorship bias documentation
- Валидация входных данных перед запуском любого бэктеста

---

### v2.1 — Market Regime Engine

Определение текущего режима рынка перед запуском стратегий.

Режимы: Trend Up / Trend Down / Flat / High Volatility.

Scope:
- Классификация режима на дневном таймфрейме
- Фильтр режима в StrategyEngine
- Таблица `market_regimes_daily` (схема уже есть в infrastructure)

---

### v2.2 — MOEX Hypothesis Lab

Инструмент для формализации и проверки торговых гипотез.

Scope:
- Шаблон гипотезы: название, экономическое обоснование, параметры
- Автоматический прогон через WalkForward Engine
- Журнал результатов: прошла / не прошла / требует уточнения
- Первые гипотезы для проверки:
  - Дивидендный gap-fill
  - Momentum на отчётностях РСБУ
  - Пары: Роснефть/Лукойл, Сбер/ВТБ

---

### v2.3 — Strategy Candidate Pipeline

Автоматический конвейер: гипотеза → валидация → допуск к paper trading.

Scope:
- Формальные критерии перехода между этапами
- Реестр кандидатов со статусами (in-research / validated / paper / rejected)
- Отчёт по каждому кандидату

---

## Принцип приоритетов

```
Validation infrastructure (v1.9, v2.0) > Research tools (v2.1, v2.2) > New strategies
```

Новые торговые стратегии не добавляются до завершения v1.9 + v2.0.

Demo-стратегии (RSI/SMA) остаются в кодовой базе только как smoke-test инструмент.

---

## Правило

После завершения каждого релиза CONTROL_CENTER обновляется. Roadmap — живой документ, обновляется при изменении приоритетов.
