cd D:\MOEX_AI
$env:PYTHONPATH="D:\MOEX_AI"

services\data_collector\.venv\Scripts\python.exe tests\test_core_imports.py
services\data_collector\.venv\Scripts\python.exe tests\test_core_portfolio_risk.py
