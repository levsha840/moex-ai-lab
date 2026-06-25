MOEX AI LAB v0.4 Core Platform

Распаковать архив в корень проекта:
D:\MOEX_AI

Проверка импортов:
cd D:\MOEX_AI
services\data_collector\.venv\Scripts\python.exe tests\test_core_imports.py

Запуск нового Replay через core:
cd D:\MOEX_AI
services\data_collector\.venv\Scripts\python.exe services\historical_replay\app\historical_replay_core.py

Обновление strategy_catalog:
cd D:\MOEX_AI
services\data_collector\.venv\Scripts\python.exe services\historical_replay\app\update_strategy_catalog_core.py

Проверка каталога:
docker exec -it moex_postgres psql -U moex -d moex_ai -c "
SELECT
    id,
    strategy_name,
    ticker,
    status,
    replay_trades,
    ROUND(replay_profit_factor::numeric, 2) AS pf,
    ROUND(replay_expectancy::numeric, 2) AS expectancy,
    ROUND(replay_total_pnl::numeric, 2) AS total_pnl
FROM strategy_catalog
ORDER BY replay_total_pnl DESC;
"
