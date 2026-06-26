# 11_NEXT_TASKS

MOEX AI LAB — ближайшие инженерные задачи после Architecture Refresh.

## Текущее состояние

В `main` добавлены:

- `CONTROL_CENTER/05_SYSTEM_VISION.md`;
- `CONTROL_CENTER/10_ARCHITECTURE_DECISIONS.md`;
- обновлён `CONTROL_CENTER/02_ROADMAP.md`.

Код проекта не изменялся.

## Следующая задача Claude Code

### TASK: Finish Architecture Refresh

1. Прочитать все документы CONTROL_CENTER.
2. Синхронизировать формулировки в:
   - `01_PROJECT_STATE.md`;
   - `03_ARCHITECTURE.md`;
   - `04_CHANGELOG.md`.
3. Не менять runtime-код проекта.
4. Убедиться, что `02_ROADMAP.md`, `05_SYSTEM_VISION.md` и `10_ARCHITECTURE_DECISIONS.md` согласованы между собой.
5. Запустить тесты, если окружение позволяет.
6. Сделать commit:
   - `Finish Architecture Refresh`.

## Следующий релиз после refresh

### v1.8 Minimal Portfolio Allocation Engine

Цель: добавить минимальный deterministic allocation layer перед RiskEngine.

Scope:

- `core/allocation/`;
- `AllocationConfig` / `AllocationLimits`;
- `AllocationRequest`;
- `AllocationDecision`;
- `AllocationDecisionType`: `ALLOCATE`, `REDUCE`, `REJECT`;
- базовые лимиты:
  - `max_position_pct`;
  - `max_strategy_pct`;
  - `max_correlated_pct`;
  - `cash_buffer`;
  - `rebalance_threshold`;
- unit tests.

Out of scope:

- Kelly criterion;
- Markowitz / mean-variance;
- Black-Litterman;
- AI allocation;
- broker integration;
- database access;
- dynamic complex rebalancing.

Architecture rule:

`PortfolioAllocationEngine` must be deterministic. It must not execute trades, write repositories, call RiskEngine, or access database/network/filesystem.
