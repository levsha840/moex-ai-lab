# Runbook

```powershell
cd D:\MOEX_AI
$env:PYTHONPATH="D:\MOEX_AI"

.\scripts\v1_run_tests.ps1
.\scripts\v1_run_replay.ps1
.\scripts\v1_run_analytics.ps1
.\scripts\v1_update_catalog.ps1
```

Проверка каталога:

```powershell
docker exec -it moex_postgres psql -U moex -d moex_ai -c "
SELECT id, strategy_name, ticker, status, replay_trades,
ROUND(replay_profit_factor::numeric, 2) AS pf,
ROUND(replay_expectancy::numeric, 2) AS expectancy,
ROUND(replay_total_pnl::numeric, 2) AS total_pnl
FROM strategy_catalog
ORDER BY status, replay_total_pnl DESC;"
```
