# Architecture

Основной поток:

```text
strategy_catalog
  -> StrategyRegistry
  -> MarketDataRepository
  -> ReplayExecutionEngine
  -> Portfolio + RiskManager
  -> paper_positions / paper_trades / paper_portfolio
  -> ReplayAnalytics
  -> Catalog update
  -> Meta scoring
```

Принцип: сервисы — оркестраторы, повторяемая логика — только в `core`.
