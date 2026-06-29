"""Thread-safe TTL cache for legacy research reports.

Eliminates repeated filesystem scans of 1817+ report.json files on every
API call to /api/dashboard/status and /api/strategies.

Design:
- Singleton per reports_dir path
- Lazy: first read populates the cache
- 60-second TTL: automatic invalidation
- Thread-safe: threading.Lock protects all mutations
- Invalidate explicitly after research session or event pipeline cycle
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


class ReportsCache:
    _instances: dict[str, "ReportsCache"] = {}
    _class_lock = threading.Lock()

    TTL_SECONDS: float = 60.0

    def __init__(self, reports_dir: Path) -> None:
        self._reports_dir = reports_dir
        self._cache: list[dict] | None = None
        self._loaded_at: float = 0.0
        self._lock = threading.Lock()

    # ── Singleton factory ─────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls, reports_dir: Path) -> "ReportsCache":
        key = str(reports_dir.resolve())
        if key not in cls._instances:
            with cls._class_lock:
                if key not in cls._instances:
                    cls._instances[key] = cls(reports_dir)
        return cls._instances[key]

    # ── Public API ────────────────────────────────────────────────────────────

    def get_legacy_reports(self) -> list[dict]:
        """Return cached list of raw report dicts. Reloads if TTL expired."""
        with self._lock:
            if self._is_stale():
                self._cache = self._load()
                self._loaded_at = time.monotonic()
        return self._cache  # type: ignore[return-value]

    def invalidate(self) -> None:
        """Force cache to reload on next access."""
        with self._lock:
            self._cache = None
            self._loaded_at = 0.0

    def is_warm(self) -> bool:
        with self._lock:
            return self._cache is not None and not self._is_stale()

    def age_seconds(self) -> float:
        with self._lock:
            if self._loaded_at == 0.0:
                return float("inf")
            return time.monotonic() - self._loaded_at

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_stale(self) -> bool:
        return (
            self._cache is None
            or time.monotonic() - self._loaded_at > self.TTL_SECONDS
        )

    def _load(self) -> list[dict]:
        results: list[dict] = []
        for path in self._reports_dir.glob("*/report.json"):
            if "visual_backtest" in str(path):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["_path"] = str(path)
                data["_mtime"] = os.path.getmtime(path)
                results.append(data)
            except Exception:
                pass
        results.sort(key=lambda x: x["_mtime"], reverse=True)
        return results
