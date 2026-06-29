"""M12 Sprint 2 — RuntimeJournal.

Append-only JSONL log: records not just what happened, but why.
Each entry: {ts, event, reason, data}.

Thread-safe. Never overwrites. Survives crashes (append mode).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeJournal:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def record(
        self,
        event_type: str,
        data: dict | None = None,
        reason: str = "",
    ) -> None:
        """Append one entry to the journal JSONL file."""
        entry = {
            "ts": _now(),
            "event": event_type,
            "reason": reason,
            "data": data or {},
        }
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
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

    def tail(self, n: int) -> list[dict]:
        return self.read_all()[-n:]

    def count(self) -> int:
        return len(self.read_all())

    @property
    def path(self) -> Path:
        return self._path
