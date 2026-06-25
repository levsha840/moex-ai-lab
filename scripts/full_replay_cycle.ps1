cd D:\MOEX_AI
$env:PYTHONPATH="D:\MOEX_AI"

services\data_collector\.venv\Scripts\python.exe tests\test_core_imports.py
services\data_collector\.venv\Scripts\python.exe tests\test_core_portfolio_risk.py
services\data_collector\.venv\Scripts\python.exe services\historical_replay\app\historical_replay_core_risk.py
services\data_collector\.venv\Scripts\python.exe services\historical_replay\app\replay_analytics_core.py
services\data_collector\.venv\Scripts\python.exe services\historical_replay\app\update_strategy_catalog_core.py
