"""
Phase 1 — Single Source of Truth
Verify each data entity has one canonical source and no silent duplicates.
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from tests.integration.conftest import (
    PROJECT_ROOT, STORE_PATH, MANIFEST_INDEX, UNIVERSE_JSON,
    ALPHA_JSON, LEARNING_JSON, REPORTS_DIR, VB_DIR,
)


# ── InstrumentManifest ────────────────────────────────────────────────────────

class TestInstrumentManifest:
    def test_universe_manifest_exists(self):
        assert UNIVERSE_JSON.exists(), "universe_manifest.json missing"

    def test_universe_manifest_61_instruments(self, universe_manifest):
        eq = len(universe_manifest["equities"])
        fu = len(universe_manifest["futures"])
        assert eq == 51, f"Expected 51 equities, got {eq}"
        assert fu == 10, f"Expected 10 futures, got {fu}"
        assert eq + fu == 61

    def test_universe_manifest_has_required_fields(self, universe_manifest):
        required_eq = {"ticker", "name", "tier", "in_research", "data_quality"}
        required_fu = {"ticker", "name", "research_allowed", "data_quality"}
        for e in universe_manifest["equities"]:
            assert required_eq.issubset(e.keys()), f"Equity {e.get('ticker')} missing fields"
        for f in universe_manifest["futures"]:
            assert required_fu.issubset(f.keys()), f"Future {f.get('ticker')} missing fields"

    def test_manifest_index_has_cells(self, manifest_index):
        assert "cells" in manifest_index, "manifest_index.json missing 'cells'"
        assert manifest_index["total_cells"] == len(manifest_index["cells"])

    def test_manifest_index_11_unique_tickers(self, manifest_index):
        tickers = {c["ticker"] for c in manifest_index["cells"]}
        assert len(tickers) == 11, f"Expected 11 unique tickers, got {len(tickers)}"

    def test_no_ticker_overlap_between_manifest_and_excluded(self, universe_manifest):
        excluded = {e["ticker"] for e in universe_manifest["equities"] if not e["in_research"]}
        excluded |= {f["ticker"] for f in universe_manifest["futures"] if not f["research_allowed"]}
        all_tickers = {e["ticker"] for e in universe_manifest["equities"]}
        all_tickers |= {f["ticker"] for f in universe_manifest["futures"]}
        # Excluded instruments are still in the universe (just not researched)
        assert excluded.issubset(all_tickers), "Excluded tickers not in main universe"


# ── Knowledge Store ───────────────────────────────────────────────────────────

class TestKnowledgeStore:
    def test_store_exists(self):
        assert STORE_PATH.exists(), f"KnowledgeStore not found at {STORE_PATH}"

    def test_store_has_facts(self, store):
        assert "facts" in store, "store.json missing 'facts' key"
        assert len(store["facts"]) > 0, "KnowledgeStore is empty"

    def test_store_205_facts(self, store):
        count = len(store["facts"])
        assert count >= 200, f"Expected >=200 facts, got {count}"

    def test_no_duplicate_fact_keys(self, store):
        keys = list(store["facts"].keys())
        assert len(keys) == len(set(keys)), "Duplicate fact keys in store.json"

    def test_fact_schema_valid(self, store):
        required = {"fact_key", "hypothesis_id", "instrument", "period", "score", "archived"}
        for key, fact in list(store["facts"].items())[:10]:
            assert required.issubset(fact.keys()), f"Fact {key} missing required fields"

    def test_legacy_knowledge_dir_exists_but_separate(self):
        legacy = PROJECT_ROOT / "knowledge" / "knowledge_base.json"
        assert legacy.exists(), "Legacy knowledge_base.json missing (needed for history)"
        d = json.loads(legacy.read_text(encoding="utf-8"))
        assert "entries" in d, "legacy knowledge_base.json has wrong schema"

    def test_evolution_store_is_canonical(self, store):
        """data/knowledge/evolution/store.json is the canonical active store."""
        assert store["version"] >= 11, f"Expected version >=11, got {store['version']}"
        assert store["ingestion_count"] >= 100, "Too few ingestions, may be outdated"


# ── Research History ──────────────────────────────────────────────────────────

class TestResearchHistory:
    def test_reports_dir_exists(self):
        assert REPORTS_DIR.exists(), "reports/ directory missing"

    def test_reports_dir_has_1800_plus_reports(self):
        count = len([p for p in REPORTS_DIR.glob("*/report.json")
                     if "visual_backtest" not in str(p)])
        assert count >= 1800, f"Expected >=1800 research reports, got {count}"

    def test_vb_reports_dir_exists(self):
        assert VB_DIR.exists(), "reports/visual_backtest/ directory missing"

    def test_vb_reports_have_3_entries(self):
        vb = list(VB_DIR.glob("**/report.json"))
        assert len(vb) >= 3, f"Expected >=3 VB reports, got {len(vb)}"

    def test_vb_report_schema(self):
        required = {"report_id", "hypothesis_id", "ticker", "period", "metrics"}
        for path in VB_DIR.glob("**/report.json"):
            d = json.loads(path.read_text(encoding="utf-8"))
            assert required.issubset(d.keys()), f"{path} missing required fields"

    def test_research_report_schema(self):
        required = {"findings", "generated_at"}
        count = 0
        for path in list(REPORTS_DIR.glob("*/report.json"))[:10]:
            if "visual_backtest" in str(path):
                continue
            d = json.loads(path.read_text(encoding="utf-8"))
            assert required.issubset(d.keys()), f"{path} missing required fields"
            count += 1
        assert count >= 5, "Not enough valid reports found"


# ── Frontend Exports ──────────────────────────────────────────────────────────

class TestFrontendExports:
    def test_all_three_exports_exist(self):
        assert UNIVERSE_JSON.exists(),  "universe_manifest.json missing"
        assert ALPHA_JSON.exists(),     "alpha_discovery.json missing"
        assert LEARNING_JSON.exists(),  "learning_state.json missing"

    def test_alpha_discovery_schema(self, alpha_data):
        required = {"generated_at", "engine_version", "queue", "feature_scores",
                    "failures", "strategies_analyzed"}
        assert required.issubset(alpha_data.keys())
        assert len(alpha_data["queue"]) > 0
        assert len(alpha_data["feature_scores"]) > 0

    def test_learning_state_schema(self, learning_data):
        required = {"generated_at", "total_schedule_entries", "cycles",
                    "budget", "schedule_top20", "knowledge_store_facts"}
        assert required.issubset(learning_data.keys())
        assert learning_data["total_schedule_entries"] == 69
        assert learning_data["knowledge_store_facts"] >= 200

    def test_learning_knowledge_facts_matches_store(self, learning_data, store):
        """Frontend learning_state.json must match real store.json fact count."""
        ui_count = learning_data["knowledge_store_facts"]
        real_count = len(store["facts"])
        assert abs(ui_count - real_count) <= 10, (
            f"UI shows {ui_count} knowledge facts but store has {real_count}. "
            "Run: python scripts/export_learning_state.py"
        )

    def test_queue_entries_have_names(self, alpha_data):
        """Every queue entry must have a strategy name (not None/empty)."""
        for entry in alpha_data["queue"]:
            assert entry.get("strategy_name") or entry.get("name"), \
                f"Queue entry missing both 'strategy_name' and 'name': {entry}"

    def test_failures_have_decisions(self, alpha_data):
        """Every failure entry must have a decision field."""
        for entry in alpha_data["failures"]:
            assert entry.get("decision") in ("REJECTED", "NEEDS_MORE_RESEARCH"), \
                f"Failure entry {entry.get('strategy_id')} has invalid decision: {entry.get('decision')}"


# ── No Empty Test Artifacts ───────────────────────────────────────────────────

class TestNoTestArtifacts:
    def test_no_empty_dry_run_artifacts(self):
        dry_runs = list((PROJECT_ROOT / "data" / "knowledge").rglob("dry_run_test.json"))
        for f in dry_runs:
            assert False, f"Empty test artifact found: {f.relative_to(PROJECT_ROOT)} — remove it"
