# Project Status

## Уже работает

- PostgreSQL + TimescaleDB.
- Дневные свечи MOEX.
- Feature Factory.
- Market Regime.
- Strategy Factory.
- WalkForward.
- Historical Replay.
- Replay Analytics.
- Paper Trading Core.
- Position Manager.
- Strategy Catalog.
- Core Platform v0.6.

## Последние подтвержденные результаты

До исключения слабой связки:

```text
55 trades
Final cash: 1 086 506.49
```

После перевода `RSI_OVERSOLD_NOT_DOWNTREND / OZON` в watchlist:

```text
50 trades
Final cash: 1 099 307.86
```

Вывод: lifecycle-фильтр улучшил результат.
