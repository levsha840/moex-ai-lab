# Next Steps

## Завершено в этом пакете

- Core DB.
- Strategy Registry.
- Strategy Catalog integration.
- Replay Execution Engine.
- Portfolio.
- Risk Manager.
- Historical Replay через core.
- Обновление strategy_catalog результатами Replay.

## Следующий этап

### v0.7 — Intraday Paper Core

Нужно добавить:

- таблицы intraday candles;
- сбор минутных свечей;
- intraday feature factory;
- intraday replay;
- paper live loop;
- scheduler;
- event loop;
- журнал сигналов.

### v0.8 — T-Invest Sandbox

Нужно добавить:

- sandbox broker adapter;
- загрузку токена из `.env`;
- sandbox account manager;
- order manager;
- execution quality monitor;
- сравнение ожидаемой и фактической цены.
