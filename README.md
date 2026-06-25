# MOEX AI LAB Platform v1.0

Полный рабочий каркас платформы текущего этапа.

## Состав

- core/db — PostgreSQL
- core/config — настройки
- core/strategy — стратегии, registry, catalog, lifecycle
- core/market — загрузка market/features/regimes
- core/execution — execution engine
- core/portfolio — portfolio/positions
- core/risk — risk manager
- core/broker — replay/paper/sandbox/live adapters
- core/analytics — metrics/reports
- core/experiment — experiments
- services/historical_replay — рабочий Replay
- services/strategy_lifecycle — обновление catalog/status/meta
- services/paper_intraday — безопасный каркас intraday
- services/sandbox_trading — безопасный sandbox smoke
- services/ai_strategy_generator — безопасный каркас generator
- migrations — SQL
- scripts — PowerShell
- tests — smoke tests
- docs — документация

## Установка

Распаковать в:

```text
D:\MOEX_AI
```

Запустить:

```powershell
cd D:\MOEX_AI
$env:PYTHONPATH="D:\MOEX_AI"
.\scripts\v1_full_smoke.ps1
```

Live trading заблокирован по умолчанию.
