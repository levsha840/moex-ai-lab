# M12.5 — Broker Sandbox Integration (T-Invest Sandbox)

**Date:** 2026-06-29  
**Sprint:** M12.5  
**Status:** COMPLETE — 2899/2899 tests pass

---

## 1. Архитектурная схема

```
┌──────────────────────────────────────────────────────────┐
│                  Runtime Layer (M12)                      │
│  RuntimeOrchestrator → AutonomousPipeline → EventBus     │
└────────────────────────────┬─────────────────────────────┘
                             │  BrokerInterface (ABC)
                             │  (Runtime знает только об интерфейсе)
                             ▼
┌──────────────────────────────────────────────────────────┐
│               services/broker/  (M12.5)                  │
│                                                           │
│  BrokerInterface (ABC)                                    │
│    ↑ implements                                           │
│  ┌────────────────┐   ┌──────────────────────────┐       │
│  │  MockBroker    │   │  TInvestSandboxAdapter    │       │
│  │  (in-memory)   │   │  (t_tech.invest gRPC)     │       │
│  └────────────────┘   └──────────────────────────┘       │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │  RiskGuard  │  │ TradeJournal │  │  BrokerHealth │   │
│  │  (7 checks) │  │ (JSONL log)  │  │  (conn/lat.)  │   │
│  └─────────────┘  └──────────────┘  └───────────────┘   │
│                                                           │
│  broker_events.py  — LabEvent subclasses for broker       │
└──────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│           T-Invest Sandbox API (external)                 │
│   sandbox-invest.tinkoff.ru:443 (gRPC)                   │
│   SDK: t_tech_investments 1.49.2                         │
│   Status: SDK installed, gRPC requires Python ≤3.12      │
│           (pre-built wheel not available for 3.14.5)     │
└──────────────────────────────────────────────────────────┘
```

**Ключевой принцип:** Runtime работает только через `BrokerInterface`. Замена T-Invest на QUIK/MOEX FIX/IBKR — одна строка кода.

---

## 2. Список файлов

### Новые файлы

| Файл | Назначение |
|---|---|
| `services/broker/__init__.py` | Пакет, публичный API |
| `services/broker/broker_interface.py` | ABC `BrokerInterface` — 11 методов |
| `services/broker/broker_models.py` | `Order`, `OrderRequest`, `Position`, `Balance`, `BrokerAccount`, enums, exceptions |
| `services/broker/broker_events.py` | `OrderPlaced`, `OrderFilled`, `OrderCancelled`, `OrderRejected`, `BrokerConnected`, `BrokerDisconnected`, `BrokerHealthChecked` |
| `services/broker/broker_risk_guard.py` | `RiskGuard` — 7 проверок последовательно |
| `services/broker/trade_journal.py` | `TradeJournal` — append-only JSONL, thread-safe |
| `services/broker/broker_health.py` | `BrokerHealth` — connection + latency check |
| `services/broker/adapters/__init__.py` | Адаптеры |
| `services/broker/adapters/mock_broker.py` | `MockBroker` — in-memory, no SDK |
| `services/broker/adapters/tinvest_sandbox.py` | `TInvestSandboxAdapter` — t_tech.invest gRPC |
| `scripts/run_broker_sandbox.py` | CLI (health/account/positions/balance/journal/place/cancel) |
| `tests/broker/__init__.py` | |
| `tests/broker/test_broker_models.py` | 10 тестов |
| `tests/broker/test_mock_broker.py` | 20 тестов |
| `tests/broker/test_risk_guard.py` | 16 тестов |
| `tests/broker/test_trade_journal.py` | 12 тестов |
| `tests/broker/test_broker_health.py` | 8 тестов |
| `tests/broker/test_broker_integration.py` | 14 тестов (e2e с MockBroker) |

### Файлы без изменений
- `services/runtime/` — не тронут
- `services/event_pipeline/` — не тронут
- `services/research/` — не тронут
- `runtime/status.json` — не тронут

---

## 3. BrokerInterface — контракт

```python
class BrokerInterface(ABC):
    def connect(self) -> bool           # открыть соединение
    def disconnect(self) -> None        # закрыть
    def is_connected: bool              # property
    def is_sandbox: bool                # MUST = True для non-live
    def broker_name: str                # human name
    def health(self) -> dict            # connected/latency/sandbox_mode/overall
    def get_account(self) -> BrokerAccount
    def get_positions(self) -> list[Position]
    def get_balance(self) -> list[Balance]
    def place_order(self, request: OrderRequest) -> Order
    def cancel_order(self, order_id: str) -> bool
    def get_order(self, order_id: str) -> Order | None
    def get_orders(self) -> list[Order]
    def get_trades(self) -> list[Order]   # only FILLED
```

---

## 4. RiskGuard — порядок проверок

```
1. kill_switch        → если ON: все заявки отклонены безусловно
2. sandbox_only       → production брокер заблокирован при sandbox_only=True
3. quantity > 0       → защита от нулевых/отрицательных заявок
4. max_position_size  → max 10 лотов на заявку (настраивается)
5. max_open_positions → max 5 открытых позиций (настраивается)
6. daily_limit        → max 20 заявок в день (настраивается)
7. instrument_whitelist → если задан список — только из него
```

Каждая проверка возвращает `RiskCheckResult(allowed, rule, reason)`.

---

## 5. TInvestSandboxAdapter — SDK-статус

| Компонент | Статус |
|---|---|
| `t_tech_investments` 1.49.2 | Установлен в `.venv` |
| `grpcio` 1.81.1 | Установлен, НО `cygrpc` не скомпилирован для Python 3.14.5 |
| Адаптер | Импортируется без SDK. `connect()` поднимает `BrokerUnavailableError` с actionable-сообщением |
| Для реального sandbox | Требует Python ≤3.12 или `grpcio` собранный из исходников |

**Сообщение при отсутствии SDK:**
```
BrokerUnavailableError: t_tech.invest SDK unavailable: cannot import name 'cygrpc'...
Fix: install grpcio from source for Python 3.14, or use Python ≤3.12.
```

---

## 6. TradeJournal — формат записей

```jsonl
{"ts":"2026-06-29T20:00:00+00:00","event":"ORDER_PLACED","order_id":"MOCK-A1B2C3D4",
 "strategy_id":"BB_SQUEEZE","cycle_id":"cycle_0001","reason":"","data":{...}}
{"ts":"2026-06-29T20:00:01+00:00","event":"ORDER_UPDATED","order_id":"MOCK-A1B2C3D4",
 "data":{"status":"CANCELLED","broker_response":{},...}}
{"ts":"2026-06-29T20:00:02+00:00","event":"ORDER_REJECTED","order_id":"none",
 "strategy_id":"BB_SQUEEZE","data":{"rule":"kill_switch","reason":"Kill switch ON"}}
```

Файл: `runtime/trade_journal.jsonl`

---

## 7. CLI — команды

```bash
python scripts/run_broker_sandbox.py --mock --health       # offline test
python scripts/run_broker_sandbox.py --mock --account
python scripts/run_broker_sandbox.py --mock --positions
python scripts/run_broker_sandbox.py --mock --balance
python scripts/run_broker_sandbox.py --mock --journal --tail 20
python scripts/run_broker_sandbox.py --mock --place-test-order SBER 5 258.0
python scripts/run_broker_sandbox.py --mock --cancel-all

# С реальным токеном (когда gRPC будет доступен):
T_INVEST_TOKEN=<token> python scripts/run_broker_sandbox.py --health
```

---

## 8. Тесты

| Файл | Тестов | Покрытие |
|---|---|---|
| `test_broker_models.py` | 10 | Enums, dataclasses, exceptions, to_dict |
| `test_mock_broker.py` | 20 | Lifecycle, account, orders, cancel, health, positions |
| `test_risk_guard.py` | 16 | Все 7 проверок, reset, record_order |
| `test_trade_journal.py` | 12 | Write, read, tail, daily_count, persistence |
| `test_broker_health.py` | 8 | OK/DEGRADED/OFFLINE, latency, to_dict |
| `test_broker_integration.py` | 14 | E2E: broker+guard+journal+health с MockBroker |
| **Итого** | **80** | |

---

## 9. Итоговый pytest

```
2899 passed, 42 warnings
  M12 Sprint 1 (integration):   120 tests
  M12 Sprint 2 (runtime):        69 tests
  M12 Patch 2.1 (evolution):     restored 2
  M12.5 (broker):                80 tests
  Прочие:                      2630 tests
─────────────────────────────────────
Total: 2899 / 2899 passed  ✓
```

---

## 10. Готовность к первому автономному тесту в песочнице

| Готово | Статус |
|---|---|
| BrokerInterface контракт | ✅ |
| MockBroker (offline) | ✅ полностью функционален |
| RiskGuard | ✅ все проверки активны |
| TradeJournal | ✅ пишет в `runtime/trade_journal.jsonl` |
| BrokerHealth | ✅ |
| TInvestSandboxAdapter код | ✅ |
| CLI (`--mock`) | ✅ |
| gRPC для Python 3.14 | ⚠️ требует компиляции из исходников |
| T_INVEST_TOKEN | ⚠️ нужно получить sandbox-токен |
| CLI с реальным SDK | 🔜 после решения gRPC |

**Для первого реального теста в sandbox:**
1. Установить Python 3.12 или скомпилировать `grpcio` для 3.14.5
2. Получить T-Invest Sandbox API Token (бесплатно, Tinkoff Invest API)
3. `export T_INVEST_TOKEN=<token>`
4. `python scripts/run_broker_sandbox.py --health`
