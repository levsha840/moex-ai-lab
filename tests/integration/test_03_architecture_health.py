"""
Phase 4 — Architecture Health
Verify no duplicate data, no dead services, no stale routes, no broken paths.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ── Dead Storage ──────────────────────────────────────────────────────────────

class TestDeadStorage:
    def test_no_empty_dry_run_artifacts_in_knowledge(self):
        """data/knowledge/*/dry_run_test.json are test artifacts with 0 facts."""
        dry = list((PROJECT_ROOT / "data" / "knowledge").rglob("dry_run_test.json"))
        assert len(dry) == 0, (
            f"Found {len(dry)} dry_run_test.json artifacts: "
            + ", ".join(str(f.relative_to(PROJECT_ROOT)) for f in dry)
        )

    def test_legacy_knowledge_dir_not_read_by_api(self):
        """
        knowledge/ root dir is legacy — API must not point there.
        Backend routers should use data/knowledge/ only.
        """
        backend_dir = PROJECT_ROOT / "terminal" / "backend" / "routers"
        for router_file in backend_dir.glob("*.py"):
            content = router_file.read_text(encoding="utf-8")
            # Should not reference root knowledge/ without data/ prefix
            assert "ROOT / \"knowledge\"" not in content, (
                f"{router_file.name} references legacy knowledge/ root. "
                "Use data/knowledge/ instead."
            )

    def test_sessions_dir_matches_reports_count(self):
        """sessions/ and reports/ should have the same number of entries."""
        sessions_dir = PROJECT_ROOT / "sessions"
        reports_dir = PROJECT_ROOT / "reports"
        if not sessions_dir.exists():
            pytest.skip("sessions/ not found")

        session_count = len(list(sessions_dir.glob("*/session_meta.json")))
        report_count = len([p for p in reports_dir.glob("*/report.json")
                            if "visual_backtest" not in str(p)])
        assert abs(session_count - report_count) <= 5, (
            f"sessions/ ({session_count}) and reports/ ({report_count}) are out of sync. "
            "This suggests parallel research history stores."
        )


# ── Route Health ──────────────────────────────────────────────────────────────

class TestRouteHealth:
    def test_all_backend_routers_import(self):
        router_modules = [
            "terminal.backend.routers.dashboard",
            "terminal.backend.routers.research",
            "terminal.backend.routers.strategies",
            "terminal.backend.routers.paper",
            "terminal.backend.routers.knowledge",
            "terminal.backend.routers.scientist",
        ]
        for mod_name in router_modules:
            import importlib
            mod = importlib.import_module(mod_name)
            assert hasattr(mod, "router"), f"{mod_name} has no 'router' export"

    def test_strategies_router_reads_real_reports(self):
        """strategies.py reads from reports/ — must return >1000 findings."""
        from terminal.backend.routers.strategies import _all_findings
        findings = _all_findings()
        assert len(findings) >= 1800, (
            f"Strategy vault has only {len(findings)} findings. "
            "Expected >=1800 (all research sessions)."
        )

    def test_strategies_router_has_visual_backtest(self):
        from terminal.backend.routers.strategies import _all_findings
        findings = _all_findings()
        vb = [f for f in findings if f["status"] == "VISUAL_BACKTEST"]
        assert len(vb) >= 3, f"Expected >=3 VB entries, got {len(vb)}"

    def test_dashboard_data_paths_exist(self):
        """dashboard.py data sources must be accessible."""
        assert (PROJECT_ROOT / "reports").exists(), "reports/ dir missing"
        assert (PROJECT_ROOT / "data" / "universe" / "manifest_index.json").exists()


# ── Service Import Health ─────────────────────────────────────────────────────

class TestServiceImports:
    SERVICES = [
        "services.alpha_discovery.engine",
        "services.alpha_discovery.failure_analyzer",
        "services.alpha_discovery.feature_importance",
        "services.alpha_discovery.self_learning",
        "services.alpha_discovery.discovery_queue",
        "services.continuous_learning.pipeline",
        "services.continuous_learning.knowledge_updater",
        "services.continuous_learning.planner_bridge",
        "services.scheduler.discovery_scheduler",
        "services.universe.equity",
        "services.universe.futures",
        "services.universe.quality_checker",
        "services.validation.passport",
        "services.validation.pipeline",
    ]

    @pytest.mark.parametrize("module", SERVICES)
    def test_service_imports_without_error(self, module):
        import importlib
        mod = importlib.import_module(module)
        assert mod is not None


# ── Data Freshness ────────────────────────────────────────────────────────────

class TestDataFreshness:
    def test_store_version_at_least_11(self):
        store = json.loads(
            (PROJECT_ROOT / "data" / "knowledge" / "evolution" / "store.json")
            .read_text(encoding="utf-8")
        )
        assert store["version"] >= 11

    def test_store_ingestion_count_reasonable(self):
        store = json.loads(
            (PROJECT_ROOT / "data" / "knowledge" / "evolution" / "store.json")
            .read_text(encoding="utf-8")
        )
        assert store["ingestion_count"] >= 50, (
            f"Only {store['ingestion_count']} ingestions. "
            "KnowledgeStore may not be receiving new findings."
        )

    def test_runtime_status_exists(self):
        status = PROJECT_ROOT / "runtime" / "status.json"
        assert status.exists(), "runtime/status.json missing — no recent run recorded"
        d = json.loads(status.read_text(encoding="utf-8"))
        assert "status" in d
        assert d.get("tasks_failed", 0) == 0, f"Last runtime run had failures: {d}"


# ── Cyclic Dependency Check ───────────────────────────────────────────────────

class TestNoCyclicDependencies:
    def test_export_scripts_dont_import_from_each_other(self):
        """Export scripts should be independent (no cross-imports)."""
        scripts = [
            "scripts/export_universe_manifest.py",
            "scripts/export_alpha_discovery.py",
            "scripts/export_learning_state.py",
        ]
        for script_path in scripts:
            content = (PROJECT_ROOT / script_path).read_text(encoding="utf-8")
            script_name = Path(script_path).stem
            for other in scripts:
                other_name = Path(other).stem
                if other_name != script_name:
                    assert f"import {other_name}" not in content, (
                        f"{script_path} imports {other_name} — circular export dependency"
                    )

    def test_services_dont_import_terminal_backend(self):
        """Core services must not depend on terminal/backend."""
        service_files = list((PROJECT_ROOT / "services").rglob("*.py"))
        for f in service_files:
            if ".venv" in str(f) or "__pycache__" in str(f):
                continue
            content = f.read_text(encoding="utf-8", errors="ignore")
            assert "terminal.backend" not in content, (
                f"{f.relative_to(PROJECT_ROOT)} imports terminal.backend — "
                "services must be backend-independent"
            )
            assert "from terminal" not in content, (
                f"{f.relative_to(PROJECT_ROOT)} imports from terminal package"
            )
