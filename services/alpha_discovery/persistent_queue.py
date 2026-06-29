"""Persistent Alpha Discovery Queue — M12 Sprint 1.

Wraps the in-memory DiscoveryQueue with disk persistence so the queue
survives process restarts. The queue file is a single JSON document at
data/alpha/queue.json.

Design:
- load() on startup: restore pending entries from disk
- save() after any mutation: atomic write
- update_from_discovery(): merge fresh scheduler output with existing queue
  (new entries added, completed entries preserved)
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PersistentAlphaQueue:
    """Thread-safe, disk-backed alpha research queue."""

    def __init__(self, queue_path: Path) -> None:
        self._path = queue_path
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = []
        self._stats: dict[str, int] = {
            "total_added": 0,
            "total_completed": 0,
            "total_failed": 0,
        }
        self._created_at: str = _now()

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load queue from disk. No-op if file doesn't exist."""
        with self._lock:
            if not self._path.exists():
                return
            try:
                doc = json.loads(self._path.read_text(encoding="utf-8"))
                self._entries = doc.get("entries", [])
                self._stats = doc.get("stats", self._stats)
                self._created_at = doc.get("created_at", self._created_at)
            except (json.JSONDecodeError, OSError):
                self._entries = []

    def save(self) -> None:
        """Atomically write queue to disk."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            doc = {
                "schema": SCHEMA_VERSION,
                "created_at": self._created_at,
                "updated_at": _now(),
                "entries": self._entries,
                "stats": self._stats,
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._path)

    # ── Mutations ─────────────────────────────────────────────────────────────

    def push(self, entry: dict[str, Any]) -> str:
        """Add a new entry. Returns entry_id."""
        entry_id = entry.get("entry_id") or str(uuid.uuid4())[:8]
        with self._lock:
            # Skip exact duplicates (same strategy + instrument + priority)
            key = (entry.get("strategy_or_instrument"), entry.get("priority"))
            for existing in self._entries:
                if (
                    existing.get("strategy_or_instrument") == key[0]
                    and existing.get("priority") == key[1]
                    and existing.get("status") == "pending"
                ):
                    return existing["entry_id"]

            record = {
                "entry_id": entry_id,
                "strategy_or_instrument": entry.get("strategy_or_instrument", "?"),
                "priority": entry.get("priority", "MEDIUM"),
                "priority_score": entry.get("priority_score", 0.0),
                "estimated_cost": entry.get("estimated_cost", "MEDIUM"),
                "status": "pending",
                "attempts": 0,
                "max_attempts": 3,
                "reason": entry.get("reason", ""),
                "source": entry.get("source", "DISCOVERY_QUEUE"),
                "created_at": _now(),
                "updated_at": _now(),
                "completed_at": None,
            }
            self._entries.append(record)
            self._stats["total_added"] += 1
        return entry_id

    def mark_done(self, entry_id: str) -> bool:
        """Mark entry as completed."""
        with self._lock:
            for entry in self._entries:
                if entry["entry_id"] == entry_id and entry["status"] != "done":
                    entry["status"] = "done"
                    entry["completed_at"] = _now()
                    entry["updated_at"] = _now()
                    self._stats["total_completed"] += 1
                    return True
        return False

    def mark_failed(self, entry_id: str, reason: str = "") -> bool:
        """Increment attempts; mark as failed if max_attempts reached."""
        with self._lock:
            for entry in self._entries:
                if entry["entry_id"] == entry_id:
                    entry["attempts"] = entry.get("attempts", 0) + 1
                    entry["updated_at"] = _now()
                    if entry["attempts"] >= entry.get("max_attempts", 3):
                        entry["status"] = "failed"
                        entry["completed_at"] = _now()
                        entry["reason"] = reason or entry.get("reason", "")
                        self._stats["total_failed"] += 1
                    else:
                        entry["status"] = "pending"
                    return True
        return False

    def mark_in_progress(self, entry_id: str, lease_until: str = "") -> bool:
        """Claim entry for processing. lease_until (ISO) enables crash recovery."""
        with self._lock:
            for entry in self._entries:
                if entry["entry_id"] == entry_id and entry["status"] == "pending":
                    now = _now()
                    entry["status"] = "in_progress"
                    entry["claimed_at"] = now
                    entry["lease_until"] = lease_until
                    entry["updated_at"] = now
                    return True
        return False

    def recover_expired_leases(self) -> int:
        """Return stale in_progress entries to pending if lease_until < now."""
        from datetime import datetime, timezone
        now_str = _now()
        count = 0
        with self._lock:
            for entry in self._entries:
                if entry.get("status") != "in_progress":
                    continue
                lease_until = entry.get("lease_until", "")
                if not lease_until:
                    continue
                try:
                    # Parse both offset-aware and naive ISO strings
                    def _parse(s: str) -> datetime:
                        s = s.replace("Z", "+00:00")
                        return datetime.fromisoformat(s)
                    if _parse(now_str) > _parse(lease_until):
                        entry["status"] = "pending"
                        entry["updated_at"] = now_str
                        entry["claimed_at"] = ""
                        entry["lease_until"] = ""
                        count += 1
                except (ValueError, TypeError):
                    pass
        return count

    # ── Discovery sync ────────────────────────────────────────────────────────

    def update_from_discovery(self, queue_entries: list) -> dict:
        """
        Merge fresh AlphaDiscovery queue output with the persistent queue.

        New entries are added. Existing pending entries are updated with
        fresh priority scores. Completed/failed entries are preserved as
        history.
        """
        added = 0
        updated = 0

        existing_keys: dict[tuple, str] = {}
        with self._lock:
            for entry in self._entries:
                key = (entry.get("strategy_or_instrument"), entry.get("source", ""))
                existing_keys[key] = entry["entry_id"]

        for qe in queue_entries:
            # Support both QueueEntry (M10) and ScheduleEntry (M11)
            name = getattr(qe, "name", None) or getattr(qe, "strategy_or_instrument", "?")
            score = getattr(qe, "priority_score", 0.5)
            cost = getattr(qe, "estimated_research_cost", None) or getattr(qe, "estimated_cost", "MEDIUM")
            source = "DISCOVERY_QUEUE" if hasattr(qe, "draft_id") else "UNIVERSE_EXPANSION"

            priority = (
                "CRITICAL" if score >= 0.75
                else "HIGH" if score >= 0.55
                else "MEDIUM" if score >= 0.35
                else "LOW"
            )

            key = (name, source)
            if key in existing_keys:
                eid = existing_keys[key]
                with self._lock:
                    for entry in self._entries:
                        if entry["entry_id"] == eid and entry["status"] == "pending":
                            entry["priority"] = priority
                            entry["priority_score"] = round(score, 4)
                            entry["updated_at"] = _now()
                            updated += 1
                            break
            else:
                new_id = self.push({
                    "strategy_or_instrument": name,
                    "priority": priority,
                    "priority_score": round(score, 4),
                    "estimated_cost": cost,
                    "source": source,
                })
                existing_keys[key] = new_id
                added += 1

        with self._lock:
            self._entries.sort(
                key=lambda e: (
                    0 if e["status"] == "pending" else 1,
                    -e.get("priority_score", 0),
                )
            )

        total = len(self._entries)
        pending = sum(1 for e in self._entries if e["status"] == "pending")
        return {
            "added": added,
            "updated": updated,
            "total_entries": total,
            "pending_entries": pending,
        }

    # ── Queries ───────────────────────────────────────────────────────────────

    def next_pending(self) -> dict | None:
        """Return highest-priority pending entry without removing it."""
        with self._lock:
            for entry in self._entries:
                if entry["status"] == "pending":
                    return dict(entry)
        return None

    def all_pending(self) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._entries if e["status"] == "pending"]

    def all_entries(self) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._entries]

    def stats(self) -> dict:
        with self._lock:
            pending = sum(1 for e in self._entries if e["status"] == "pending")
            in_progress = sum(1 for e in self._entries if e["status"] == "in_progress")
            done = sum(1 for e in self._entries if e["status"] == "done")
            failed = sum(1 for e in self._entries if e["status"] == "failed")
            return {
                **self._stats,
                "pending": pending,
                "in_progress": in_progress,
                "done": done,
                "failed": failed,
                "total": len(self._entries),
            }
