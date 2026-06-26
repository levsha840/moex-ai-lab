# 02_ROADMAP — MOEX AI LAB

## Завершено

- v1.0 Foundation.
- v1.1 Intraday Data Layer.
- v1.2 Feature Factory.
- v1.3 Replay Engine.

## Далее

### v1.4 Strategy Runtime Layer

Цель: подключить стратегии к replay-потоку и получать сигналы на каждой свече.

План:

1. Единый интерфейс стратегии.
2. Runtime-контекст стратегии.
3. Подключение `ReplayEngine` + `FeatureFactory` + strategy callback.
4. Журнал событий стратегии.
5. Unit-тесты.

### v1.5 Backtest Metrics Layer

Цель: считать сделки, equity curve, drawdown, win-rate, profit factor.

### v1.6 Paper Trading Integration

Цель: связать сигналы стратегии с paper execution.

### v1.7 AI Learning Dataset

Цель: подготовить датасет для обучения моделей.
