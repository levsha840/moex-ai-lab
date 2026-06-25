cd D:\MOEX_AI
$env:PYTHONPATH="D:\MOEX_AI"
services\data_collector\.venv\Scripts\python.exe tests\test_platform_imports.py
services\data_collector\.venv\Scripts\python.exe tests\test_core_portfolio_risk.py
services\data_collector\.venv\Scripts\python.exe tests\test_strategy_registry.py
services\data_collector\.venv\Scripts\python.exe tests\test_broker_safety.py
services\data_collector\.venv\Scripts\python.exe services\historical_replay\app\run_replay.py
services\data_collector\.venv\Scripts\python.exe services\historical_replay\app\run_analytics.py
services\data_collector\.venv\Scripts\python.exe services\strategy_lifecycle\app\update_catalog_from_replay.py
services\data_collector\.venv\Scripts\python.exe services\strategy_lifecycle\app\meta_score.py
