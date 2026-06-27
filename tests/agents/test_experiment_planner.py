"""Tests for ExperimentPlanner — Layer 3 RESEARCH Agent.

All tests are pure Python — no network, no real file I/O beyond tmp_path.
Covers: protocol compliance, plan generation from all trigger types,
overfitting risk, confidence from evidence count, stop conditions,
missing data, persistence, and determinism.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from agents.models import (
    AgentResult,
    ConfidenceScore,
    EvidenceRef,
    ExperimentPlan,
    ExperimentTask,
    KnowledgeConnection,
    KnowledgeFact,
    KnowledgePattern,
    KnowledgeSnapshot,
    OverfittingRisk,
    StopCondition,
)
from agents.research.planner import (
    ExperimentPlanner,
    _evidence_confidence,
    _instrument_from_dataset,
    _make_tasks,
    _overfitting_risk,
    _plan_from_contradiction,
    _plan_from_negative_connection,
    _plan_from_outperformance,
    _plan_from_underperformance,
    _plans_from_snapshot,
    _default_stop_conditions,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_DATASETS = ["sber_1h_2023_main", "gazp_1h_2023_main", "lkoh_1h_2023_main"]


def _evidence() -> EvidenceRef:
    return EvidenceRef(source="test", reference="test", timestamp="2026-06-27T12:00:00")


def _conf(v: float = 0.7) -> ConfidenceScore:
    return ConfidenceScore(value=v, reason="test")


def _underperform_pattern(
    hyp_id: str = "H-13",
    occurrence_count: int = 3,
    confidence: float = 0.6,
) -> KnowledgePattern:
    return KnowledgePattern(
        pattern_id="pat_0001",
        description=f"{hyp_id} consistently underperforms (avg pass_rate=0.22)",
        pattern_type="underperformance",
        entities=(hyp_id,),
        occurrence_count=occurrence_count,
        confidence=confidence,
        supporting_facts=tuple(f"f{i}" for i in range(occurrence_count)),
        contradicting_facts=(),
    )


def _outperform_pattern(
    hyp_id: str = "H-07",
    occurrence_count: int = 4,
) -> KnowledgePattern:
    return KnowledgePattern(
        pattern_id="pat_0002",
        description=f"{hyp_id} consistently outperforms (avg pass_rate=0.85)",
        pattern_type="outperformance",
        entities=(hyp_id,),
        occurrence_count=occurrence_count,
        confidence=0.8,
        supporting_facts=tuple(f"f{i}" for i in range(occurrence_count)),
        contradicting_facts=(),
    )


def _negative_conn(
    hyp_id: str = "H-13",
    regime: str = "TREND_UP",
    support_count: int = 3,
) -> KnowledgeConnection:
    return KnowledgeConnection(
        connection_id=f"conn_{hyp_id.lower().replace('-','')}_{regime.lower()}",
        entity_a=hyp_id,
        entity_b=regime,
        relation="negative",
        strength=1.0,
        support_count=support_count,
        evidence=tuple(f"f{i}" for i in range(support_count)),
    )


def _snap(
    patterns: tuple[KnowledgePattern, ...] = (),
    connections: tuple[KnowledgeConnection, ...] = (),
    contradictions: tuple[str, ...] = (),
) -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        snapshot_id="knowledge_camp",
        campaign_id="camp",
        facts=(),
        connections=connections,
        patterns=patterns,
        strong_facts=(),
        weak_facts=(),
        contradictions=contradictions,
        recommendations=(),
        source_refs=(_evidence(),),
        confidence=_conf(0.7),
    )


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


# ---------------------------------------------------------------------------
# ExperimentPlanner protocol compliance
# ---------------------------------------------------------------------------

class TestExperimentPlannerProtocol:
    def test_agent_id(self, tmp_path: Path) -> None:
        assert ExperimentPlanner(tmp_path).agent_id == "experiment-planner"

    def test_agent_type_is_research(self, tmp_path: Path) -> None:
        assert ExperimentPlanner(tmp_path).agent_type == "RESEARCH"

    def test_version_is_string(self, tmp_path: Path) -> None:
        assert isinstance(ExperimentPlanner(tmp_path).version, str)

    def test_run_is_callable(self, tmp_path: Path) -> None:
        assert callable(ExperimentPlanner(tmp_path).run)


# ---------------------------------------------------------------------------
# _instrument_from_dataset
# ---------------------------------------------------------------------------

class TestInstrumentFromDataset:
    def test_sber_extracted(self) -> None:
        assert _instrument_from_dataset("sber_1h_2023_main") == "SBER"

    def test_gazp_extracted(self) -> None:
        assert _instrument_from_dataset("gazp_1h_2023_main") == "GAZP"

    def test_uppercase_result(self) -> None:
        assert _instrument_from_dataset("lkoh_1h_2022_full") == "LKOH"

    def test_empty_string_gives_unknown(self) -> None:
        assert _instrument_from_dataset("") == "UNKNOWN"


# ---------------------------------------------------------------------------
# _evidence_confidence
# ---------------------------------------------------------------------------

class TestEvidenceConfidence:
    def test_below_3_gives_low(self) -> None:
        assert _evidence_confidence(1) == pytest.approx(0.30)
        assert _evidence_confidence(2) == pytest.approx(0.30)

    def test_exactly_3_gives_medium(self) -> None:
        assert _evidence_confidence(3) == pytest.approx(0.60)

    def test_below_5_gives_medium(self) -> None:
        assert _evidence_confidence(4) == pytest.approx(0.60)

    def test_5_or_more_gives_high(self) -> None:
        assert _evidence_confidence(5) == pytest.approx(0.80)
        assert _evidence_confidence(20) == pytest.approx(0.80)


# ---------------------------------------------------------------------------
# _overfitting_risk
# ---------------------------------------------------------------------------

class TestOverfittingRiskFunction:
    def test_no_params_is_low(self) -> None:
        r = _overfitting_risk(())
        assert r.level == "low"
        assert r.parameter_count == 0

    def test_one_param_is_medium(self) -> None:
        r = _overfitting_risk((("adx_threshold", "30"),))
        assert r.level == "medium"
        assert r.parameter_count == 1

    def test_two_params_is_high(self) -> None:
        r = _overfitting_risk((("adx_threshold", "30"), ("lookback", "14")))
        assert r.level == "high"
        assert r.parameter_count == 2

    def test_high_risk_reasons_mention_count(self) -> None:
        r = _overfitting_risk((("a", "1"), ("b", "2"), ("c", "3")))
        assert any("3" in reason for reason in r.reasons)

    def test_reasons_is_tuple(self) -> None:
        r = _overfitting_risk(())
        assert isinstance(r.reasons, tuple)


# ---------------------------------------------------------------------------
# _default_stop_conditions
# ---------------------------------------------------------------------------

class TestDefaultStopConditions:
    def test_regime_filter_has_two_conditions(self) -> None:
        sc = _default_stop_conditions("regime_filter")
        assert len(sc) == 2

    def test_contradiction_has_max_5_runs(self) -> None:
        sc = _default_stop_conditions("contradiction_replication")
        assert len(sc) == 1
        assert sc[0].value == pytest.approx(5.0)

    def test_regime_exploration_has_max_experiments(self) -> None:
        sc = _default_stop_conditions("regime_exploration")
        types = {c.condition_type for c in sc}
        assert "max_experiments" in types

    def test_expansion_has_stop_condition(self) -> None:
        sc = _default_stop_conditions("expansion")
        assert len(sc) >= 1

    def test_all_conditions_are_stop_condition_type(self) -> None:
        for plan_type in ("regime_filter", "regime_exploration", "contradiction_replication", "expansion"):
            for sc in _default_stop_conditions(plan_type):
                assert isinstance(sc, StopCondition)


# ---------------------------------------------------------------------------
# Plan from underperformance pattern
# ---------------------------------------------------------------------------

class TestPlanFromUnderperformance:
    def _plan(self, occurrence_count: int = 3) -> ExperimentPlan:
        return _plan_from_underperformance(
            _underperform_pattern(occurrence_count=occurrence_count),
            _DATASETS, 1,
        )

    def test_plan_type_regime_exploration(self) -> None:
        assert self._plan().plan_type == "regime_exploration"

    def test_hypothesis_id_extracted(self) -> None:
        assert self._plan().hypothesis_id == "H-13"

    def test_priority_is_medium(self) -> None:
        assert self._plan().priority == "medium"

    def test_regime_filter_set(self) -> None:
        assert self._plan().regime_filter != ""

    def test_no_parameter_changes(self) -> None:
        assert self._plan().parameters == ()

    def test_overfitting_risk_is_low(self) -> None:
        assert self._plan().overfitting_risk.level == "low"

    def test_stop_conditions_present(self) -> None:
        assert len(self._plan().stop_conditions) >= 1

    def test_expected_evidence_not_empty(self) -> None:
        assert len(self._plan().expected_evidence) >= 1

    def test_rationale_mentions_pattern(self) -> None:
        assert "underperforms" in self._plan().rationale.lower()

    def test_low_evidence_gives_low_confidence(self) -> None:
        plan = self._plan(occurrence_count=2)
        assert plan.confidence == pytest.approx(0.30)

    def test_medium_evidence_gives_medium_confidence(self) -> None:
        plan = self._plan(occurrence_count=4)
        assert plan.confidence == pytest.approx(0.60)

    def test_tasks_generated_for_datasets(self) -> None:
        assert len(self._plan().tasks) == len(_DATASETS)

    def test_source_pattern_id_set(self) -> None:
        assert self._plan().source_pattern_id == "pat_0001"


# ---------------------------------------------------------------------------
# Plan from negative connection
# ---------------------------------------------------------------------------

class TestPlanFromNegativeConnection:
    def _plan(self, support_count: int = 3) -> ExperimentPlan:
        return _plan_from_negative_connection(
            _negative_conn(support_count=support_count),
            _DATASETS, 1,
        )

    def test_plan_type_regime_filter(self) -> None:
        assert self._plan().plan_type == "regime_filter"

    def test_hypothesis_id_from_entity_a(self) -> None:
        assert self._plan().hypothesis_id == "H-13"

    def test_priority_is_high(self) -> None:
        assert self._plan().priority == "high"

    def test_regime_filter_excludes_regime(self) -> None:
        assert "TREND_UP" in self._plan().regime_filter

    def test_no_parameter_changes(self) -> None:
        assert self._plan().parameters == ()

    def test_overfitting_risk_is_low(self) -> None:
        assert self._plan().overfitting_risk.level == "low"

    def test_stop_conditions_include_min_pass_rate(self) -> None:
        types = {sc.condition_type for sc in self._plan().stop_conditions}
        assert "min_pass_rate" in types

    def test_rationale_mentions_connection_strength(self) -> None:
        assert "strength" in self._plan().rationale.lower()

    def test_rationale_mentions_hypothesis_refinement(self) -> None:
        assert "refinement" in self._plan().rationale.lower()

    def test_low_evidence_confidence(self) -> None:
        assert self._plan(support_count=2).confidence == pytest.approx(0.30)

    def test_sufficient_evidence_confidence(self) -> None:
        assert self._plan(support_count=5).confidence == pytest.approx(0.80)

    def test_tasks_reference_hypothesis(self) -> None:
        tasks = self._plan().tasks
        assert all(t.hypothesis_id == "H-13" for t in tasks)

    def test_tasks_carry_regime_filter(self) -> None:
        tasks = self._plan().tasks
        assert all("TREND_UP" in t.regime_filter for t in tasks)


# ---------------------------------------------------------------------------
# Plan from contradiction
# ---------------------------------------------------------------------------

class TestPlanFromContradiction:
    _CONTRA = "Contradiction: H-13 in RANGE for SBER shows conflicting results"

    def _plan(self) -> ExperimentPlan:
        return _plan_from_contradiction(self._CONTRA, _DATASETS, 1)

    def test_plan_type_contradiction_replication(self) -> None:
        assert self._plan().plan_type == "contradiction_replication"

    def test_priority_is_critical(self) -> None:
        assert self._plan().priority == "critical"

    def test_confidence_is_low(self) -> None:
        assert self._plan().confidence == pytest.approx(0.30)

    def test_no_regime_filter(self) -> None:
        assert self._plan().regime_filter == ""

    def test_no_parameter_changes(self) -> None:
        assert self._plan().parameters == ()

    def test_overfitting_risk_is_low(self) -> None:
        assert self._plan().overfitting_risk.level == "low"

    def test_stop_condition_max_5(self) -> None:
        scs = self._plan().stop_conditions
        assert any(sc.value == pytest.approx(5.0) for sc in scs)

    def test_rationale_mentions_replication(self) -> None:
        assert "replication" in self._plan().rationale.lower()

    def test_hypothesis_id_extracted_from_string(self) -> None:
        assert self._plan().hypothesis_id == "H-13"


# ---------------------------------------------------------------------------
# Plan from outperformance
# ---------------------------------------------------------------------------

class TestPlanFromOutperformance:
    def _plan(self, occurrence_count: int = 4) -> ExperimentPlan:
        return _plan_from_outperformance(
            _outperform_pattern(occurrence_count=occurrence_count),
            _DATASETS, 1,
        )

    def test_plan_type_expansion(self) -> None:
        assert self._plan().plan_type == "expansion"

    def test_hypothesis_id_extracted(self) -> None:
        assert self._plan().hypothesis_id == "H-07"

    def test_priority_is_high(self) -> None:
        assert self._plan().priority == "high"

    def test_no_regime_filter(self) -> None:
        assert self._plan().regime_filter == ""

    def test_no_parameter_changes(self) -> None:
        assert self._plan().parameters == ()

    def test_overfitting_risk_is_low(self) -> None:
        assert self._plan().overfitting_risk.level == "low"

    def test_expected_evidence_mentions_pass_rate(self) -> None:
        assert any("pass_rate" in e or "0.7" in e for e in self._plan().expected_evidence)

    def test_datasets_included(self) -> None:
        assert len(self._plan().datasets) == len(_DATASETS)


# ---------------------------------------------------------------------------
# _plans_from_snapshot — integration of all rule triggers
# ---------------------------------------------------------------------------

class TestPlansFromSnapshot:
    def test_underperformance_generates_plan(self) -> None:
        snap = _snap(patterns=(_underperform_pattern(),))
        plans = _plans_from_snapshot(snap, _DATASETS)
        assert any(p.plan_type == "regime_exploration" for p in plans)

    def test_negative_connection_generates_plan(self) -> None:
        snap = _snap(connections=(_negative_conn(),))
        plans = _plans_from_snapshot(snap, _DATASETS)
        assert any(p.plan_type == "regime_filter" for p in plans)

    def test_contradiction_generates_plan(self) -> None:
        snap = _snap(contradictions=("Contradiction: H-13 shows conflict",))
        plans = _plans_from_snapshot(snap, _DATASETS)
        assert any(p.plan_type == "contradiction_replication" for p in plans)

    def test_outperformance_generates_plan(self) -> None:
        snap = _snap(patterns=(_outperform_pattern(),))
        plans = _plans_from_snapshot(snap, _DATASETS)
        assert any(p.plan_type == "expansion" for p in plans)

    def test_empty_snapshot_empty_plans(self) -> None:
        snap = _snap()
        assert _plans_from_snapshot(snap, _DATASETS) == []

    def test_multiple_triggers_multiple_plans(self) -> None:
        snap = _snap(
            patterns=(_underperform_pattern(), _outperform_pattern()),
            connections=(_negative_conn(),),
            contradictions=("Contradiction: H-13 conflict",),
        )
        plans = _plans_from_snapshot(snap, _DATASETS)
        # 1 underperform + 1 negative + 1 contradiction + 1 outperform = 4
        assert len(plans) == 4

    def test_plan_ids_unique(self) -> None:
        snap = _snap(
            patterns=(_underperform_pattern("H-13"), _underperform_pattern("H-07")),
        )
        plans = _plans_from_snapshot(snap, _DATASETS)
        ids = [p.plan_id for p in plans]
        assert len(ids) == len(set(ids))

    def test_empty_datasets_gives_empty_tasks(self) -> None:
        snap = _snap(patterns=(_underperform_pattern(),))
        plans = _plans_from_snapshot(snap, [])
        assert all(len(p.tasks) == 0 for p in plans)


# ---------------------------------------------------------------------------
# ExperimentPlanner — full agent run
# ---------------------------------------------------------------------------

class TestExperimentPlannerRun:
    def _run(
        self,
        tmp_path: Path,
        snap: KnowledgeSnapshot | None = None,
    ) -> AgentResult:
        if snap is None:
            snap = _snap(
                patterns=(_underperform_pattern(),),
                connections=(_negative_conn(),),
            )
        return ExperimentPlanner(tmp_path).run(
            snap, _DATASETS, campaign_id="camp", _clock=_fixed_clock
        )

    def test_returns_agent_result(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path), AgentResult)

    def test_agent_id(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_id == "experiment-planner"

    def test_agent_type_research(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_type == "RESEARCH"

    def test_output_is_tuple(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path).output, tuple)

    def test_output_contains_experiment_plans(self, tmp_path: Path) -> None:
        for plan in self._run(tmp_path).output:
            assert isinstance(plan, ExperimentPlan)

    def test_created_at_uses_clock(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).created_at == "2026-06-27T12:00:00"

    def test_confidence_is_average_of_plan_confidences(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        plans: tuple[ExperimentPlan, ...] = result.output  # type: ignore[assignment]
        if plans:
            expected = sum(p.confidence for p in plans) / len(plans)
            assert result.confidence.value == pytest.approx(expected, abs=1e-5)

    def test_evidence_references_knowledge_snapshot(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert any("knowledge" in e.source for e in result.evidence)

    def test_empty_snapshot_zero_confidence(self, tmp_path: Path) -> None:
        result = ExperimentPlanner(tmp_path).run(
            _snap(), _DATASETS, _clock=_fixed_clock
        )
        assert result.confidence.value == 0.0

    def test_contradiction_plan_is_critical(self, tmp_path: Path) -> None:
        snap = _snap(contradictions=("Contradiction: H-13 conflict",))
        result = ExperimentPlanner(tmp_path).run(snap, _DATASETS, _clock=_fixed_clock)
        plans: tuple[ExperimentPlan, ...] = result.output  # type: ignore[assignment]
        assert any(p.priority == "critical" for p in plans)


# ---------------------------------------------------------------------------
# Overfitting risk detection in full runs
# ---------------------------------------------------------------------------

class TestOverfittingRiskDetection:
    def test_no_param_plans_have_low_risk(self, tmp_path: Path) -> None:
        snap = _snap(
            patterns=(_underperform_pattern(),),
            connections=(_negative_conn(),),
        )
        result = ExperimentPlanner(tmp_path).run(snap, _DATASETS, _clock=_fixed_clock)
        for plan in result.output:
            assert plan.overfitting_risk.level == "low"

    def test_low_risk_reason_mentions_no_params(self, tmp_path: Path) -> None:
        snap = _snap(patterns=(_underperform_pattern(),))
        result = ExperimentPlanner(tmp_path).run(snap, _DATASETS, _clock=_fixed_clock)
        for plan in result.output:
            assert plan.overfitting_risk.parameter_count == 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def _run_and_list_files(self, tmp_path: Path) -> list[Path]:
        snap = _snap(
            patterns=(_underperform_pattern(), _outperform_pattern()),
            connections=(_negative_conn(),),
        )
        ExperimentPlanner(tmp_path).run(snap, _DATASETS, _clock=_fixed_clock)
        return list((tmp_path / "research_programs" / "plans").glob("*.json"))

    def test_json_files_created(self, tmp_path: Path) -> None:
        files = self._run_and_list_files(tmp_path)
        assert len(files) == 3  # 1 underperform + 1 negative + 1 outperform

    def test_plans_dir_is_inside_research_programs(self, tmp_path: Path) -> None:
        files = self._run_and_list_files(tmp_path)
        for f in files:
            assert "research_programs" in str(f)
            assert "plans" in str(f)

    def test_json_contains_plan_id(self, tmp_path: Path) -> None:
        files = self._run_and_list_files(tmp_path)
        for f in files:
            with open(f) as fp:
                data = json.load(fp)
            assert "plan_id" in data
            assert data["plan_id"] == f.stem

    def test_json_contains_hypothesis_id(self, tmp_path: Path) -> None:
        files = self._run_and_list_files(tmp_path)
        for f in files:
            with open(f) as fp:
                data = json.load(fp)
            assert "hypothesis_id" in data

    def test_json_contains_stop_conditions(self, tmp_path: Path) -> None:
        files = self._run_and_list_files(tmp_path)
        for f in files:
            with open(f) as fp:
                data = json.load(fp)
            assert isinstance(data["stop_conditions"], list)
            assert len(data["stop_conditions"]) >= 1

    def test_json_contains_overfitting_risk(self, tmp_path: Path) -> None:
        files = self._run_and_list_files(tmp_path)
        for f in files:
            with open(f) as fp:
                data = json.load(fp)
            assert "overfitting_risk" in data
            assert data["overfitting_risk"]["level"] in ("low", "medium", "high")

    def test_json_contains_tasks(self, tmp_path: Path) -> None:
        files = self._run_and_list_files(tmp_path)
        for f in files:
            with open(f) as fp:
                data = json.load(fp)
            assert isinstance(data["tasks"], list)

    def test_second_run_overwrites(self, tmp_path: Path) -> None:
        snap = _snap(patterns=(_underperform_pattern(),))
        planner = ExperimentPlanner(tmp_path)
        planner.run(snap, _DATASETS, _clock=_fixed_clock)
        planner.run(snap, _DATASETS, _clock=_fixed_clock)  # no error
        files = list((tmp_path / "research_programs" / "plans").glob("*.json"))
        assert len(files) == 1  # same file overwritten


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def _plans(self, tmp_path: Path, snap: KnowledgeSnapshot) -> tuple[ExperimentPlan, ...]:
        return ExperimentPlanner(tmp_path).run(
            snap, _DATASETS, _clock=_fixed_clock
        ).output  # type: ignore[return-value]

    def test_same_input_same_plan_ids(self, tmp_path: Path) -> None:
        snap = _snap(patterns=(_underperform_pattern(),), connections=(_negative_conn(),))
        p1 = self._plans(tmp_path, snap)
        p2 = self._plans(tmp_path, snap)
        assert [p.plan_id for p in p1] == [p.plan_id for p in p2]

    def test_same_input_same_priorities(self, tmp_path: Path) -> None:
        snap = _snap(patterns=(_underperform_pattern(),), connections=(_negative_conn(),))
        p1 = self._plans(tmp_path, snap)
        p2 = self._plans(tmp_path, snap)
        assert [p.priority for p in p1] == [p.priority for p in p2]

    def test_created_at_matches_clock(self, tmp_path: Path) -> None:
        snap = _snap(patterns=(_underperform_pattern(),))
        result = ExperimentPlanner(tmp_path).run(
            snap, _DATASETS, _clock=lambda: datetime(2025, 1, 1, 0, 0, 0)
        )
        assert result.created_at == "2025-01-01T00:00:00"

    def test_different_hypotheses_different_plan_ids(self, tmp_path: Path) -> None:
        snap1 = _snap(patterns=(_underperform_pattern("H-13"),))
        snap2 = _snap(patterns=(_underperform_pattern("H-07"),))
        p1 = self._plans(tmp_path, snap1)
        p2 = self._plans(tmp_path, snap2)
        assert p1[0].plan_id != p2[0].plan_id
