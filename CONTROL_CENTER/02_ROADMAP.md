# 02_ROADMAP

MOEX AI LAB — актуальное состояние после релиза v1.5 Paper Trading Engine.

## Статус релизов

- v1.0 Foundation — завершен.
- v1.1 Intraday Data Layer — завершен.
- v1.2 Feature Factory — завершен.
- v1.3 Replay Engine — завершен.
- v1.4 Strategy Engine — завершен.
- v1.5 Paper Trading Engine — завершен в этом патче.

## v1.5 Paper Trading Engine

Добавлен промышленный long-only paper execution layer:

- доменные модели виртуальных заявок, сделок, позиций, отклоненных заявок и портфельных snapshot;
- PaperTradingEngine для исполнения BUY / SELL / HOLD сигналов Strategy Engine;
- учет initial cash, комиссии, минимальной комиссии и проскальзывания;
- проверка достаточности денежных средств;
- запрет short-продаж по умолчанию;
- журнал виртуальных заявок, сделок, отклонений и portfolio snapshots;
- расчет realized / unrealized PnL, equity и market value;
- тесты Paper Trading Engine.

## Архитектурное правило

Paper Trading Engine не пишет напрямую в PostgreSQL. Он является чистым детерминированным execution-layer. Persistency/Repository слой будет добавлен отдельным релизом, чтобы не смешивать доменную логику исполнения и хранение данных.

## Следующий релиз

v1.6 Portfolio / Risk Manager Integration:

- связать PaperTradingEngine с Risk Manager;
- добавить лимиты на размер позиции и риск на сделку;
- добавить portfolio-level ограничения;
- подготовить persistence adapter для paper trading журналов;
- расширить end-to-end replay → strategy → paper execution сценарий.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
