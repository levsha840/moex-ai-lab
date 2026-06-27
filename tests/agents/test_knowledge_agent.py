"""Tests for KnowledgeAgent — Layer 3 KNOWLEDGE Agent.

All tests use FixtureKnowledgeSource — no file I/O, no network.
Covers: protocol compliance, fact extraction, connection graph,
pattern discovery, contradiction detection, recommendations,
missing data, persistence, and determinism.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from agents.analysis.regime import FixtureRegimeSource  # structural reference, not used here
from agents.knowledge.agent import (
    FixtureKnowledgeSource,
    KnowledgeAgent,
    _OUTPERFORMANCE_THRESHOLD,
    _STRONG_THRESHOLD,
    _UNDERPERFORMANCE_THRESHOLD,
    _WEAK_THRESHOLD,
    _build_connections,
    _detect_contradictions,
    _facts_from_kb_entry,
    _facts_from_report,
    _discover_patterns,
    _make_recommendations,
)
from agents.models import (
    AgentResult,
    KnowledgeConnection,
    KnowledgeFact,
    KnowledgePattern,
    KnowledgeSnapshot,
)


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------

def _report(
    report_id: str = "h13_sber_2023",
    hypothesis_id: str = "H-13",
    instrument: str = "SBER",
    period: str = "2023",
    pass_rate: float = 0.239,
    passed: bool = False,
    confidence: float = 0.85,
    regime_label: str = "TREND_UP",
    source_ref: str = "reports/h13.json",
    features: list[str] | None = None,
) -> dict:
    r: dict = {
        "report_id": report_id,
        "hypothesis_id": hypothesis_id,
        "instrument": instrument,
        "period": period,
        "pass_rate": pass_rate,
        "passed": passed,
        "confidence": confidence,
        "regime_label": regime_label,
        "source_ref": source_ref,
    }
    if features is not None:
        r["features"] = features
    return r


def _kb_entry(
    entry_id: str = "kb_001",
    hypothesis_id: str = "H-13",
    finding: str = "ADX threshold <= 25 has zero effect",
    confidence: float = 0.9,
    source_ref: str = "knowledge_base/entry_001.json",
) -> dict:
    return {
        "entry_id": entry_id,
        "hypothesis_id": hypothesis_id,
        "finding": finding,
        "confidence": confidence,
        "source_ref": source_ref,
    }


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


# Three failing reports for the same hypothesis in the same regime → pattern
_THREE_H13_FAIL_TREND_UP = [
    _report("r1", pass_rate=0.2, passed=False, regime_label="TREND_UP"),
    _report("r2", pass_rate=0.15, passed=False, regime_label="TREND_UP"),
    _report("r3", pass_rate=0.3, passed=False, regime_label="TREND_UP"),
]

# Mixed results for same conditions → contradiction
_CONTRADICTION_REPORTS = [
    _report("r1", pass_rate=0.85, passed=True,  regime_label="RANGE", confidence=0.9),
    _report("r2", pass_rate=0.15, passed=False, regime_label="RANGE", confidence=0.9),
]

# High-performing hypothesis across two data points
_OUTPERFORM_REPORTS = [
    _report("o1", hypothesis_id="H-07", pass_rate=0.9, passed=True, confidence=0.8),
    _report("o2", hypothesis_id="H-07", pass_rate=0.85, passed=True, confidence=0.8),
]

# Low-performing hypothesis across two data points
_UNDERPERFORM_REPORTS = [
    _report("u1", hypothesis_id="H-21", pass_rate=0.2, passed=False, confidence=0.7),
    _report("u2", hypothesis_id="H-21", pass_rate=0.25, passed=False, confidence=0.7),
]


# ---------------------------------------------------------------------------
# FixtureKnowledgeSource
# ---------------------------------------------------------------------------

class TestFixtureKnowledgeSource:
    def test_load_reports_returns_data(self) -> None:
        src = FixtureKnowledgeSource([_report()])
        assert len(src.load_reports("any")) == 1

    def test_load_reports_period_arg_ignored(self) -> None:
        src = FixtureKnowledgeSource([_report(), _report()])
        assert len(src.load_reports("campaign_X")) == 2

    def test_load_kb_entries_returns_data(self) -> None:
        src = FixtureKnowledgeSource([], kb_entries=[_kb_entry()])
        assert len(src.load_kb_entries("any")) == 1

    def test_load_kb_entries_default_empty(self) -> None:
        src = FixtureKnowledgeSource([_report()])
        assert src.load_kb_entries("any") == []

    def test_does_not_mutate_source(self) -> None:
        src = FixtureKnowledgeSource([_report()])
        fetched = src.load_reports("any")
        fetched.clear()
        assert len(src.load_reports("any")) == 1


# ---------------------------------------------------------------------------
# KnowledgeAgent protocol compliance
# ---------------------------------------------------------------------------

class TestKnowledgeAgentProtocol:
    def test_agent_id(self, tmp_path: Path) -> None:
        assert KnowledgeAgent(tmp_path).agent_id == "knowledge-agent"

    def test_agent_type_is_knowledge(self, tmp_path: Path) -> None:
        assert KnowledgeAgent(tmp_path).agent_type == "KNOWLEDGE"

    def test_version_is_string(self, tmp_path: Path) -> None:
        assert isinstance(KnowledgeAgent(tmp_path).version, str)

    def test_run_is_callable(self, tmp_path: Path) -> None:
        assert callable(KnowledgeAgent(tmp_path).run)


# ---------------------------------------------------------------------------
# _facts_from_report
# ---------------------------------------------------------------------------

class TestFactsFromReport:
    def test_returns_one_fact(self) -> None:
        facts = _facts_from_report(_report(), 0)
        assert len(facts) == 1

    def test_fact_metric_is_pass_rate(self) -> None:
        [f] = _facts_from_report(_report(), 0)
        assert f.metric == "pass_rate"

    def test_fact_value_is_pass_rate(self) -> None:
        [f] = _facts_from_report(_report(pass_rate=0.239), 0)
        assert f.value == pytest.approx(0.239)

    def test_fact_regime_extracted(self) -> None:
        [f] = _facts_from_report(_report(regime_label="HIGH_VOL"), 0)
        assert f.regime == "HIGH_VOL"

    def test_no_regime_gives_empty_string(self) -> None:
        r = _report()
        r.pop("regime_label", None)
        [f] = _facts_from_report(r, 0)
        assert f.regime == ""

    def test_features_become_tags(self) -> None:
        [f] = _facts_from_report(_report(features=["ADX", "RSI"]), 0)
        assert "ADX" in f.tags
        assert "RSI" in f.tags

    def test_passed_bool_preserved(self) -> None:
        [f_false] = _facts_from_report(_report(passed=False), 0)
        [f_true] = _facts_from_report(_report(passed=True), 1)
        assert f_false.passed is False
        assert f_true.passed is True

    def test_fact_id_contains_index(self) -> None:
        [f0] = _facts_from_report(_report(), 0)
        [f5] = _facts_from_report(_report(), 5)
        assert "0000" in f0.fact_id
        assert "0005" in f5.fact_id

    def test_source_type_is_research_report(self) -> None:
        [f] = _facts_from_report(_report(), 0)
        assert f.source_type == "research_report"


# ---------------------------------------------------------------------------
# _facts_from_kb_entry
# ---------------------------------------------------------------------------

class TestFactsFromKbEntry:
    def test_returns_one_fact(self) -> None:
        assert len(_facts_from_kb_entry(_kb_entry(), 0)) == 1

    def test_source_type_is_knowledge_base(self) -> None:
        [f] = _facts_from_kb_entry(_kb_entry(), 0)
        assert f.source_type == "knowledge_base"

    def test_hypothesis_id_extracted(self) -> None:
        [f] = _facts_from_kb_entry(_kb_entry(hypothesis_id="H-07"), 0)
        assert f.hypothesis_id == "H-07"

    def test_metric_is_kb_finding(self) -> None:
        [f] = _facts_from_kb_entry(_kb_entry(), 0)
        assert f.metric == "kb_finding"

    def test_passed_is_none(self) -> None:
        [f] = _facts_from_kb_entry(_kb_entry(), 0)
        assert f.passed is None

    def test_confidence_extracted(self) -> None:
        [f] = _facts_from_kb_entry(_kb_entry(confidence=0.9), 0)
        assert f.confidence == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# _build_connections
# ---------------------------------------------------------------------------

class TestBuildConnections:
    def _facts(self, reports: list[dict]) -> list[KnowledgeFact]:
        facts: list[KnowledgeFact] = []
        for i, r in enumerate(reports):
            facts.extend(_facts_from_report(r, i))
        return facts

    def test_positive_when_all_pass(self) -> None:
        reports = [
            _report("r1", passed=True, regime_label="RANGE"),
            _report("r2", passed=True, regime_label="RANGE"),
        ]
        conns = _build_connections(self._facts(reports))
        assert len(conns) == 1
        assert conns[0].relation == "positive"

    def test_negative_when_all_fail(self) -> None:
        conns = _build_connections(self._facts(_THREE_H13_FAIL_TREND_UP))
        assert len(conns) == 1
        assert conns[0].relation == "negative"

    def test_neutral_when_exactly_split(self) -> None:
        # 1 pass + 1 fail → pass_fraction = 0.5 → neutral
        reports = [
            _report("r1", passed=True,  regime_label="RANGE"),
            _report("r2", passed=False, regime_label="RANGE"),
        ]
        conns = _build_connections(self._facts(reports))
        assert conns[0].relation == "neutral"

    def test_strength_proportional(self) -> None:
        # All fail: pass_fraction = 0 → strength = 1.0
        conns = _build_connections(self._facts(_THREE_H13_FAIL_TREND_UP))
        assert conns[0].strength == pytest.approx(1.0)

    def test_empty_when_no_regime(self) -> None:
        r = _report()
        r["regime_label"] = ""
        assert _build_connections(self._facts([r])) == []

    def test_separate_connections_per_regime(self) -> None:
        reports = [
            _report("r1", passed=False, regime_label="TREND_UP"),
            _report("r2", passed=True,  regime_label="RANGE"),
        ]
        conns = _build_connections(self._facts(reports))
        assert len(conns) == 2

    def test_support_count_matches_group_size(self) -> None:
        conns = _build_connections(self._facts(_THREE_H13_FAIL_TREND_UP))
        assert conns[0].support_count == 3

    def test_evidence_contains_fact_ids(self) -> None:
        conns = _build_connections(self._facts(_THREE_H13_FAIL_TREND_UP))
        assert len(conns[0].evidence) == 3
        for eid in conns[0].evidence:
            assert isinstance(eid, str)

    def test_entity_a_is_hypothesis(self) -> None:
        conns = _build_connections(self._facts([_report(hypothesis_id="H-07")]))
        assert conns[0].entity_a == "H-07"

    def test_entity_b_is_regime(self) -> None:
        conns = _build_connections(self._facts([_report(regime_label="HIGH_VOL")]))
        assert conns[0].entity_b == "HIGH_VOL"


# ---------------------------------------------------------------------------
# _discover_patterns
# ---------------------------------------------------------------------------

class TestDiscoverPatterns:
    def _facts(self, reports: list[dict]) -> list[KnowledgeFact]:
        result: list[KnowledgeFact] = []
        for i, r in enumerate(reports):
            result.extend(_facts_from_report(r, i))
        return result

    def test_negative_regime_pattern_from_three_fails(self) -> None:
        patterns = _discover_patterns(self._facts(_THREE_H13_FAIL_TREND_UP))
        rg = [p for p in patterns if p.pattern_type == "regime_hypothesis"]
        assert len(rg) >= 1
        assert "FAILS" in rg[0].description

    def test_positive_regime_pattern_from_passes(self) -> None:
        reports = [
            _report("r1", hypothesis_id="H-07", passed=True,  regime_label="RANGE"),
            _report("r2", hypothesis_id="H-07", passed=True,  regime_label="RANGE"),
        ]
        patterns = _discover_patterns(self._facts(reports))
        rg = [p for p in patterns if p.pattern_type == "regime_hypothesis"]
        assert any("PASSES" in p.description for p in rg)

    def test_no_pattern_from_single_fact(self) -> None:
        patterns = _discover_patterns(self._facts([_report()]))
        rg = [p for p in patterns if p.pattern_type == "regime_hypothesis"]
        assert rg == []

    def test_underperformance_pattern(self) -> None:
        patterns = _discover_patterns(self._facts(_UNDERPERFORM_REPORTS))
        up = [p for p in patterns if p.pattern_type == "underperformance"]
        assert len(up) == 1
        assert "underperforms" in up[0].description

    def test_outperformance_pattern(self) -> None:
        patterns = _discover_patterns(self._facts(_OUTPERFORM_REPORTS))
        op = [p for p in patterns if p.pattern_type == "outperformance"]
        assert len(op) == 1
        assert "outperforms" in op[0].description

    def test_pattern_confidence_in_range(self) -> None:
        for patterns in [
            _discover_patterns(self._facts(_THREE_H13_FAIL_TREND_UP)),
            _discover_patterns(self._facts(_UNDERPERFORM_REPORTS)),
            _discover_patterns(self._facts(_OUTPERFORM_REPORTS)),
        ]:
            for p in patterns:
                assert 0.0 <= p.confidence <= 1.0

    def test_pattern_ids_unique(self) -> None:
        reports = _THREE_H13_FAIL_TREND_UP + _UNDERPERFORM_REPORTS
        patterns = _discover_patterns(self._facts(reports))
        ids = [p.pattern_id for p in patterns]
        assert len(ids) == len(set(ids))

    def test_supporting_facts_non_empty_when_pattern_found(self) -> None:
        patterns = _discover_patterns(self._facts(_THREE_H13_FAIL_TREND_UP))
        rg = [p for p in patterns if p.pattern_type == "regime_hypothesis"]
        assert len(rg[0].supporting_facts) > 0

    def test_mixed_pass_fail_no_regime_pattern(self) -> None:
        # 1 pass + 1 fail in same regime → mixed, no consistent pattern
        reports = [
            _report("r1", passed=True,  regime_label="TREND_UP"),
            _report("r2", passed=False, regime_label="TREND_UP"),
        ]
        patterns = _discover_patterns(self._facts(reports))
        rg = [p for p in patterns if p.pattern_type == "regime_hypothesis"]
        assert rg == []


# ---------------------------------------------------------------------------
# _detect_contradictions
# ---------------------------------------------------------------------------

class TestDetectContradictions:
    def _facts(self, reports: list[dict]) -> list[KnowledgeFact]:
        result: list[KnowledgeFact] = []
        for i, r in enumerate(reports):
            result.extend(_facts_from_report(r, i))
        return result

    def test_same_conditions_mixed_is_contradiction(self) -> None:
        contras = _detect_contradictions(self._facts(_CONTRADICTION_REPORTS))
        assert len(contras) == 1

    def test_no_contradiction_when_all_pass(self) -> None:
        reports = [
            _report("r1", passed=True, regime_label="RANGE"),
            _report("r2", passed=True, regime_label="RANGE"),
        ]
        assert _detect_contradictions(self._facts(reports)) == []

    def test_no_contradiction_when_all_fail(self) -> None:
        assert _detect_contradictions(self._facts(_THREE_H13_FAIL_TREND_UP)) == []

    def test_different_regimes_not_contradiction(self) -> None:
        reports = [
            _report("r1", passed=True,  regime_label="RANGE"),
            _report("r2", passed=False, regime_label="TREND_UP"),
        ]
        assert _detect_contradictions(self._facts(reports)) == []

    def test_contradiction_message_contains_hypothesis(self) -> None:
        contras = _detect_contradictions(self._facts(_CONTRADICTION_REPORTS))
        assert "H-13" in contras[0]

    def test_empty_when_no_hypothesis(self) -> None:
        r = _report()
        r["hypothesis_id"] = ""
        assert _detect_contradictions(self._facts([r])) == []

    def test_output_is_sorted(self) -> None:
        # Multiple contradictions should be deterministically sorted
        reports = [
            _report("r1", hypothesis_id="H-21", passed=True,  regime_label="RANGE"),
            _report("r2", hypothesis_id="H-21", passed=False, regime_label="RANGE"),
            _report("r3", hypothesis_id="H-07", passed=True,  regime_label="HIGH_VOL"),
            _report("r4", hypothesis_id="H-07", passed=False, regime_label="HIGH_VOL"),
        ]
        contras = _detect_contradictions(self._facts(reports))
        assert contras == sorted(contras)


# ---------------------------------------------------------------------------
# _make_recommendations
# ---------------------------------------------------------------------------

class TestMakeRecommendations:
    def _patterns_negative(self) -> list[KnowledgePattern]:
        facts = [
            _facts_from_report(r, i)[0]
            for i, r in enumerate(_THREE_H13_FAIL_TREND_UP)
        ]
        return _discover_patterns(facts)

    def test_negative_pattern_generates_avoid_rec(self) -> None:
        recs = _make_recommendations(self._patterns_negative(), [])
        assert any("Avoid" in r for r in recs)

    def test_outperformance_pattern_generates_expand_rec(self) -> None:
        facts = [_facts_from_report(r, i)[0] for i, r in enumerate(_OUTPERFORM_REPORTS)]
        patterns = _discover_patterns(facts)
        recs = _make_recommendations(patterns, [])
        assert any("Expand" in r for r in recs)

    def test_contradiction_generates_resolve_rec(self) -> None:
        recs = _make_recommendations([], ["Contradiction: H-13 shows conflict"])
        assert any("Resolve" in r for r in recs)

    def test_empty_input_empty_output(self) -> None:
        assert _make_recommendations([], []) == []

    def test_output_deduplicated(self) -> None:
        # Identical patterns → single recommendation each
        recs = _make_recommendations(
            self._patterns_negative() + self._patterns_negative(), []
        )
        assert len(recs) == len(set(recs))


# ---------------------------------------------------------------------------
# KnowledgeAgent — full fixture run
# ---------------------------------------------------------------------------

class TestKnowledgeAgentRun:
    def _run(
        self,
        tmp_path: Path,
        reports: list[dict] | None = None,
        kb: list[dict] | None = None,
    ) -> AgentResult:
        src = FixtureKnowledgeSource(
            reports if reports is not None else _THREE_H13_FAIL_TREND_UP,
            kb_entries=kb or [],
        )
        agent = KnowledgeAgent(tmp_path, source=src)
        return agent.run("campaign_001", _clock=_fixed_clock)

    def test_returns_agent_result(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path), AgentResult)

    def test_agent_id(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_id == "knowledge-agent"

    def test_agent_type_knowledge(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_type == "KNOWLEDGE"

    def test_output_is_knowledge_snapshot(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path).output, KnowledgeSnapshot)

    def test_created_at_uses_clock(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).created_at == "2026-06-27T12:00:00"

    def test_snapshot_id_format(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.snapshot_id == "knowledge_campaign_001"

    def test_campaign_id_in_snapshot(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.campaign_id == "campaign_001"

    def test_facts_not_empty(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert len(snap.facts) > 0

    def test_facts_count_equals_reports(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert len(snap.facts) == 3

    def test_connections_built(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert len(snap.connections) >= 1

    def test_patterns_found(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert len(snap.patterns) >= 1

    def test_strong_facts_subset_of_all_facts(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        all_ids = {f.fact_id for f in snap.facts}
        assert all(fid in all_ids for fid in snap.strong_facts)

    def test_weak_facts_subset_of_all_facts(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        all_ids = {f.fact_id for f in snap.facts}
        assert all(fid in all_ids for fid in snap.weak_facts)

    def test_kb_entries_add_facts(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(
            tmp_path,
            reports=[_report()],
            kb=[_kb_entry()],
        ).output  # type: ignore[assignment]
        sources = {f.source_type for f in snap.facts}
        assert "knowledge_base" in sources

    def test_contradiction_detected(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(
            tmp_path, reports=_CONTRADICTION_REPORTS
        ).output  # type: ignore[assignment]
        assert len(snap.contradictions) >= 1

    def test_recommendations_generated_for_negative_pattern(self, tmp_path: Path) -> None:
        snap: KnowledgeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert len(snap.recommendations) >= 1

    def test_confidence_positive(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert result.confidence.value > 0.0

    def test_evidence_refs_present(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert len(result.evidence) >= 1

    def test_evidence_source_contains_campaign(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        sources = {e.source for e in result.evidence}
        assert any("campaign" in s for s in sources)


# ---------------------------------------------------------------------------
# Missing / edge-case data
# ---------------------------------------------------------------------------

class TestMissingDataHandling:
    def _agent(self, tmp_path: Path, reports: list[dict], kb: list[dict] | None = None) -> KnowledgeSnapshot:
        src = FixtureKnowledgeSource(reports, kb_entries=kb or [])
        result = KnowledgeAgent(tmp_path, source=src).run("camp", _clock=_fixed_clock)
        return result.output  # type: ignore[return-value]

    def test_empty_reports_empty_facts(self, tmp_path: Path) -> None:
        snap = self._agent(tmp_path, [])
        assert snap.facts == ()

    def test_empty_reports_empty_patterns(self, tmp_path: Path) -> None:
        snap = self._agent(tmp_path, [])
        assert snap.patterns == ()

    def test_empty_reports_zero_confidence(self, tmp_path: Path) -> None:
        snap = self._agent(tmp_path, [])
        assert snap.confidence.value == 0.0

    def test_single_report_no_regime_patterns(self, tmp_path: Path) -> None:
        snap = self._agent(tmp_path, [_report()])
        rg = [p for p in snap.patterns if p.pattern_type == "regime_hypothesis"]
        assert rg == []

    def test_only_kb_entries_yields_facts(self, tmp_path: Path) -> None:
        snap = self._agent(tmp_path, [], kb=[_kb_entry(), _kb_entry("kb_002", "H-07")])
        assert len(snap.facts) == 2

    def test_report_without_regime_label_gives_no_connection(self, tmp_path: Path) -> None:
        r = _report()
        r.pop("regime_label", None)
        snap = self._agent(tmp_path, [r, r])
        assert snap.connections == ()

    def test_no_contradiction_when_no_conflicting_passed(self, tmp_path: Path) -> None:
        snap = self._agent(tmp_path, _THREE_H13_FAIL_TREND_UP)
        assert snap.contradictions == ()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def _paths(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        src = FixtureKnowledgeSource(_THREE_H13_FAIL_TREND_UP)
        KnowledgeAgent(tmp_path, source=src).run("camp_001", _clock=_fixed_clock)
        return (
            tmp_path / "knowledge" / "snapshots" / "camp_001.json",
            tmp_path / "knowledge" / "graph" / "camp_001.json",
            tmp_path / "knowledge" / "patterns" / "camp_001.json",
        )

    def test_snapshot_json_created(self, tmp_path: Path) -> None:
        snap_path, _, _ = self._paths(tmp_path)
        assert snap_path.exists()

    def test_graph_json_created(self, tmp_path: Path) -> None:
        _, graph_path, _ = self._paths(tmp_path)
        assert graph_path.exists()

    def test_patterns_json_created(self, tmp_path: Path) -> None:
        _, _, pat_path = self._paths(tmp_path)
        assert pat_path.exists()

    def test_snapshot_json_contains_campaign_id(self, tmp_path: Path) -> None:
        snap_path, _, _ = self._paths(tmp_path)
        with open(snap_path) as f:
            data = json.load(f)
        assert data["campaign_id"] == "camp_001"

    def test_snapshot_json_contains_facts(self, tmp_path: Path) -> None:
        snap_path, _, _ = self._paths(tmp_path)
        with open(snap_path) as f:
            data = json.load(f)
        assert isinstance(data["facts"], list)
        assert len(data["facts"]) == 3

    def test_graph_json_contains_connections(self, tmp_path: Path) -> None:
        _, graph_path, _ = self._paths(tmp_path)
        with open(graph_path) as f:
            data = json.load(f)
        assert "connections" in data

    def test_patterns_json_contains_patterns(self, tmp_path: Path) -> None:
        _, _, pat_path = self._paths(tmp_path)
        with open(pat_path) as f:
            data = json.load(f)
        assert "patterns" in data

    def test_second_run_overwrites(self, tmp_path: Path) -> None:
        src = FixtureKnowledgeSource(_THREE_H13_FAIL_TREND_UP)
        agent = KnowledgeAgent(tmp_path, source=src)
        agent.run("camp_001", _clock=_fixed_clock)
        agent.run("camp_001", _clock=_fixed_clock)  # no error
        path = tmp_path / "knowledge" / "snapshots" / "camp_001.json"
        assert path.exists()

    def test_files_in_knowledge_subdir(self, tmp_path: Path) -> None:
        snap_path, graph_path, pat_path = self._paths(tmp_path)
        for p in (snap_path, graph_path, pat_path):
            assert "knowledge" in str(p)
            assert str(tmp_path.resolve()) in str(p.resolve())


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def _snap(self, tmp_path: Path, reports: list[dict]) -> KnowledgeSnapshot:
        src = FixtureKnowledgeSource(reports)
        return KnowledgeAgent(tmp_path, source=src).run(
            "det", _clock=_fixed_clock
        ).output  # type: ignore[return-value]

    def test_same_input_same_fact_ids(self, tmp_path: Path) -> None:
        s1 = self._snap(tmp_path, _THREE_H13_FAIL_TREND_UP)
        s2 = self._snap(tmp_path, _THREE_H13_FAIL_TREND_UP)
        assert [f.fact_id for f in s1.facts] == [f.fact_id for f in s2.facts]

    def test_same_input_same_patterns(self, tmp_path: Path) -> None:
        s1 = self._snap(tmp_path, _THREE_H13_FAIL_TREND_UP)
        s2 = self._snap(tmp_path, _THREE_H13_FAIL_TREND_UP)
        assert [p.pattern_id for p in s1.patterns] == [p.pattern_id for p in s2.patterns]

    def test_same_input_same_connections(self, tmp_path: Path) -> None:
        s1 = self._snap(tmp_path, _THREE_H13_FAIL_TREND_UP)
        s2 = self._snap(tmp_path, _THREE_H13_FAIL_TREND_UP)
        assert [c.connection_id for c in s1.connections] == [c.connection_id for c in s2.connections]

    def test_different_campaign_ids_different_snapshot_ids(self, tmp_path: Path) -> None:
        src = FixtureKnowledgeSource(_THREE_H13_FAIL_TREND_UP)
        agent = KnowledgeAgent(tmp_path, source=src)
        s1: KnowledgeSnapshot = agent.run("camp_A", _clock=_fixed_clock).output  # type: ignore[assignment]
        s2: KnowledgeSnapshot = agent.run("camp_B", _clock=_fixed_clock).output  # type: ignore[assignment]
        assert s1.snapshot_id != s2.snapshot_id

    def test_created_at_matches_clock(self, tmp_path: Path) -> None:
        src = FixtureKnowledgeSource([_report()])
        result = KnowledgeAgent(tmp_path, source=src).run(
            "x", _clock=lambda: datetime(2025, 1, 1, 0, 0, 0)
        )
        assert result.created_at == "2025-01-01T00:00:00"
