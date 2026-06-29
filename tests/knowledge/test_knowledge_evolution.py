"""Tests for Knowledge Evolution Layer — M4 Sprint 2.

Coverage:
    TestFactScore          — FactScore creation + validation
    TestMergeNewFact       — ingest creates new EnrichedFacts correctly
    TestMergeUpdateFact    — repeated ingest updates existing facts
    TestConfirmBoost       — passed=True raises confidence
    TestRefutePenalty      — passed=False lowers confidence
    TestAutoArchive        — auto-archive below ARCHIVE_THRESHOLD
    TestConflictDetection  — contradicting observations create ConflictRecord
    TestVersioning         — each ingest writes versioned snapshot file
    TestEvolutionDelta     — delta has correct counts after ingest
    TestEvolutionReport    — build_report returns correct aggregate
    TestDiff               — diff(v_old, v_new) shows changes correctly
    TestDecay              — apply_decay reduces confidence on stale facts
    TestCLIReport          — CLI --report runs without error
    TestCLIDiff            — CLI --diff v1 v2 runs without error
    TestNoGitOps           — no git operations in source code
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Project root ──────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from services.knowledge.evolution import (
    ARCHIVE_THRESHOLD,
    CONFIRM_BOOST,
    REFUTE_PENALTY,
    KnowledgeStore,
    FactScore,
    EnrichedFact,
    ConflictRecord,
    EvolutionDelta,
    EvolutionReport,
    EvolutionDiff,
    _fact_key,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path):
    return KnowledgeStore(tmp_path / "evolution")


def _report(hyp="H-ADX", instr="SBER", period="2023", regime="TREND_UP",
            passed=True, confidence=0.7, source="r1.json"):
    return {
        "hypothesis_id": hyp,
        "instrument":    instr,
        "period":        period,
        "regime":        regime,
        "passed":        passed,
        "confidence":    confidence,
        "source_ref":    source,
        "metric":        "pass_rate",
        "value":         0.65 if passed else 0.25,
    }


def _ingest_one(store, **kw):
    return store.ingest([_report(**kw)])


# ─────────────────────────────────────────────────────────────────────────────
# TestFactScore
# ─────────────────────────────────────────────────────────────────────────────

class TestFactScore:
    def test_fields_present(self):
        s = FactScore(
            confidence=0.7, evidence_count=3,
            success_count=2, failure_count=1,
            last_seen="2026-01-01T00:00:00+00:00",
            decay_score=1.0, stability_score=0.5,
        )
        assert s.confidence == 0.7
        assert s.success_count == 2
        assert s.stability_score == 0.5

    def test_all_fields_stored(self):
        s = FactScore(0.5, 1, 1, 0, "ts", 1.0, 1.0)
        assert s.evidence_count == 1
        assert s.failure_count == 0
        assert s.decay_score == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TestMergeNewFact
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeNewFact:
    def test_new_fact_created(self, store):
        _ingest_one(store, hyp="H-1", instr="SBER")
        fkey = _fact_key("H-1", "SBER", "2023", "TREND_UP")
        ef = store.get_fact(fkey)
        assert ef is not None
        assert ef.hypothesis_id == "H-1"
        assert ef.instrument    == "SBER"

    def test_initial_evidence_count_is_1(self, store):
        _ingest_one(store)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.score.evidence_count == 1

    def test_initial_not_archived(self, store):
        _ingest_one(store)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.archived is False

    def test_source_ref_recorded(self, store):
        _ingest_one(store, source="my_source.json")
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert "my_source.json" in ef.source_refs

    def test_fact_key_canonical(self, store):
        _ingest_one(store, hyp="H-42", instr="GAZP", period="2021", regime="FLAT")
        expected = "H-42__GAZP__2021__FLAT"
        assert store.get_fact(expected) is not None

    def test_empty_fields_normalized_in_key(self):
        k = _fact_key("H-X", "", "2022", "")
        assert "all" in k   # instrument → "all"
        assert "any" in k   # regime → "any"


# ─────────────────────────────────────────────────────────────────────────────
# TestMergeUpdateFact
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeUpdateFact:
    def test_evidence_count_increments(self, store):
        _ingest_one(store)
        _ingest_one(store)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.score.evidence_count == 2

    def test_source_refs_accumulate(self, store):
        _ingest_one(store, source="s1.json")
        _ingest_one(store, source="s2.json")
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert "s1.json" in ef.source_refs
        assert "s2.json" in ef.source_refs

    def test_duplicate_source_ref_not_duplicated(self, store):
        _ingest_one(store, source="same.json")
        _ingest_one(store, source="same.json")
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.source_refs.count("same.json") == 1

    def test_separate_phenomena_not_merged(self, store):
        store.ingest([
            _report(instr="SBER"),
            _report(instr="GAZP"),
        ])
        k1 = _fact_key("H-ADX", "SBER", "2023", "TREND_UP")
        k2 = _fact_key("H-ADX", "GAZP", "2023", "TREND_UP")
        assert store.get_fact(k1) is not None
        assert store.get_fact(k2) is not None
        assert store.get_fact(k1).score.evidence_count == 1
        assert store.get_fact(k2).score.evidence_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestConfirmBoost
# ─────────────────────────────────────────────────────────────────────────────

class TestConfirmBoost:
    def test_passed_true_raises_confidence(self, store):
        _ingest_one(store, passed=True, confidence=0.6)
        ef1 = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        c1 = ef1.score.confidence

        _ingest_one(store, passed=True, confidence=0.6)
        ef2 = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef2.score.confidence > c1

    def test_success_count_increments(self, store):
        _ingest_one(store, passed=True)
        _ingest_one(store, passed=True)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.score.success_count == 2

    def test_confidence_never_exceeds_max(self, store):
        for _ in range(30):
            _ingest_one(store, passed=True, confidence=0.99)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.score.confidence <= 0.99


# ─────────────────────────────────────────────────────────────────────────────
# TestRefutePenalty
# ─────────────────────────────────────────────────────────────────────────────

class TestRefutePenalty:
    def test_passed_false_lowers_confidence(self, store):
        _ingest_one(store, passed=True, confidence=0.8)
        ef1 = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        c1 = ef1.score.confidence

        _ingest_one(store, passed=False)
        ef2 = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef2.score.confidence < c1

    def test_failure_count_increments(self, store):
        _ingest_one(store, passed=True)
        _ingest_one(store, passed=False)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.score.failure_count == 1

    def test_confidence_never_below_zero(self, store):
        _ingest_one(store, passed=True, confidence=0.01)
        for _ in range(30):
            _ingest_one(store, passed=False)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.score.confidence >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestAutoArchive
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoArchive:
    def test_low_confidence_triggers_archive(self, store):
        """Drive confidence below ARCHIVE_THRESHOLD by repeated refutations."""
        _ingest_one(store, passed=True, confidence=0.05)
        for _ in range(20):
            _ingest_one(store, passed=False)
        ef = store.get_fact(_fact_key("H-ADX", "SBER", "2023", "TREND_UP"))
        assert ef.archived is True

    def test_archived_fact_in_archived_list(self, store):
        _ingest_one(store, passed=True, confidence=0.05)
        for _ in range(20):
            _ingest_one(store, passed=False)
        assert any(
            ef.archived for ef in store.archived_facts()
        )

    def test_archived_fact_not_in_active_list(self, store):
        _ingest_one(store, passed=True, confidence=0.05)
        for _ in range(20):
            _ingest_one(store, passed=False)
        key = _fact_key("H-ADX", "SBER", "2023", "TREND_UP")
        assert all(ef.fact_key != key for ef in store.active_facts())

    def test_archived_counted_in_delta(self, store):
        _ingest_one(store, passed=True, confidence=0.05)
        deltas = []
        for _ in range(20):
            d = _ingest_one(store, passed=False)
            deltas.append(d)
        total_archived = sum(d.facts_archived for d in deltas)
        assert total_archived >= 1


# ─────────────────────────────────────────────────────────────────────────────
# TestConflictDetection
# ─────────────────────────────────────────────────────────────────────────────

class TestConflictDetection:
    def test_conflict_when_passed_flips(self, store):
        _ingest_one(store, passed=True)
        _ingest_one(store, passed=False)
        conflicts = store.all_conflicts()
        assert len(conflicts) == 1

    def test_conflict_has_correct_hypothesis(self, store):
        _ingest_one(store, hyp="H-X", passed=True)
        _ingest_one(store, hyp="H-X", passed=False)
        c = store.all_conflicts()[0]
        assert c.hypothesis_id == "H-X"

    def test_conflict_records_both_sides(self, store):
        _ingest_one(store, passed=True,  source="s1.json")
        _ingest_one(store, passed=False, source="s2.json")
        c = store.all_conflicts()[0]
        assert c.passed_a is True
        assert c.passed_b is False

    def test_no_conflict_when_consistent(self, store):
        _ingest_one(store, passed=True)
        _ingest_one(store, passed=True)
        assert len(store.all_conflicts()) == 0

    def test_no_conflict_when_passed_is_none(self, store):
        _ingest_one(store, passed=None)
        _ingest_one(store, passed=None)
        assert len(store.all_conflicts()) == 0

    def test_conflict_is_unresolved_by_default(self, store):
        _ingest_one(store, passed=True)
        _ingest_one(store, passed=False)
        c = store.all_conflicts()[0]
        assert c.resolved is False

    def test_resolve_conflict(self, store):
        _ingest_one(store, passed=True)
        _ingest_one(store, passed=False)
        cid = store.all_conflicts()[0].conflict_id
        ok = store.resolve_conflict(cid, note="Regime shifted")
        assert ok is True
        assert store.unresolved_conflicts() == []

    def test_different_facts_no_cross_conflict(self, store):
        # H-A passes, H-B fails — no conflict because different hypotheses
        store.ingest([
            _report(hyp="H-A", passed=True),
            _report(hyp="H-B", passed=False),
        ])
        store.ingest([
            _report(hyp="H-A", passed=True),
            _report(hyp="H-B", passed=False),
        ])
        assert len(store.all_conflicts()) == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestVersioning
# ─────────────────────────────────────────────────────────────────────────────

class TestVersioning:
    def test_version_starts_at_zero(self, store):
        assert store.version == 0

    def test_version_increments_on_ingest(self, store):
        _ingest_one(store)
        assert store.version == 1
        _ingest_one(store)
        assert store.version == 2

    def test_version_file_written(self, store, tmp_path):
        _ingest_one(store)
        snap_dir = tmp_path / "evolution" / "versions"
        files = list(snap_dir.glob("*.json"))
        assert len(files) == 1
        assert "v001" in files[0].name

    def test_version_file_contains_facts(self, store, tmp_path):
        _ingest_one(store)
        snap_dir = tmp_path / "evolution" / "versions"
        snap = json.loads(list(snap_dir.glob("*.json"))[0].read_text())
        assert snap["version"] == 1
        assert snap["total_facts"] == 1
        assert snap["active_facts"] == 1

    def test_multiple_version_files(self, store, tmp_path):
        _ingest_one(store)
        _ingest_one(store, instr="GAZP")
        snap_dir = tmp_path / "evolution" / "versions"
        files = sorted(snap_dir.glob("*.json"))
        assert len(files) == 2
        assert "v001" in files[0].name
        assert "v002" in files[1].name

    def test_version_snapshot_has_avg_confidence(self, store, tmp_path):
        _ingest_one(store, confidence=0.8)
        snap_dir = tmp_path / "evolution" / "versions"
        snap = json.loads(list(snap_dir.glob("*.json"))[0].read_text())
        assert "avg_confidence" in snap
        assert snap["avg_confidence"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# TestEvolutionDelta
# ─────────────────────────────────────────────────────────────────────────────

class TestEvolutionDelta:
    def test_new_facts_counted(self, store):
        delta = store.ingest([_report(instr="SBER"), _report(instr="GAZP")])
        assert delta.facts_new == 2

    def test_updated_facts_counted(self, store):
        store.ingest([_report(instr="SBER")])
        delta = store.ingest([_report(instr="SBER")])
        assert delta.facts_updated == 1
        assert delta.facts_new == 0

    def test_delta_has_version(self, store):
        delta = _ingest_one(store)
        assert delta.version == 1

    def test_delta_has_campaign_id(self, store):
        delta = store.ingest([_report()], )
        assert delta.campaign_id == "manual"

    def test_confidence_delta_positive_on_confirm(self, store):
        _ingest_one(store, passed=True, confidence=0.6)
        delta = _ingest_one(store, passed=True, confidence=0.6)
        assert delta.avg_confidence_after >= delta.avg_confidence_before

    def test_delta_archived_keys_listed(self, store):
        _ingest_one(store, passed=True, confidence=0.05)
        archived_total = 0
        for _ in range(20):
            d = _ingest_one(store, passed=False)
            archived_total += d.facts_archived
        assert archived_total >= 1

    def test_empty_ingest_returns_delta(self, store):
        delta = store.ingest([])
        assert delta.facts_new == 0
        assert delta.facts_updated == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestEvolutionReport
# ─────────────────────────────────────────────────────────────────────────────

class TestEvolutionReport:
    def test_report_has_all_fields(self, store):
        _ingest_one(store)
        r = store.build_report()
        assert isinstance(r, EvolutionReport)
        assert r.total_facts     >= 1
        assert r.active_facts    >= 1
        assert r.store_version   == 1
        assert r.ingestion_count == 1

    def test_report_counts_active_vs_archived(self, store):
        store.ingest([_report(instr="SBER"), _report(instr="GAZP")])
        r = store.build_report()
        assert r.total_facts  == 2
        assert r.active_facts == 2
        assert r.archived_facts == 0

    def test_report_top_by_confidence_not_empty(self, store):
        store.ingest([_report(instr="SBER", confidence=0.9),
                      _report(instr="GAZP", confidence=0.3)])
        r = store.build_report()
        assert len(r.top_by_confidence) > 0

    def test_report_recommendations_not_empty(self, store):
        _ingest_one(store)
        r = store.build_report()
        assert len(r.recommendations) > 0

    def test_report_conflicts_listed(self, store):
        _ingest_one(store, passed=True)
        _ingest_one(store, passed=False)
        r = store.build_report()
        assert r.unresolved_conflicts == 1
        assert len(r.active_conflicts) == 1

    def test_report_written_to_disk(self, store, tmp_path):
        _ingest_one(store)
        store.build_report()
        rdir = tmp_path / "evolution" / "evolution_reports"
        files = list(rdir.glob("*.json"))
        assert len(files) >= 1

    def test_report_md_written(self, store, tmp_path):
        _ingest_one(store)
        store.build_report()
        rdir = tmp_path / "evolution" / "evolution_reports"
        md_files = list(rdir.glob("*.md"))
        assert len(md_files) >= 1

    def test_total_knowledge_score_positive(self, store):
        _ingest_one(store, confidence=0.8, passed=True)
        r = store.build_report()
        assert r.total_knowledge_score > 0.0

    def test_avg_confidence_in_range(self, store):
        _ingest_one(store, confidence=0.7)
        r = store.build_report()
        assert 0.0 <= r.avg_confidence <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TestDiff
# ─────────────────────────────────────────────────────────────────────────────

class TestDiff:
    def test_diff_added_keys(self, store):
        _ingest_one(store, instr="SBER")       # v1
        _ingest_one(store, instr="GAZP")       # v2 — new instrument
        d = store.diff(1, 2)
        gazp_key = _fact_key("H-ADX", "GAZP", "2023", "TREND_UP")
        assert gazp_key in d.added_keys

    def test_diff_changed_keys(self, store):
        _ingest_one(store, passed=True,  confidence=0.5)  # v1
        _ingest_one(store, passed=True,  confidence=0.5)  # v2 — confidence changes
        d = store.diff(1, 2)
        assert len(d.changed_keys) > 0

    def test_diff_confidence_delta_sign(self, store):
        _ingest_one(store, passed=True, confidence=0.5)   # v1
        _ingest_one(store, passed=True, confidence=0.5)   # v2 — confirm → up
        d = store.diff(1, 2)
        if d.confidence_delta:
            for info in d.confidence_delta.values():
                assert info["delta"] > 0

    def test_diff_missing_version_raises(self, store):
        _ingest_one(store)
        with pytest.raises(FileNotFoundError):
            store.diff(99, 100)

    def test_diff_summary_not_empty(self, store):
        _ingest_one(store)
        _ingest_one(store)
        d = store.diff(1, 2)
        assert len(d.summary) > 0

    def test_diff_removed_keys_on_archive(self, store):
        """A fact that flips to archived between versions appears in removed_keys."""
        _ingest_one(store, passed=True, confidence=0.05)  # v1 — low conf, active
        # Drive to archive via repeated failures
        last_delta = None
        for _ in range(20):
            last_delta = _ingest_one(store, passed=False)
        v_start = 1
        v_end = store.version
        d = store.diff(v_start, v_end)
        if last_delta and last_delta.facts_archived > 0:
            # archived fact should appear in removed_keys of the diff
            archived_key = last_delta.archived_fact_keys[0]
            # In the latest version it's archived, so removed from active view
            assert archived_key in d.removed_keys or archived_key in d.changed_keys


# ─────────────────────────────────────────────────────────────────────────────
# TestDecay
# ─────────────────────────────────────────────────────────────────────────────

class TestDecay:
    def test_fresh_facts_not_decayed(self, store):
        _ingest_one(store)
        decayed = store.apply_decay()
        # Fact was just created — less than 1 day old
        assert len(decayed) == 0

    def test_stale_facts_decayed(self, store):
        _ingest_one(store)
        # Patch the last_seen to be 30 days ago
        key = _fact_key("H-ADX", "SBER", "2023", "TREND_UP")
        ef = store.get_fact(key)
        old_ts = "2026-01-01T00:00:00+00:00"
        from dataclasses import asdict
        from services.knowledge.evolution import FactScore, EnrichedFact
        new_score = FactScore(
            confidence      = ef.score.confidence,
            evidence_count  = ef.score.evidence_count,
            success_count   = ef.score.success_count,
            failure_count   = ef.score.failure_count,
            last_seen       = old_ts,
            decay_score     = ef.score.decay_score,
            stability_score = ef.score.stability_score,
        )
        store._facts[key] = EnrichedFact(
            **{**asdict(ef), "score": new_score}
        )
        store._facts[key].score.__class__  # access doesn't mutate

        # Re-assign through proper reconstruction
        ef_data = asdict(ef)
        ef_data["score"] = asdict(new_score)
        store._facts[key] = _ef_from_dict_local(ef_data)

        decayed = store.apply_decay()
        assert key in decayed
        assert decayed[key] >= 10.0  # at least 10 days

    def test_decayed_confidence_lower(self, store):
        _ingest_one(store, confidence=0.8)
        key = _fact_key("H-ADX", "SBER", "2023", "TREND_UP")
        ef = store.get_fact(key)
        conf_before = ef.score.confidence

        # Inject stale timestamp
        from dataclasses import asdict
        from services.knowledge.evolution import FactScore, EnrichedFact
        old_ts = "2026-01-01T00:00:00+00:00"
        ef_data = asdict(ef)
        ef_data["score"]["last_seen"] = old_ts
        store._facts[key] = _ef_from_dict_local(ef_data)

        store.apply_decay()
        ef_after = store.get_fact(key)
        assert ef_after.score.confidence < conf_before


def _ef_from_dict_local(d: dict):
    """Local helper matching evolution._ef_from_dict for test use."""
    from services.knowledge.evolution import FactScore, EnrichedFact
    score = FactScore(**d["score"])
    d2 = dict(d)
    d2["score"] = score
    return EnrichedFact(**d2)


# ─────────────────────────────────────────────────────────────────────────────
# TestCLIReport
# ─────────────────────────────────────────────────────────────────────────────

class TestCLIReport:
    def test_report_cli_runs(self, tmp_path):
        """--report completes without error on an empty store."""
        from scripts.knowledge_evolution import main
        rc = main(["--report", "--store-dir", str(tmp_path / "evo")])
        assert rc == 0

    def test_report_cli_shows_version(self, tmp_path, capsys):
        store = KnowledgeStore(tmp_path / "evo")
        _ingest_one(store)
        from scripts.knowledge_evolution import main
        main(["--report", "--store-dir", str(tmp_path / "evo")])
        out = capsys.readouterr().out
        assert "v1" in out or "1" in out

    def test_status_cli(self, tmp_path, capsys):
        store = KnowledgeStore(tmp_path / "evo")
        _ingest_one(store)
        from scripts.knowledge_evolution import main
        rc = main(["--status", "--store-dir", str(tmp_path / "evo")])
        assert rc == 0
        out = capsys.readouterr().out
        assert "facts" in out.lower()

    def test_decay_cli(self, tmp_path, capsys):
        store = KnowledgeStore(tmp_path / "evo")
        _ingest_one(store)
        from scripts.knowledge_evolution import main
        rc = main(["--decay", "--store-dir", str(tmp_path / "evo")])
        assert rc == 0


# ─────────────────────────────────────────────────────────────────────────────
# TestCLIDiff
# ─────────────────────────────────────────────────────────────────────────────

class TestCLIDiff:
    def test_diff_cli_two_versions(self, tmp_path, capsys):
        store = KnowledgeStore(tmp_path / "evo")
        _ingest_one(store)            # v1
        _ingest_one(store, instr="GAZP")  # v2
        from scripts.knowledge_evolution import main
        rc = main(["--diff", "v1", "v2", "--store-dir", str(tmp_path / "evo")])
        assert rc == 0
        out = capsys.readouterr().out
        assert "v1" in out and "v2" in out

    def test_diff_cli_integer_versions(self, tmp_path, capsys):
        store = KnowledgeStore(tmp_path / "evo")
        _ingest_one(store)
        _ingest_one(store)
        from scripts.knowledge_evolution import main
        rc = main(["--diff", "1", "2", "--store-dir", str(tmp_path / "evo")])
        assert rc == 0

    def test_diff_cli_missing_version_exits(self, tmp_path):
        store = KnowledgeStore(tmp_path / "evo")
        _ingest_one(store)
        from scripts.knowledge_evolution import main
        with pytest.raises(SystemExit) as exc:
            main(["--diff", "99", "100", "--store-dir", str(tmp_path / "evo")])
        assert exc.value.code != 0

    def test_diff_shows_added_facts(self, tmp_path, capsys):
        store = KnowledgeStore(tmp_path / "evo")
        _ingest_one(store, instr="SBER")         # v1
        _ingest_one(store, instr="LKOH")         # v2
        from scripts.knowledge_evolution import main
        main(["--diff", "v1", "v2", "--store-dir", str(tmp_path / "evo")])
        out = capsys.readouterr().out
        assert "LKOH" in out


# ─────────────────────────────────────────────────────────────────────────────
# TestNoGitOps
# ─────────────────────────────────────────────────────────────────────────────

class TestNoGitOps:
    def _read_source(self, rel_path: str) -> str:
        return (_ROOT / rel_path).read_text(encoding="utf-8")

    def test_no_git_commit_in_evolution(self):
        src = self._read_source("services/knowledge/evolution.py")
        assert not re.search(r"subprocess\.\w+.*git\s+commit", src)

    def test_no_git_push_in_evolution(self):
        src = self._read_source("services/knowledge/evolution.py")
        assert not re.search(r"subprocess\.\w+.*git\s+push", src)

    def test_no_git_add_in_cli(self):
        src = self._read_source("scripts/knowledge_evolution.py")
        assert not re.search(r"subprocess\.\w+.*git\s+add", src)

    def test_no_live_trading_flag(self):
        src = self._read_source("services/knowledge/evolution.py")
        assert "MOEX_ENABLE_LIVE_TRADING" not in src
        assert "T_INVEST_EXECUTE" not in src

    def test_no_research_service_import(self):
        src = self._read_source("services/knowledge/evolution.py")
        assert "services.research" not in src
        assert "from services.research" not in src
