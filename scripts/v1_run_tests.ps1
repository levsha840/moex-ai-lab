cd D:\MOEX_AI
$env:PYTHONPATH="D:\MOEX_AI"
services\data_collector\.venv\Scripts\python.exe tests\test_platform_imports.py
services\data_collector\.venv\Scripts\python.exe tests\test_core_portfolio_risk.py
services\data_collector\.venv\Scripts\python.exe tests\test_strategy_registry.py
services\data_collector\.venv\Scripts\python.exe tests\test_broker_safety.py
