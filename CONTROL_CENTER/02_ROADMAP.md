# 02_ROADMAP

MOEX AI LAB — актуальное состояние после релиза v1.7 Risk Engine.

## Статус релизов

- v1.0 Foundation — завершен.
- v1.1 Intraday Data Layer — завершен.
- v1.2 Feature Factory — завершен.
- v1.3 Replay Engine — завершен.
- v1.4 Strategy Engine — завершен.
- v1.5 Paper Trading Engine — завершен.
- v1.6 Position Manager — завершен.
- v1.6.1 Persistence Layer — завершен.
- v1.7 Risk Engine — завершен.
- v1.8 — в плане.

## Завершённые релизы

- v1.0–v1.2: фундамент, данные, фичи.
- v1.3: ReplayEngine — детерминированный посвечный replayer.
- v1.4: StrategyEngine — конвейер BUY/SELL/HOLD сигналов.
- v1.5: PaperTradingEngine — виртуальное исполнение заявок.
- v1.6: PositionManager — управление LONG/SHORT позициями.
- v1.6.1: Persistence Layer — Protocol-based абстракция хранения, MemoryRepository.
- v1.7: RiskEngine — pre-trade оценка риска, интеграция с PaperTradingEngine.

## Следующий релиз

v1.8 (планируется):

- PostgreSQL backend для PositionRepository;
- дневные лимиты риска;
- stop-loss и take-profit;
- end-to-end интеграционный тест: ReplayEngine → StrategyEngine → RiskEngine → PaperTradingEngine.

## Правило

После завершения каждого релиза документы CONTROL_CENTER должны быть обновлены и оставаться единственным источником актуального состояния проекта.
