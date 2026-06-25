# SQL Checks

## Размер основных таблиц

```sql
SELECT 'candles' tbl, COUNT(*) cnt FROM candles
UNION ALL
SELECT 'features_daily', COUNT(*) FROM features_daily
UNION ALL
SELECT 'market_regimes_daily', COUNT(*) FROM market_regimes_daily
UNION ALL
SELECT 'strategy_results', COUNT(*) FROM strategy_results
UNION ALL
SELECT 'strategy_validation_results', COUNT(*) FROM strategy_validation_results
UNION ALL
SELECT 'paper_positions', COUNT(*) FROM paper_positions
UNION ALL
SELECT 'paper_trades', COUNT(*) FROM paper_trades
UNION ALL
SELECT 'paper_portfolio', COUNT(*) FROM paper_portfolio
UNION ALL
SELECT 'strategy_catalog', COUNT(*) FROM strategy_catalog;
```

## Активные стратегии

```sql
SELECT id, strategy_name, ticker, status,
       replay_trades,
       ROUND(replay_profit_factor::numeric, 2) AS pf,
       ROUND(replay_expectancy::numeric, 2) AS expectancy,
       ROUND(replay_total_pnl::numeric, 2) AS total_pnl
FROM strategy_catalog
ORDER BY status, replay_total_pnl DESC;
```

## Сделки после Replay

```sql
SELECT side, COUNT(*)
FROM paper_trades
GROUP BY side;
```

## Позиции после Replay

```sql
SELECT status, COUNT(*)
FROM paper_positions
GROUP BY status;
```

## Equity curve

```sql
SELECT
    MIN(time) AS start_date,
    MAX(time) AS end_date,
    MIN(equity) AS min_equity,
    MAX(equity) AS max_equity,
    COUNT(*) AS days
FROM paper_portfolio;
```
