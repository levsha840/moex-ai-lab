"""M12.5 — TradeJournal tests (12 tests)."""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.broker.trade_journal import TradeJournal
from services.broker.broker_models import (
    Order, OrderSide, OrderType, OrderStatus,
)


def _order(order_id="ORD-001", instrument="SBER", status=OrderStatus.FILLED,
           strategy_id="STRAT_A", cycle_id="cycle_0001") -> Order:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    return Order(
        order_id=order_id,
        instrument=instrument,
        side=OrderSide.BUY,
        quantity=2,
        price=258.0,
        order_type=OrderType.LIMIT,
        status=status,
        created_at=now,
        updated_at=now,
        filled_quantity=2,
        avg_price=258.0,
        strategy_id=strategy_id,
        cycle_id=cycle_id,
    )


class TestTradeJournalImport:
    def test_importable(self):
        from services.broker.trade_journal import TradeJournal
        assert TradeJournal is not None


class TestJournalWrite:
    def test_record_order_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal.jsonl"
            j = TradeJournal(path)
            j.record_order(_order())
            assert path.exists()

    def test_record_order_line_is_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal.jsonl"
            j = TradeJournal(path)
            j.record_order(_order())
            lines = path.read_text().splitlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["event"] == "ORDER_PLACED"
            assert entry["order_id"] == "ORD-001"

    def test_multiple_records_append(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "j.jsonl"
            j = TradeJournal(path)
            j.record_order(_order("O1"))
            j.record_order(_order("O2"))
            assert j.count() == 2

    def test_update_order(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "j.jsonl"
            j = TradeJournal(path)
            j.record_order(_order("O1"))
            j.update_order("O1", OrderStatus.CANCELLED, {"msg": "cancelled"})
            entries = j.read_all()
            assert len(entries) == 2
            assert entries[1]["event"] == "ORDER_UPDATED"

    def test_record_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "j.jsonl"
            j = TradeJournal(path)
            j.record_rejection("none", "kill_switch", "Kill switch ON", "STRAT_A")
            entries = j.read_all()
            assert entries[0]["event"] == "ORDER_REJECTED"
            assert entries[0]["data"]["rule"] == "kill_switch"


class TestJournalRead:
    def test_read_all_empty(self):
        with tempfile.TemporaryDirectory() as td:
            j = TradeJournal(Path(td) / "j.jsonl")
            assert j.read_all() == []

    def test_tail_returns_last_n(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "j.jsonl"
            j = TradeJournal(path)
            for i in range(10):
                j.record_order(_order(f"O{i}"))
            tail = j.tail(3)
            assert len(tail) == 3
            assert tail[-1]["order_id"] == "O9"

    def test_daily_count_today(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "j.jsonl"
            j = TradeJournal(path)
            j.record_order(_order("O1"))
            j.record_order(_order("O2"))
            assert j.daily_count() == 2

    def test_daily_count_other_date(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "j.jsonl"
            j = TradeJournal(path)
            j.record_order(_order("O1"))
            assert j.daily_count("1999-01-01") == 0


class TestJournalPersistence:
    def test_survives_reload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "j.jsonl"
            j1 = TradeJournal(path)
            j1.record_order(_order("O1"))
            # New instance — reads from same file
            j2 = TradeJournal(path)
            assert j2.count() == 1

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "deep" / "nested" / "j.jsonl"
            j = TradeJournal(path)
            j.record_order(_order())
            assert path.exists()
