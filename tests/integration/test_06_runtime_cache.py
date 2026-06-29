"""
M12 Sprint 1 — Integration Tests: Runtime Cache

Verifies the thread-safe TTL cache for legacy reports:
- Lazy loading
- TTL-based expiry
- Thread safety
- Manual invalidation
- dashboard.py and strategies.py use the cache
"""
from __future__ import annotations
import sys
import time
import threading
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestReportsCacheCore:
    def test_cache_importable(self):
        from services.cache.reports_cache import ReportsCache
        assert ReportsCache is not None

    def test_cache_loads_reports(self):
        from services.cache.reports_cache import ReportsCache
        reports_dir = PROJECT_ROOT / "reports"
        cache = ReportsCache(reports_dir)
        reports = cache.get_legacy_reports()
        assert len(reports) > 1000, f"Expected >1000 reports, got {len(reports)}"

    def test_cache_excludes_visual_backtest(self):
        from services.cache.reports_cache import ReportsCache
        reports_dir = PROJECT_ROOT / "reports"
        cache = ReportsCache(reports_dir)
        reports = cache.get_legacy_reports()
        for r in reports:
            assert "visual_backtest" not in r.get("_path", ""), \
                "VB report leaked into legacy_reports()"

    def test_cache_reports_have_path_and_mtime(self):
        from services.cache.reports_cache import ReportsCache
        cache = ReportsCache(PROJECT_ROOT / "reports")
        reports = cache.get_legacy_reports()[:5]
        for r in reports:
            assert "_path" in r
            assert "_mtime" in r

    def test_cache_second_call_returns_same_object(self):
        """Confirm cache hit — same list object returned without reload."""
        from services.cache.reports_cache import ReportsCache
        cache = ReportsCache(PROJECT_ROOT / "reports")
        r1 = cache.get_legacy_reports()
        r2 = cache.get_legacy_reports()
        assert r1 is r2, "Cache miss on second call — should return same object"

    def test_cache_invalidate_forces_reload(self):
        from services.cache.reports_cache import ReportsCache
        cache = ReportsCache(PROJECT_ROOT / "reports")
        r1 = cache.get_legacy_reports()
        cache.invalidate()
        assert not cache.is_warm(), "Cache should be cold after invalidate()"
        r2 = cache.get_legacy_reports()
        assert r1 is not r2, "After invalidate, should reload (new list object)"
        assert len(r1) == len(r2), "Same data should be loaded after re-read"

    def test_cache_age_seconds(self):
        from services.cache.reports_cache import ReportsCache
        cache = ReportsCache(PROJECT_ROOT / "reports")
        assert cache.age_seconds() == float("inf"), "Cold cache should have infinite age"
        _ = cache.get_legacy_reports()
        assert cache.age_seconds() < 5.0, "Freshly loaded cache should be < 5s old"

    def test_cache_is_warm_after_load(self):
        from services.cache.reports_cache import ReportsCache
        cache = ReportsCache(PROJECT_ROOT / "reports")
        assert not cache.is_warm()
        _ = cache.get_legacy_reports()
        assert cache.is_warm()
        cache.invalidate()
        assert not cache.is_warm()


class TestReportsCacheSingleton:
    def test_get_instance_returns_same_object(self):
        from services.cache.reports_cache import ReportsCache
        reports_dir = PROJECT_ROOT / "reports"
        c1 = ReportsCache.get_instance(reports_dir)
        c2 = ReportsCache.get_instance(reports_dir)
        assert c1 is c2, "get_instance should return singleton"

    def test_different_paths_give_different_instances(self):
        from services.cache.reports_cache import ReportsCache
        with tempfile.TemporaryDirectory() as tmp:
            d1 = PROJECT_ROOT / "reports"
            d2 = Path(tmp)
            c1 = ReportsCache.get_instance(d1)
            c2 = ReportsCache.get_instance(d2)
            assert c1 is not c2


class TestReportsCacheThreadSafety:
    def test_concurrent_reads_return_consistent_data(self):
        from services.cache.reports_cache import ReportsCache
        cache = ReportsCache(PROJECT_ROOT / "reports")

        results = []
        errors = []

        def reader():
            try:
                r = cache.get_legacy_reports()
                results.append(len(r))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(set(results)) == 1, "Concurrent reads returned different counts"

    def test_invalidate_during_reads_is_safe(self):
        from services.cache.reports_cache import ReportsCache
        cache = ReportsCache(PROJECT_ROOT / "reports")
        cache.get_legacy_reports()  # warm up

        errors = []

        def reader():
            for _ in range(5):
                try:
                    cache.get_legacy_reports()
                except Exception as exc:
                    errors.append(str(exc))

        def invalidator():
            for _ in range(3):
                cache.invalidate()
                time.sleep(0.01)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        threads.append(threading.Thread(target=invalidator))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors during invalidate: {errors}"


class TestCacheIntegration:
    def test_dashboard_router_uses_cache(self):
        """dashboard._legacy_reports() must delegate to ReportsCache."""
        import inspect
        from terminal.backend.routers import dashboard
        source = inspect.getsource(dashboard._legacy_reports)
        assert "ReportsCache" in source, "_legacy_reports() must use ReportsCache"

    def test_strategies_router_uses_cache(self):
        """strategies._all_findings() must delegate to ReportsCache."""
        import inspect
        from terminal.backend.routers import strategies
        source = inspect.getsource(strategies._all_findings)
        assert "ReportsCache" in source, "_all_findings() must use ReportsCache"

    def test_dashboard_status_runs_without_error(self):
        from terminal.backend.routers.dashboard import get_status
        result = get_status()
        assert result["research"]["sessions"] > 1000
        assert result["research_budget"]["total"] > 1000

    def test_strategies_list_runs_without_error(self):
        from terminal.backend.routers.strategies import _all_findings
        findings = _all_findings()
        assert len(findings) > 1000

    def test_cache_shared_between_dashboard_and_strategies(self):
        """Both routers share the same singleton cache."""
        from services.cache.reports_cache import ReportsCache
        from terminal.backend.routers import dashboard, strategies

        reports_dir = PROJECT_ROOT / "reports"
        singleton = ReportsCache.get_instance(reports_dir)

        # Warm via dashboard
        dashboard._legacy_reports()
        assert singleton.is_warm(), "Cache should be warm after dashboard call"

        # strategies reads from the same singleton — cache still warm
        age_before = singleton.age_seconds()
        _ = strategies._all_findings()
        age_after = singleton.age_seconds()
        assert age_after >= age_before, "Age should not reset on strategies read"
