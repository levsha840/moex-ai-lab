"""M12.5 — TradeJournal.

Append-only JSONL log of all order lifecycle events.
Each line is a JSON dict with: ts, event_type, order_id, data.

The journal is the authoritative record of what the broker was asked to do and
what it returned. It never overwrites entries — only appends.

Thread-safe via threading.Lock.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .broker_models import Order, OrderStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class TradeJournal:
    """Append-only trade journal stored as JSONL.

    Each entry:
        {
            "ts":         ISO timestamp,
            "event":      "ORDER_PLACED" | "ORDER_UPDATED" | ...,
            "order_id":   str,
            "strategy_id": str,
            "cycle_id":   str,
            "data":       dict  (full order snapshot or update delta)
        }
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    # ── Write ─────────────────────────────────────────────────────────────────

    def record_order(
        self,
        order: Order,
        event: str = "ORDER_PLACED",
        reason: str = "",
    ) -> None:
        """Append an order snapshot to the journal."""
        entry = {
            "ts":          _now(),
            "event":       event,
            "order_id":    order.order_id,
            "strategy_id": order.strategy_id,
            "cycle_id":    order.cycle_id,
            "reason":      reason,
            "data":        order.to_dict(),
        }
        self._append(entry)

    def update_order(
        self,
        order_id: str,
        status: OrderStatus,
        broker_response: dict | None = None,
        filled_quantity: int = 0,
        avg_price: float = 0.0,
    ) -> None:
        """Append an update entry for an existing order."""
        entry = {
            "ts":       _now(),
            "event":    "ORDER_UPDATED",
            "order_id": order_id,
            "data": {
                "status":           status.value,
                "broker_response":  broker_response or {},
                "filled_quantity":  filled_quantity,
                "avg_price":        avg_price,
            },
        }
        self._append(entry)

    def record_rejection(
        self,
        order_id: str,
        rule: str,
        reason: str,
        strategy_id: str = "",
        cycle_id: str = "",
    ) -> None:
        """Append a risk-rejection entry."""
        entry = {
            "ts":          _now(),
            "event":       "ORDER_REJECTED",
            "order_id":    order_id,
            "strategy_id": strategy_id,
            "cycle_id":    cycle_id,
            "data": {
                "rule":   rule,
                "reason": reason,
            },
        }
        self._append(entry)

    # ── Read ──────────────────────────────────────────────────────────────────

    def read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: list[dict] = []
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass
        return entries

    def tail(self, n: int = 20) -> list[dict]:
        return self.read_all()[-n:]

    def daily_count(self, date_str: str | None = None) -> int:
        """Count ORDER_PLACED entries for a given date (default: today UTC)."""
        target = date_str or _today()
        return sum(
            1
            for e in self.read_all()
            if e.get("event") == "ORDER_PLACED" and e.get("ts", "").startswith(target)
        )

    def count(self) -> int:
        return len(self.read_all())

    @property
    def path(self) -> Path:
        return self._path

    # ── Internal ──────────────────────────────────────────────────────────────

    def _append(self, entry: dict) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
