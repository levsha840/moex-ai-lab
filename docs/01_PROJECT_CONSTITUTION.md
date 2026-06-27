# 01_PROJECT_CONSTITUTION — MOEX AI LAB

> Инженерный устав проекта. Описывает структуру модулей, допустимые зависимости
> и правила расширения платформы.

---

## Core Modules

### Production Core

Детерминированный контур исполнения торговых решений.

| Модуль | Путь | Назначение |
|--------|------|------------|
| FeatureFactory | `core/features/` | Вычисление признаков из свечей |
| ReplayEngine | `core/replay/` | Воспроизведение исторических данных |
| StrategyEngine | `core/strategy/` | Генерация торговых сигналов |
| PortfolioAllocationEngine | `core/allocation/` | Распределение капитала |
| RiskEngine | `core/risk/` | Pre-trade проверка лимитов |
| PaperTradingEngine | `core/paper/` | Симуляция исполнения ордеров |
| PositionManager | `core/position/` | Учёт позиций |
| Persistence Layer | `core/persistence/` | Абстракция хранения (PositionRepository) |

### Validation Core

Обязательный шлюз перед допуском стратегии в Production.

| Модуль | Путь | Назначение |
|--------|------|------------|
| ExecutionCostEngine | `core/costs/` | Расчёт издержек исполнения |
| WalkForwardWindowGenerator | `core/walkforward/` | Генерация rolling-окон |
| WalkForwardEngine | `core/walkforward/` | Запуск runner по окнам |
| ValidationReportBuilder | `core/validation/` | Сборка PASS/FAIL отчёта |

### Research Core

Контур исследования гипотез. Не имеет прямого доступа к Production Core.

| Модуль | Путь | Назначение | Версия |
|--------|------|------------|--------|
| MarketRegimeEngine | `core/regime/` | Классификация рыночного режима | v2.1 |
| HypothesisRegistry | `core/hypothesis/` | Lifecycle управление гипотезами | v2.3 |
| KnowledgeBase | `core/knowledge/` | Накопление результатов исследований | v2.4 |
| ExperimentRunner | `core/experiment/` | Оркестрация experiment pipeline | v2.2 |
| ResearchPipeline | `core/research_pipeline/` | Связка Experiment → KnowledgeBase | v3.1 |
| Hypothesis Generator Module | `core/hypothesis_generator/` | Генерация и knowledge-guided ранжирование кандидатов | v3.3+ |
| Research Orchestrator | `core/research_orchestrator/` | Sequence executor для плана задач | v4.1 |
| Research Session | `core/research_session/` | Coordination facade: generate → plan → execute → aggregate | v4.3 |

### Experiments

Конкретные исследовательские эксперименты. Живут за пределами Core.

| Путь | Назначение |
|------|------------|
| `experiments/h13_adx_continuation/` | H-13: ADX Trend Continuation |

---

## Карта допустимых зависимостей

```
experiments/
    └─► core/research_pipeline/
    └─► core/hypothesis_generator/
    └─► core/hypothesis/
    └─► core/knowledge/
    └─► core/experiment/
    └─► core/costs/
    └─► core/walkforward/
    └─► core/validation/
    └─► core/regime/
    └─► core/features/

core/research_session/
    └─► core/research_orchestrator/  (ResearchPlan, ResearchTask, PlanExecutor Protocol)
    └─► core/hypothesis_generator/   (HypothesisGenerator)
    └─► core/hypothesis/             (HypothesisRegistry)
    └─► core/research_pipeline/      (ResearchPipeline — concrete)

core/research_orchestrator/
    └─► core/hypothesis/             (HypothesisRegistry)
    └─► core/research_pipeline/      (ResearchPipeline)

core/research_pipeline/
    └─► core/experiment/
    └─► core/hypothesis/
    └─► core/knowledge/

core/hypothesis_generator/
    └─► core/hypothesis/             (engine.py, accept())
    └─► core/knowledge/              (statistics.py only — KBTemplateStatisticsProvider)

core/experiment/
    └─► (только собственные models, никаких Research/Production зависимостей)

core/regime/
    └─► (независим)

core/validation/
    └─► core/walkforward/

core/walkforward/
    └─► (независим)

core/costs/
    └─► core/common/

core/features/
    └─► (независим, stdlib only)

Production Core (strategy, allocation, risk, paper, position, persistence)
    └─► core/common/
    └─► core/persistence/ (через Protocol)
```

**Запрещено:**

- `core/` → `experiments/` (любой модуль ядра не импортирует из experiments)
- Research Core → Production Core (прямой доступ)
- Production Core → Research Core (прямой доступ)
- Любые циклические зависимости

---

## Правила создания нового Core Module

Новый модуль в `core/` требует:

1. **Обоснования:** почему нельзя расширить существующий модуль.
2. **Архитектурного ревью:** показать место в dependency graph, Protocol-интерфейсы,
   доменные модели.
3. **ADR-записи** в `30_ARCHITECTURE_DECISION_LOG.md`.
4. **stdlib only:** никаких новых внешних зависимостей без явного обоснования.
5. **Минимум 10 тестов** перед merge.
6. **Термин "Engine"** применяется только к модулям с нетривиальной вычислительной
   логикой. Для простых оркестраторов, репозиториев и сервисов — другие термины.

---

## Требования к тестируемости

- **Каждый Core Module** покрывается юнит-тестами без моков базы данных
  (in-memory реализация является стандартной).
- **Каждый Protocol** должен иметь хотя бы одну конкретную реализацию с тестами.
- **Детерминизм** фиксируется тестами: `result_a == result_b` при идентичных входах.
- **Deepcopy изоляция** проверяется там, где Repository возвращает объекты
  (мутация снаружи не должна менять хранилище).
- **Порог:** 100% прохождение перед каждым commit в main.

---

## Правила расширения платформы

### Добавление нового Core Module

Следовать правилам из раздела выше. Минимальный состав пакета:

```
core/<module_name>/
    __init__.py      (публичный API)
    models.py        (доменные модели)
    protocols.py     (Protocol-интерфейсы, если нужны)
    engine.py / service.py / repository.py  (реализация)
```

### Добавление нового эксперимента

Создать `experiments/<name>/` с:

```
__init__.py
dataset.py        (доменный объект данных эксперимента)
providers.py      (FeatureProvider, RegimeAdapter, StrategyRunner)
experiment.py     (точка входа: run_<name>_experiment())
template.py       (HypothesisTemplate для данного эксперимента)
```

Эксперимент импортирует из `core/`, никогда наоборот.

### Добавление новой стратегии

Новые стратегии **не добавляются** в Production Core без полного цикла:

```
HypothesisRegistry (IDEA → RESEARCH)
    ↓
ResearchPipeline (ExperimentRunner + KnowledgeBase)
    ↓
ValidationReport (PASS)
    ↓
Production Core
```

Демонстрационные стратегии (RSI/SMA) остаются как smoke-test. Они не являются
кандидатами для production.

### Изменение существующего Core Module

- Backward-compatible изменения допускаются без ADR.
- Breaking changes требуют ADR и обновления тестов всех затронутых модулей.
- Изменение `00_AI_CONSTITUTION.md` или `01_PROJECT_CONSTITUTION.md` требует
  явного подтверждения.
