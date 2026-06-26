# 02_ROADMAP

MOEX AI LAB — актуальное состояние после релиза v1.4 Strategy Engine.

## Статус релизов

- v1.0 Foundation — завершен.
- v1.1 Intraday Data Layer — завершен.
- v1.2 Feature Factory — завершен.
- v1.3 Replay Engine — завершен.
- v1.4 Strategy Engine — завершен в этом патче.

## v1.4 Strategy Engine

Добавлен новый слой торгового ядра:

- единая модель сигналов BUY / SELL / HOLD;
- StrategyContext для передачи candle/history/features в стратегии;
- BaseStrategy для новых стратегий;
- StrategyEngine для запуска стратегий поверх ReplayEngine;
- EngineStrategyRegistry для регистрации стратегий;
- адаптер для старых стратегий, использующих generate_signal(row);
- тесты Strategy Engine.

## Следующий релиз

v1.5 Paper Trading Engine:

- исполнение сигналов;
- виртуальные заявки;
- сделки;
- комиссия;
- проскальзывание;
- журнал операций;
- подготовка к Portfolio/Risk Manager.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
