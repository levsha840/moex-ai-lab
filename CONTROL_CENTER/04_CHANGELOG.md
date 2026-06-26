# 04_CHANGELOG

MOEX AI LAB — актуальное состояние после релиза **v1.6.1 Persistence Layer**.

---

## Статус релизов

* ✅ v1.0 Foundation — завершен.
* ✅ v1.1 Intraday Data Layer — завершен.
* ✅ v1.2 Feature Factory — завершен.
* ✅ v1.3 Replay Engine — завершен.
* ✅ v1.4 Strategy Engine — завершен.
* ✅ v1.5 Paper Trading Engine — завершен.
* ✅ v1.6 Position Manager — завершен.
* 🚧 v1.6.1 Persistence Layer — в разработке (текущий релиз).

---

# v1.6 Position Manager

Добавлен промышлененный модуль управления позициями.

Реализовано:

* поддержка LONG и SHORT;
* открытие позиции;
* увеличение существующей позиции;
* частичное закрытие;
* полное закрытие;
* расчет средней цены;
* расчет realized PnL;
* расчет unrealized PnL;
* обновление рыночной цены;
* управление открытыми позициями;
* модульные тесты Position Manager.

---

# v1.6.1 Persistence Layer

Начато построение единого слоя хранения данных проекта.

Реализовано:

* выделен отдельный слой `core/persistence`;
* реализован интерфейс `PositionRepository`;
* реализована in-memory реализация `MemoryPositionRepository`;
* реализована фабрика `PersistenceFactory`;
* добавлены специализированные исключения Persistence Layer;
* подготовлен каркас PostgreSQL Repository;
* PositionManager переведен на dependency injection репозитория;
* сохранена обратная совместимость с текущей in-memory реализацией;
* добавлены модульные тесты Persistence Layer;
* добавлены интеграционные тесты PositionManager ↔ Persistence Layer.

---

# Архитектурное правило

Начиная с v1.6.1 бизнес-логика проекта не должна зависеть от конкретного способа хранения данных.

Все сервисы работают только через интерфейсы Persistence Layer.

Это позволяет использовать:

* in-memory backend;
* PostgreSQL backend;
* будущие реализации (Redis, ClickHouse и др.) без изменения бизнес-логики.

---

# Следующий релиз

## v1.7 Risk Engine

Планируется реализовать:

* риск на сделку;
* максимальный размер позиции;
* дневные лимиты риска;
* контроль максимальной просадки;
* stop-loss;
* take-profit;
* portfolio risk limits;
* интеграцию с PositionManager и Persistence Layer.

---

# Правило проекта

После завершения каждого релиза:

1. запускаются все тесты;
2. обновляется CONTROL_CENTER;
3. выполняется git commit;
4. выполняется git push;
5. проверяется состояние репозитория (`working tree clean`).

CONTROL_CENTER остается единственным источником актуального состояния проекта.
