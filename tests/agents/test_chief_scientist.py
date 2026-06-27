"""Tests for ChiefScientist v1 — Layer 3 CHIEF_SCIENTIST Agent (Phase 8).

No ML, no LLM, no Research Service calls. All tests are pure Python.
Covers: protocol compliance, all 7 rules, decision ordering, persistence, determinism.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from agents.models import (
    AgentResult,
    ConfidenceScore,
    DecisionReason,
    EvidenceRef,
    ExperimentPlan,
    ExperimentTask,
    KnowledgeConnection,
    KnowledgeFact,
    KnowledgePattern,
    KnowledgeSnapshot,
    OverfittingRisk,
    ResearchDecision,
    ResearchPolicy,
    StopCondition,
    ValidationBatchResult,
)
from agents.research.chief import (
    ChiefScientist,
    _R01_STOP,
    _R02_ARCHIVE,
    _R03_CONTRADICTION,
    _R04_NEGATIVE_CONN,
    _R05_EVIDENCE,
    _R06_SKIP_RISK,
    _R07_EXPANSION,
    _evaluate_rules,
    _hypothesis_stats,
    _r02_archive_hypothesis,
    _r03_contradiction_replication,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_DATASETS = ["sber_1h_2023_main", "gazp_1h_2023_main", "lkoh_1h_2023_main"]


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


def _evidence() -> EvidenceRef:
    return EvidenceRef(source="test", reference="snap_001", timestamp="2026-06-27T12:00:00")


def _conf(v: float = 0.7) -> ConfidenceScore:
    return ConfidenceScore(value=v, reason="test")


def _fact(
    hyp_id: str = "H-13",
    passed: bool | None = False,
    value: float = 0.15,
    metric: str = "pass_rate",
    idx: int = 0,
) -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=f"fact_{hyp_id}_{idx:04d}",
        source_type="research_report",
        source_ref=f"reports/{hyp_id}_{idx}.json",
        hypothesis_id=hyp_id,
        instrument="SBER",
        period="2023",
        regime="TREND_UP",
        metric=metric,
        value=value,
        passed=passed,
        confidence=0.85,
        tags=("adx",),
    )


def _connection(
    hyp_id: str = "H-13",
    regime: str = "TREND_UP",
    relation: str = "negative",
    strength: float = 0.8,
    support_count: int = 3,
) -> KnowledgeConnection:
    return KnowledgeConnection(
        connection_id=f"conn_{hyp_id.lower().replace('-', '')}_{regime.lower()}",
        entity_a=hyp_id,
        entity_b=regime,
        relation=relation,
        strength=strength,
        support_count=support_count,
        evidence=tuple(f"fact_{i}" for i in range(support_count)),
    )


def _pattern(
    hyp_id: str = "H-07",
    pattern_type: str = "outperformance",
    occurrence_count: int = 4,
) -> KnowledgePattern:
    return KnowledgePattern(
        pattern_id=f"pat_{hyp_id.lower().replace('-', '')}_{pattern_type}",
        description=f"{hyp_id} {pattern_type}",
        pattern_type=pattern_type,
        entities=(hyp_id,),
        occurrence_count=occurrence_count,
        confidence=0.8,
        supporting_facts=tuple(f"f{i}" for i in range(occurrence_count)),
        contradicting_facts=(),
    )


def _snap(
    facts: tuple[KnowledgeFact, ...] = (),
    connections: tuple[KnowledgeConnection, ...] = (),
    patterns: tuple[KnowledgePattern, ...] = (),
    contradictions: tuple[str, ...] = (),
) -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        snapshot_id="snap_camp_001",
        campaign_id="camp",
        facts=facts,
        connections=connections,
        patterns=patterns,
        strong_facts=(),
        weak_facts=(),
        contradictions=contradictions,
        recommendations=(),
        source_refs=(_evidence(),),
        confidence=_conf(0.7),
    )


def _overfitting(level: str = "low", n: int = 0) -> OverfittingRisk:
    return OverfittingRisk(level=level, parameter_count=n, reasons=(f"{level} risk",))


def _plan(
    plan_id: str = "plan_0001_explore_h13",
    plan_type: str = "regime_exploration",
    hyp_id: str = "H-13",
    overfitting_level: str = "low",
    confidence: float = 0.6,
    n_tasks: int = 2,
) -> ExperimentPlan:
    tasks = tuple(
        ExperimentTask(
            task_id=f"{plan_id}_t{i:02d}",
            hypothesis_id=hyp_id,
            instrument=_DATASETS[i].split("_")[0].upper(),
            dataset_id=_DATASETS[i],
            regime_filter="",
            parameters=(),
        )
        for i in range(n_tasks)
    )
    return ExperimentPlan(
        plan_id=plan_id,
        plan_type=plan_type,
        objective=f"Test {hyp_id}",
        hypothesis_id=hyp_id,
        instruments=tuple(t.instrument for t in tasks),
        datasets=tuple(_DATASETS[:n_tasks]),
        regime_filter="",
        tasks=tasks,
        parameters=(),
        expected_evidence=("improved pass_rate",),
        rationale="test plan",
        priority="medium",
        overfitting_risk=_overfitting(overfitting_level, 0 if overfitting_level == "low" else 2),
        stop_conditions=(StopCondition("max_experiments", 10.0, "stop at 10"),),
        confidence=confidence,
        source_pattern_id="pat_0001",
    )


def _contradiction_plan(hyp_id: str = "H-13") -> ExperimentPlan:
    return _plan(
        plan_id=f"plan_0002_replicate_{hyp_id.lower().replace('-', '')}",
        plan_type="contradiction_replication",
        hyp_id=hyp_id,
    )


def _regime_filter_plan(hyp_id: str = "H-13") -> ExperimentPlan:
    return _plan(
        plan_id=f"plan_0003_filter_{hyp_id.lower().replace('-', '')}",
        plan_type="regime_filter",
        hyp_id=hyp_id,
        confidence=0.6,
    )


def _expansion_plan(hyp_id: str = "H-07", confidence: float = 0.8) -> ExperimentPlan:
    return _plan(
        plan_id=f"plan_0004_expand_{hyp_id.lower().replace('-', '')}",
        plan_type="expansion",
        hyp_id=hyp_id,
        confidence=confidence,
    )


def _batch_result(
    plan_id: str = "plan_0001_explore_h13",
    stop_triggered: bool = False,
    stop_reason: str = "",
    avg_pass_rate: float | None = 0.65,
) -> ValidationBatchResult:
    return ValidationBatchResult(
        batch_id=f"{plan_id}_batch",
        plan_id=plan_id,
        campaign_id="camp",
        total_tasks=2,
        completed_tasks=2 if not stop_triggered else 0,
        stopped_tasks=0,
        error_tasks=0,
        dry_run_tasks=0,
        blocked_tasks=0,
        avg_pass_rate=avg_pass_rate,
        stop_triggered=stop_triggered,
        stop_reason=stop_reason,
        report_paths=("reports/r.json",) if not stop_triggered else (),
        validation_run_path="research_programs/validation_runs/v.json",
        created_at="2026-06-27T12:00:00",
    )


_DEFAULT_POLICY = ResearchPolicy()


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

class TestChiefScientistProtocol:
    def test_agent_id(self, tmp_path: Path) -> None:
        assert ChiefScientist(tmp_path).agent_id == "chief-scientist"

    def test_agent_type_is_chief_scientist(self, tmp_path: Path) -> None:
        assert ChiefScientist(tmp_path).agent_type == "CHIEF_SCIENTIST"

    def test_version_is_string(self, tmp_path: Path) -> None:
        assert isinstance(ChiefScientist(tmp_path).version, str)

    def test_run_returns_agent_result(self, tmp_path: Path) -> None:
        result = ChiefScientist(tmp_path).run(
            _snap(), [], _clock=_fixed_clock
        )
        assert isinstance(result, AgentResult)

    def test_output_is_tuple_of_decisions(self, tmp_path: Path) -> None:
        result = ChiefScientist(tmp_path).run(
            _snap(), [], _clock=_fixed_clock
        )
        assert isinstance(result.output, tuple)
        for item in result.output:
            assert isinstance(item, ResearchDecision)


# ---------------------------------------------------------------------------
# R02 — Archive hypothesis
# ---------------------------------------------------------------------------

class TestArchiveRule:
    def _snap_with_fails(self, n_fails: int, avg_pr: float, hyp_id: str = "H-13") -> KnowledgeSnapshot:
        facts = tuple(
            _fact(hyp_id=hyp_id, passed=False, value=avg_pr, idx=i)
            for i in range(n_fails)
        )
        return _snap(facts=facts)

    def test_archive_triggered_with_three_fails(self, tmp_path: Path) -> None:
        snap = self._snap_with_fails(3, 0.10)
        result = ChiefScientist(tmp_path).run(snap, [], _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.decision_type == "ARCHIVE_HYPOTHESIS" for d in decisions)

    def test_archive_not_triggered_with_two_fails(self, tmp_path: Path) -> None:
        snap = self._snap_with_fails(2, 0.10)
        result = ChiefScientist(tmp_path).run(snap, [], _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.decision_type == "ARCHIVE_HYPOTHESIS" for d in decisions)

    def test_archive_not_triggered_if_pass_rate_above_ceiling(self, tmp_path: Path) -> None:
        snap = self._snap_with_fails(5, 0.50)  # high pass_rate → no archive
        result = ChiefScientist(tmp_path).run(snap, [], _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.decision_type == "ARCHIVE_HYPOTHESIS" for d in decisions)

    def test_archive_decision_hypothesis_id(self, tmp_path: Path) -> None:
        snap = self._snap_with_fails(3, 0.10, hyp_id="H-13")
        result = ChiefScientist(tmp_path).run(snap, [], _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        archive = next(d for d in decisions if d.decision_type == "ARCHIVE_HYPOTHESIS")
        assert archive.hypothesis_id == "H-13"

    def test_archive_priority_is_high(self, tmp_path: Path) -> None:
        snap = self._snap_with_fails(3, 0.10)
        result = ChiefScientist(tmp_path).run(snap, [], _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        archive = next(d for d in decisions if d.decision_type == "ARCHIVE_HYPOTHESIS")
        assert archive.priority == "high"

    def test_archive_rule_id(self, tmp_path: Path) -> None:
        snap = self._snap_with_fails(3, 0.10)
        result = ChiefScientist(tmp_path).run(snap, [], _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        archive = next(d for d in decisions if d.decision_type == "ARCHIVE_HYPOTHESIS")
        assert archive.reason.rule_id == _R02_ARCHIVE

    def test_custom_threshold_respected(self, tmp_path: Path) -> None:
        policy = ResearchPolicy(archive_fail_threshold=5)
        snap = self._snap_with_fails(4, 0.10)  # only 4 fails, threshold=5
        result = ChiefScientist(tmp_path).run(snap, [], policy=policy, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.decision_type == "ARCHIVE_HYPOTHESIS" for d in decisions)


# ---------------------------------------------------------------------------
# R03 — Contradiction priority
# ---------------------------------------------------------------------------

class TestContradictionPriorityRule:
    def test_contradiction_triggers_run_plan(self, tmp_path: Path) -> None:
        snap = _snap(contradictions=("Contradiction: H-13 in RANGE shows conflict",))
        plans = [_contradiction_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.decision_type == "RUN_PLAN" for d in decisions)

    def test_contradiction_run_plan_priority_is_critical(self, tmp_path: Path) -> None:
        snap = _snap(contradictions=("Contradiction: H-13 shows conflict",))
        plans = [_contradiction_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        run = next(d for d in decisions if d.decision_type == "RUN_PLAN" and d.priority == "critical")
        assert run.priority == "critical"

    def test_no_contradiction_no_critical_run(self, tmp_path: Path) -> None:
        snap = _snap()  # no contradictions
        plans = [_contradiction_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        # No critical RUN_PLAN decisions expected
        critical_run = [d for d in decisions if d.decision_type == "RUN_PLAN" and d.priority == "critical"]
        assert critical_run == []

    def test_contradiction_selects_contradiction_plan(self, tmp_path: Path) -> None:
        snap = _snap(contradictions=("Contradiction: H-13 conflict",))
        plans = [_contradiction_plan("H-13")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        run = next(d for d in decisions if d.decision_type == "RUN_PLAN" and d.priority == "critical")
        assert "replicate" in run.plan_id or "contradiction" in run.plan_id

    def test_contradiction_rule_id_r03(self, tmp_path: Path) -> None:
        snap = _snap(contradictions=("Contradiction: H-13 conflict",))
        plans = [_contradiction_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        run = next(d for d in decisions if d.decision_type == "RUN_PLAN" and d.priority == "critical")
        assert run.reason.rule_id == _R03_CONTRADICTION


# ---------------------------------------------------------------------------
# R04 — Negative connection plan selection
# ---------------------------------------------------------------------------

class TestNegativeConnectionPlanSelection:
    def test_negative_conn_selects_regime_filter(self, tmp_path: Path) -> None:
        snap = _snap(connections=(_connection(strength=0.8),))
        plans = [_regime_filter_plan("H-13")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.decision_type == "RUN_PLAN" and d.priority == "high" for d in decisions)

    def test_strength_below_threshold_no_decision(self, tmp_path: Path) -> None:
        snap = _snap(connections=(_connection(strength=0.5),))  # below 0.6
        plans = [_regime_filter_plan("H-13")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        filter_runs = [d for d in decisions if d.decision_type == "RUN_PLAN" and d.reason.rule_id == _R04_NEGATIVE_CONN]
        assert filter_runs == []

    def test_connection_strength_at_threshold_fires(self, tmp_path: Path) -> None:
        snap = _snap(connections=(_connection(strength=0.6),))  # exactly 0.6
        plans = [_regime_filter_plan("H-13")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.reason.rule_id == _R04_NEGATIVE_CONN for d in decisions)

    def test_run_plan_priority_is_high(self, tmp_path: Path) -> None:
        snap = _snap(connections=(_connection(strength=0.9),))
        plans = [_regime_filter_plan("H-13")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        run = next(d for d in decisions if d.reason.rule_id == _R04_NEGATIVE_CONN)
        assert run.priority == "high"

    def test_positive_connection_not_selected(self, tmp_path: Path) -> None:
        snap = _snap(connections=(_connection(relation="positive", strength=1.0),))
        plans = [_regime_filter_plan("H-13")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        filter_runs = [d for d in decisions if d.reason.rule_id == _R04_NEGATIVE_CONN]
        assert filter_runs == []

    def test_rule_id_is_r04(self, tmp_path: Path) -> None:
        snap = _snap(connections=(_connection(strength=0.8),))
        plans = [_regime_filter_plan("H-13")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        run = next(d for d in decisions if d.reason.rule_id == _R04_NEGATIVE_CONN)
        assert run.reason.rule_id == _R04_NEGATIVE_CONN


# ---------------------------------------------------------------------------
# R05 — Insufficient evidence
# ---------------------------------------------------------------------------

class TestInsufficientEvidence:
    def test_zero_facts_requests_evidence(self, tmp_path: Path) -> None:
        snap = _snap()  # no facts
        plans = [_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.decision_type == "REQUEST_MORE_EVIDENCE" for d in decisions)

    def test_two_facts_below_threshold(self, tmp_path: Path) -> None:
        snap = _snap(facts=(_fact(idx=0), _fact(idx=1)))
        plans = [_plan()]  # min_runs_for_evidence=3
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.decision_type == "REQUEST_MORE_EVIDENCE" for d in decisions)

    def test_three_facts_not_triggers(self, tmp_path: Path) -> None:
        snap = _snap(facts=tuple(_fact(idx=i) for i in range(3)))
        plans = [_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.decision_type == "REQUEST_MORE_EVIDENCE" for d in decisions)

    def test_decision_type_is_request_more_evidence(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        evidence_dec = next(d for d in decisions if d.decision_type == "REQUEST_MORE_EVIDENCE")
        assert evidence_dec.decision_type == "REQUEST_MORE_EVIDENCE"

    def test_priority_is_medium(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        evidence_dec = next(d for d in decisions if d.decision_type == "REQUEST_MORE_EVIDENCE")
        assert evidence_dec.priority == "medium"

    def test_rule_id_is_r05(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        evidence_dec = next(d for d in decisions if d.decision_type == "REQUEST_MORE_EVIDENCE")
        assert evidence_dec.reason.rule_id == _R05_EVIDENCE

    def test_deduplication_per_hypothesis(self, tmp_path: Path) -> None:
        snap = _snap()
        # Two plans for the same hypothesis — should produce only ONE REQUEST_MORE_EVIDENCE
        plans = [
            _plan(plan_id="plan_0001", hyp_id="H-13"),
            _plan(plan_id="plan_0002", hyp_id="H-13"),
        ]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        evidence_decs = [d for d in decisions if d.decision_type == "REQUEST_MORE_EVIDENCE"]
        assert len(evidence_decs) == 1


# ---------------------------------------------------------------------------
# R06 — Overfitting skip
# ---------------------------------------------------------------------------

class TestOverfittingSkip:
    def test_high_risk_skipped_by_default(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan(overfitting_level="high")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.decision_type == "SKIP_PLAN" for d in decisions)

    def test_high_risk_not_skipped_with_allow(self, tmp_path: Path) -> None:
        policy = ResearchPolicy(allow_high_risk=True)
        snap = _snap()
        plans = [_plan(overfitting_level="high")]
        result = ChiefScientist(tmp_path).run(snap, plans, policy=policy, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.decision_type == "SKIP_PLAN" for d in decisions)

    def test_low_risk_not_skipped(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan(overfitting_level="low")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.decision_type == "SKIP_PLAN" for d in decisions)

    def test_skip_priority_is_low(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan(overfitting_level="high")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        skip = next(d for d in decisions if d.decision_type == "SKIP_PLAN")
        assert skip.priority == "low"

    def test_skip_decision_references_plan(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan(plan_id="plan_0001_explore_h13", overfitting_level="high")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        skip = next(d for d in decisions if d.decision_type == "SKIP_PLAN")
        assert "plan_0001" in skip.plan_id

    def test_rule_id_is_r06(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_plan(overfitting_level="high")]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        skip = next(d for d in decisions if d.decision_type == "SKIP_PLAN")
        assert skip.reason.rule_id == _R06_SKIP_RISK


# ---------------------------------------------------------------------------
# R01 — Stop condition rule
# ---------------------------------------------------------------------------

class TestStopConditionRule:
    def test_stop_triggered_creates_stop_decision(self, tmp_path: Path) -> None:
        snap = _snap()
        prev = [_batch_result(stop_triggered=True, stop_reason="max_experiments=10 reached")]
        result = ChiefScientist(tmp_path).run(snap, [], previous_results=prev, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.decision_type == "STOP_RESEARCH_LINE" for d in decisions)

    def test_no_stop_no_decision(self, tmp_path: Path) -> None:
        snap = _snap()
        prev = [_batch_result(stop_triggered=False)]
        result = ChiefScientist(tmp_path).run(snap, [], previous_results=prev, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.decision_type == "STOP_RESEARCH_LINE" for d in decisions)

    def test_stop_priority_is_critical(self, tmp_path: Path) -> None:
        snap = _snap()
        prev = [_batch_result(stop_triggered=True, stop_reason="min_pass_rate triggered")]
        result = ChiefScientist(tmp_path).run(snap, [], previous_results=prev, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        stop = next(d for d in decisions if d.decision_type == "STOP_RESEARCH_LINE")
        assert stop.priority == "critical"

    def test_stop_decision_type(self, tmp_path: Path) -> None:
        snap = _snap()
        prev = [_batch_result(stop_triggered=True, stop_reason="stop_reason_here")]
        result = ChiefScientist(tmp_path).run(snap, [], previous_results=prev, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        stop = next(d for d in decisions if d.decision_type == "STOP_RESEARCH_LINE")
        assert stop.decision_type == "STOP_RESEARCH_LINE"

    def test_rule_id_is_r01(self, tmp_path: Path) -> None:
        snap = _snap()
        prev = [_batch_result(stop_triggered=True, stop_reason="x")]
        result = ChiefScientist(tmp_path).run(snap, [], previous_results=prev, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        stop = next(d for d in decisions if d.decision_type == "STOP_RESEARCH_LINE")
        assert stop.reason.rule_id == _R01_STOP

    def test_multiple_stops(self, tmp_path: Path) -> None:
        snap = _snap()
        prev = [
            _batch_result("plan_a", stop_triggered=True, stop_reason="x"),
            _batch_result("plan_b", stop_triggered=True, stop_reason="y"),
        ]
        result = ChiefScientist(tmp_path).run(snap, [], previous_results=prev, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        stops = [d for d in decisions if d.decision_type == "STOP_RESEARCH_LINE"]
        assert len(stops) == 2


# ---------------------------------------------------------------------------
# R07 — Outperformance expansion
# ---------------------------------------------------------------------------

class TestOutperformanceExpansionRule:
    def test_expansion_plan_selected(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_expansion_plan(confidence=0.8)]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert any(d.reason.rule_id == _R07_EXPANSION for d in decisions)

    def test_below_confidence_threshold_not_selected(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_expansion_plan(confidence=0.1)]  # below min_confidence=0.3
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        assert not any(d.reason.rule_id == _R07_EXPANSION for d in decisions)

    def test_expansion_priority_is_high(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_expansion_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        expand = next(d for d in decisions if d.reason.rule_id == _R07_EXPANSION)
        assert expand.priority == "high"


# ---------------------------------------------------------------------------
# Decision ordering
# ---------------------------------------------------------------------------

class TestDeterministicDecisionOrdering:
    def _full_snap(self) -> KnowledgeSnapshot:
        facts = tuple(_fact(idx=i, passed=False, value=0.10) for i in range(3))
        return _snap(
            facts=facts,
            connections=(_connection(strength=0.8),),
            contradictions=("Contradiction: H-13 conflict",),
        )

    def _all_plans(self) -> list[ExperimentPlan]:
        return [
            _contradiction_plan(),
            _regime_filter_plan(),
            _expansion_plan(),
            _plan(overfitting_level="high"),
        ]

    def test_critical_before_high(self, tmp_path: Path) -> None:
        snap = self._full_snap()
        result = ChiefScientist(tmp_path).run(
            snap, self._all_plans(), _clock=_fixed_clock
        )
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        priorities = [d.priority for d in decisions]
        # Once we see "high", we must not see "critical" again
        found_critical = False
        found_high = False
        for p in priorities:
            if p == "critical":
                found_critical = True
                assert not found_high, "critical found after high"
            elif p == "high":
                found_high = True

    def test_high_before_medium(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [_expansion_plan(), _plan()]  # R07=high, R05=medium
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        priorities = [d.priority for d in decisions]
        found_high = found_medium = False
        for p in priorities:
            if p == "high":
                found_high = True
                assert not found_medium, "high found after medium"
            elif p == "medium":
                found_medium = True

    def test_medium_before_low(self, tmp_path: Path) -> None:
        snap = _snap()
        plans = [
            _plan(overfitting_level="high"),  # R06=low
            _plan(plan_id="plan_0002", overfitting_level="low"),  # R05=medium
        ]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        decisions: tuple[ResearchDecision, ...] = result.output  # type: ignore[assignment]
        priorities = [d.priority for d in decisions]
        found_medium = found_low = False
        for p in priorities:
            if p == "medium":
                found_medium = True
                assert not found_low, "medium found after low"
            elif p == "low":
                found_low = True

    def test_same_input_same_order(self, tmp_path: Path) -> None:
        snap = self._full_snap()
        agent = ChiefScientist(tmp_path)
        r1 = agent.run(snap, self._all_plans(), _clock=_fixed_clock)
        r2 = agent.run(snap, self._all_plans(), _clock=_fixed_clock)
        ids1 = [d.decision_id for d in r1.output]
        ids2 = [d.decision_id for d in r2.output]
        assert ids1 == ids2

    def test_max_decisions_respected(self, tmp_path: Path) -> None:
        policy = ResearchPolicy(max_decisions_per_run=2)
        snap = self._full_snap()
        result = ChiefScientist(tmp_path).run(
            snap, self._all_plans(), policy=policy, _clock=_fixed_clock
        )
        assert len(result.output) <= 2


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def _run(self, tmp_path: Path) -> tuple[ResearchDecision, ...]:
        snap = _snap(
            facts=tuple(_fact(idx=i, passed=False, value=0.10) for i in range(3)),
            contradictions=("Contradiction: H-13 conflict",),
        )
        plans = [_contradiction_plan()]
        result = ChiefScientist(tmp_path).run(snap, plans, _clock=_fixed_clock)
        return result.output  # type: ignore[return-value]

    def test_json_files_created(self, tmp_path: Path) -> None:
        decisions = self._run(tmp_path)
        files = list((tmp_path / "research_programs" / "decisions").glob("*.json"))
        assert len(files) == len(decisions)
        assert len(files) > 0

    def test_each_decision_has_own_file(self, tmp_path: Path) -> None:
        decisions = self._run(tmp_path)
        files = list((tmp_path / "research_programs" / "decisions").glob("*.json"))
        file_names = {f.stem for f in files}
        decision_ids = {d.decision_id for d in decisions}
        assert file_names == decision_ids

    def test_json_contains_decision_id(self, tmp_path: Path) -> None:
        decisions = self._run(tmp_path)
        for dec in decisions:
            path = tmp_path / "research_programs" / "decisions" / f"{dec.decision_id}.json"
            with open(path) as fp:
                data = json.load(fp)
            assert data["decision_id"] == dec.decision_id

    def test_json_contains_rule_id(self, tmp_path: Path) -> None:
        decisions = self._run(tmp_path)
        for dec in decisions:
            path = tmp_path / "research_programs" / "decisions" / f"{dec.decision_id}.json"
            with open(path) as fp:
                data = json.load(fp)
            assert "rule_id" in data["reason"]

    def test_decision_dir_inside_research_programs(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        dec_dir = tmp_path / "research_programs" / "decisions"
        assert dec_dir.exists()

    def test_json_contains_priority(self, tmp_path: Path) -> None:
        decisions = self._run(tmp_path)
        for dec in decisions:
            path = tmp_path / "research_programs" / "decisions" / f"{dec.decision_id}.json"
            with open(path) as fp:
                data = json.load(fp)
            assert data["priority"] in ("critical", "high", "medium", "low")

    def test_json_contains_evidence(self, tmp_path: Path) -> None:
        decisions = self._run(tmp_path)
        for dec in decisions:
            path = tmp_path / "research_programs" / "decisions" / f"{dec.decision_id}.json"
            with open(path) as fp:
                data = json.load(fp)
            assert isinstance(data["reason"]["evidence"], list)

    def test_second_run_overwrites(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        self._run(tmp_path)  # no error, files overwritten
        files = list((tmp_path / "research_programs" / "decisions").glob("*.json"))
        assert len(files) > 0


# ---------------------------------------------------------------------------
# AgentResult protocol compliance
# ---------------------------------------------------------------------------

class TestAgentResultCompliance:
    def _result(self, tmp_path: Path) -> AgentResult:
        snap = _snap(contradictions=("Contradiction: H-13",))
        return ChiefScientist(tmp_path).run(snap, [_contradiction_plan()], _clock=_fixed_clock)

    def test_agent_id(self, tmp_path: Path) -> None:
        assert self._result(tmp_path).agent_id == "chief-scientist"

    def test_agent_type(self, tmp_path: Path) -> None:
        assert self._result(tmp_path).agent_type == "CHIEF_SCIENTIST"

    def test_created_at_uses_clock(self, tmp_path: Path) -> None:
        assert self._result(tmp_path).created_at == "2026-06-27T12:00:00"

    def test_evidence_references_snapshot(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        assert any("knowledge" in e.source for e in result.evidence)

    def test_confidence_in_valid_range(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        assert 0.0 <= result.confidence.value <= 1.0

    def test_empty_input_returns_agent_result(self, tmp_path: Path) -> None:
        result = ChiefScientist(tmp_path).run(_snap(), [], _clock=_fixed_clock)
        assert isinstance(result, AgentResult)
        assert result.output == ()

    def test_input_summary_contains_facts_count(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        assert "facts" in result.input_summary


# ---------------------------------------------------------------------------
# _hypothesis_stats helper
# ---------------------------------------------------------------------------

class TestHypothesisStats:
    def test_fail_count(self) -> None:
        facts = tuple(_fact(passed=False, idx=i) for i in range(3))
        fails, _ = _hypothesis_stats(facts)
        assert fails.get("H-13", 0) == 3

    def test_pass_fact_not_counted_as_fail(self) -> None:
        facts = (_fact(passed=True, idx=0),)
        fails, _ = _hypothesis_stats(facts)
        assert fails.get("H-13", 0) == 0

    def test_avg_pass_rate_computed(self) -> None:
        facts = (
            _fact(passed=False, value=0.10, idx=0),
            _fact(passed=False, value=0.20, idx=1),
        )
        _, rates = _hypothesis_stats(facts)
        assert rates.get("H-13") == pytest.approx(0.15)

    def test_nan_value_excluded_from_avg(self) -> None:
        facts = (
            _fact(metric="pass_rate", value=float("nan"), idx=0, passed=None),
            _fact(metric="pass_rate", value=0.30, idx=1, passed=True),
        )
        _, rates = _hypothesis_stats(facts)
        assert rates.get("H-13") == pytest.approx(0.30)

    def test_no_facts_empty_dicts(self) -> None:
        fails, rates = _hypothesis_stats(())
        assert fails == {}
        assert rates == {}

    def test_multiple_hypotheses(self) -> None:
        facts = (
            _fact(hyp_id="H-13", passed=False, idx=0),
            _fact(hyp_id="H-07", passed=False, idx=0),
            _fact(hyp_id="H-07", passed=False, idx=1),
        )
        fails, _ = _hypothesis_stats(facts)
        assert fails.get("H-13", 0) == 1
        assert fails.get("H-07", 0) == 2
