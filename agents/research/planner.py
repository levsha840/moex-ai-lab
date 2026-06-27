"""ExperimentPlanner — Layer 3 RESEARCH Agent.

Generates reproducible, evidence-based experiment proposals from existing
KnowledgeSnapshot artifacts.  Never runs experiments itself.  Never modifies
Research Service.  Never selects the "best" strategy.  Never generates trading
signals.  Pure proposal generation from deterministic rules.

Planning rules:
  1. Underperformance pattern   → regime_exploration plan  (priority: medium)
  2. Negative connection        → regime_filter plan        (priority: high)
  3. Contradiction              → contradiction_replication (priority: critical)
  4. Outperformance pattern     → expansion plan            (priority: high)

Confidence from evidence support_count:
  < 3 runs → 0.30  (low evidence)
  < 5 runs → 0.60
  ≥ 5 runs → 0.80

Overfitting risk from parameter_count:
  0 changes → low
  1 change  → medium
  ≥ 2       → high  (flagged, not forbidden)

Plans saved to {data_dir}/research_programs/plans/{plan_id}.json.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.models import (
    AgentResult,
    ConfidenceScore,
    EvidenceRef,
    ExperimentPlan,
    ExperimentTask,
    KnowledgeConnection,
    KnowledgePattern,
    KnowledgeSnapshot,
    OverfittingRisk,
    StopCondition,
)

_AGENT_ID = "experiment-planner"
_AGENT_TYPE = "RESEARCH"
_VERSION = "1.0"

_DEFAULT_MAX_EXPERIMENTS = 10.0
_DEFAULT_MIN_PASS_RATE = 0.5
_MAX_TASKS_PER_PLAN = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _instrument_from_dataset(dataset_id: str) -> str:
    """Extract instrument ticker from dataset id using {ticker}_{tf}_{period}_{session} convention."""
    parts = dataset_id.split("_")
    return parts[0].upper() if parts and parts[0] else "UNKNOWN"


def _evidence_confidence(support_count: int) -> float:
    """Confidence derived from the number of runs supporting the trigger."""
    if support_count < 3:
        return 0.30
    if support_count < 5:
        return 0.60
    return 0.80


def _overfitting_risk(parameters: tuple[tuple[str, str], ...]) -> OverfittingRisk:
    """Assess overfitting risk from the number of parameters being changed."""
    n = len(parameters)
    if n == 0:
        return OverfittingRisk(
            level="low",
            parameter_count=0,
            reasons=("No hypothesis parameters changed — regime or instrument change only",),
        )
    if n == 1:
        return OverfittingRisk(
            level="medium",
            parameter_count=1,
            reasons=(
                "Single parameter change — verify out-of-sample performance before concluding",
            ),
        )
    return OverfittingRisk(
        level="high",
        parameter_count=n,
        reasons=(
            f"{n} parameters changed simultaneously — high risk of curve fitting",
            "Test each parameter independently in separate experiments",
        ),
    )


def _default_stop_conditions(plan_type: str) -> tuple[StopCondition, ...]:
    """Build standard stop conditions appropriate for the plan type."""
    max_exp = StopCondition(
        condition_type="max_experiments",
        value=_DEFAULT_MAX_EXPERIMENTS,
        description="Stop after 10 runs to prevent resource exhaustion",
    )
    min_pr = StopCondition(
        condition_type="min_pass_rate",
        value=_DEFAULT_MIN_PASS_RATE,
        description="Stop if pass_rate remains below 50% — hypothesis not viable",
    )
    if plan_type == "contradiction_replication":
        return (
            StopCondition(
                condition_type="max_experiments",
                value=5.0,
                description="5 runs are sufficient to resolve a contradiction",
            ),
        )
    if plan_type == "regime_filter":
        return (max_exp, min_pr)
    return (max_exp,)


def _make_tasks(
    plan_id: str,
    hypothesis_id: str,
    datasets: list[str],
    regime_filter: str,
    parameters: tuple[tuple[str, str], ...],
) -> tuple[ExperimentTask, ...]:
    tasks: list[ExperimentTask] = []
    for i, ds in enumerate(datasets[:_MAX_TASKS_PER_PLAN]):
        tasks.append(ExperimentTask(
            task_id=f"{plan_id}_t{i:02d}",
            hypothesis_id=hypothesis_id,
            instrument=_instrument_from_dataset(ds),
            dataset_id=ds,
            regime_filter=regime_filter,
            parameters=parameters,
        ))
    return tuple(tasks)


def _instruments_from_datasets(datasets: list[str], limit: int = 3) -> tuple[str, ...]:
    seen: list[str] = []
    for ds in datasets[:limit]:
        instr = _instrument_from_dataset(ds)
        if instr not in seen:
            seen.append(instr)
    return tuple(seen)


# ---------------------------------------------------------------------------
# Plan builders — one per trigger type
# ---------------------------------------------------------------------------

def _plan_from_underperformance(
    pattern: KnowledgePattern,
    datasets: list[str],
    idx: int,
) -> ExperimentPlan:
    """underperformance → explore whether the hypothesis performs in other regimes."""
    hyp_id = pattern.entities[0] if pattern.entities else "UNKNOWN"
    safe = hyp_id.lower().replace("-", "").replace(" ", "_")
    plan_id = f"plan_{idx:04d}_explore_{safe}"
    params: tuple[tuple[str, str], ...] = ()
    regime_filter = "RANGE"  # controlled alternative: test in RANGE regime

    return ExperimentPlan(
        plan_id=plan_id,
        plan_type="regime_exploration",
        objective=(
            f"Explore whether {hyp_id} underperformance is regime-specific"
        ),
        hypothesis_id=hyp_id,
        instruments=_instruments_from_datasets(datasets),
        datasets=tuple(datasets[:3]),
        regime_filter=regime_filter,
        tasks=_make_tasks(plan_id, hyp_id, datasets, regime_filter, params),
        parameters=params,
        expected_evidence=(
            f"Improved pass_rate when restricted to {regime_filter} regime",
            f"Regime-specific performance profile for {hyp_id}",
        ),
        rationale=(
            f"Pattern '{pattern.description}' detected with "
            f"{pattern.occurrence_count} occurrences "
            f"(confidence={pattern.confidence:.2f}). "
            f"Controlled experiment in RANGE regime tests whether underperformance "
            f"is universal or regime-dependent. "
            f"No parameter changes — hypothesis refinement only if regime difference confirmed."
        ),
        priority="medium",
        overfitting_risk=_overfitting_risk(params),
        stop_conditions=_default_stop_conditions("regime_exploration"),
        confidence=_evidence_confidence(pattern.occurrence_count),
        source_pattern_id=pattern.pattern_id,
    )


def _plan_from_negative_connection(
    conn: KnowledgeConnection,
    datasets: list[str],
    idx: int,
) -> ExperimentPlan:
    """negative connection → exclude the failing regime and measure impact."""
    hyp_id = conn.entity_a
    regime = conn.entity_b
    safe = hyp_id.lower().replace("-", "").replace(" ", "_")
    plan_id = f"plan_{idx:04d}_filter_{safe}_{regime.lower()}"
    params: tuple[tuple[str, str], ...] = ()
    regime_filter = f"EXCLUDE_{regime}"

    return ExperimentPlan(
        plan_id=plan_id,
        plan_type="regime_filter",
        objective=f"Test {hyp_id} performance with {regime} regime excluded",
        hypothesis_id=hyp_id,
        instruments=_instruments_from_datasets(datasets),
        datasets=tuple(datasets[:3]),
        regime_filter=regime_filter,
        tasks=_make_tasks(plan_id, hyp_id, datasets, regime_filter, params),
        parameters=params,
        expected_evidence=(
            f"Pass_rate above 0.50 when {regime} is excluded",
            f"Confirmation that {regime} is the primary failure driver for {hyp_id}",
        ),
        rationale=(
            f"Negative connection {hyp_id} ↔ {regime} detected "
            f"(strength={conn.strength:.2f}, support={conn.support_count} runs). "
            f"This is a hypothesis refinement experiment — not a proven strategy. "
            f"Adding a regime filter is one configuration change; "
            f"overfitting risk remains low."
        ),
        priority="high",
        overfitting_risk=_overfitting_risk(params),
        stop_conditions=_default_stop_conditions("regime_filter"),
        confidence=_evidence_confidence(conn.support_count),
        source_pattern_id=conn.connection_id,
    )


def _plan_from_contradiction(
    contradiction: str,
    datasets: list[str],
    idx: int,
) -> ExperimentPlan:
    """contradiction → clean controlled replication before any refinement."""
    # Extract hypothesis id: "Contradiction: H-X ... shows conflicting results"
    parts = contradiction.split(":")
    hyp_raw = parts[1].strip().split()[0] if len(parts) > 1 else "UNKNOWN"
    safe = hyp_raw.lower().replace("-", "").replace(" ", "_")
    plan_id = f"plan_{idx:04d}_replicate_{safe}"
    params: tuple[tuple[str, str], ...] = ()

    return ExperimentPlan(
        plan_id=plan_id,
        plan_type="contradiction_replication",
        objective=f"Resolve contradicting evidence: {contradiction}",
        hypothesis_id=hyp_raw,
        instruments=_instruments_from_datasets(datasets),
        datasets=tuple(datasets[:3]),
        regime_filter="",
        tasks=_make_tasks(plan_id, hyp_raw, datasets, "", params),
        parameters=params,
        expected_evidence=(
            "Consistent pass/fail outcome across ≥3 replications",
            "Identification of the confounding variable causing the contradiction",
        ),
        rationale=(
            f"Contradicting evidence detected: {contradiction}. "
            "A clean replication under identical conditions MUST precede any "
            "parameter or regime change. No modifications to hypothesis allowed "
            "until contradiction is resolved."
        ),
        priority="critical",
        overfitting_risk=_overfitting_risk(params),
        stop_conditions=_default_stop_conditions("contradiction_replication"),
        confidence=0.30,  # low — contradictions indicate unreliable existing evidence
        source_pattern_id="contradiction",
    )


def _plan_from_outperformance(
    pattern: KnowledgePattern,
    datasets: list[str],
    idx: int,
) -> ExperimentPlan:
    """outperformance → validate generalisability across more instruments."""
    hyp_id = pattern.entities[0] if pattern.entities else "UNKNOWN"
    safe = hyp_id.lower().replace("-", "").replace(" ", "_")
    plan_id = f"plan_{idx:04d}_expand_{safe}"
    params: tuple[tuple[str, str], ...] = ()

    return ExperimentPlan(
        plan_id=plan_id,
        plan_type="expansion",
        objective=(
            f"Validate {hyp_id} outperformance across additional instruments"
        ),
        hypothesis_id=hyp_id,
        instruments=_instruments_from_datasets(datasets, limit=5),
        datasets=tuple(datasets),
        regime_filter="",
        tasks=_make_tasks(plan_id, hyp_id, datasets, "", params),
        parameters=params,
        expected_evidence=(
            f"Consistent pass_rate > 0.70 across new instruments",
            f"Robust performance without regime restriction",
        ),
        rationale=(
            f"Pattern '{pattern.description}' "
            f"({pattern.occurrence_count} occurrences, "
            f"confidence={pattern.confidence:.2f}). "
            f"Expansion validates generalisability — "
            f"performance on familiar instruments does not guarantee robustness."
        ),
        priority="high",
        overfitting_risk=_overfitting_risk(params),
        stop_conditions=_default_stop_conditions("expansion"),
        confidence=_evidence_confidence(pattern.occurrence_count),
        source_pattern_id=pattern.pattern_id,
    )


# ---------------------------------------------------------------------------
# Core planner logic
# ---------------------------------------------------------------------------

def _plans_from_snapshot(
    snapshot: KnowledgeSnapshot,
    datasets: list[str],
) -> list[ExperimentPlan]:
    """Derive experiment plans from KnowledgeSnapshot using deterministic rules."""
    plans: list[ExperimentPlan] = []
    idx = 0

    # 1. Underperformance patterns → regime exploration
    for pattern in snapshot.patterns:
        if pattern.pattern_type == "underperformance":
            idx += 1
            plans.append(_plan_from_underperformance(pattern, datasets, idx))

    # 2. Negative connections → regime filter
    for conn in snapshot.connections:
        if conn.relation == "negative":
            idx += 1
            plans.append(_plan_from_negative_connection(conn, datasets, idx))

    # 3. Contradictions → controlled replication (highest priority)
    for contradiction in snapshot.contradictions:
        idx += 1
        plans.append(_plan_from_contradiction(contradiction, datasets, idx))

    # 4. Outperformance patterns → expansion
    for pattern in snapshot.patterns:
        if pattern.pattern_type == "outperformance":
            idx += 1
            plans.append(_plan_from_outperformance(pattern, datasets, idx))

    return plans


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _write_plan(data_dir: Path, plan: ExperimentPlan) -> Path:
    out = data_dir / "research_programs" / "plans"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{plan.plan_id}.json"

    payload = {
        "plan_id": plan.plan_id,
        "plan_type": plan.plan_type,
        "objective": plan.objective,
        "hypothesis_id": plan.hypothesis_id,
        "instruments": list(plan.instruments),
        "datasets": list(plan.datasets),
        "regime_filter": plan.regime_filter,
        "parameters": dict(plan.parameters),
        "expected_evidence": list(plan.expected_evidence),
        "rationale": plan.rationale,
        "priority": plan.priority,
        "overfitting_risk": {
            "level": plan.overfitting_risk.level,
            "parameter_count": plan.overfitting_risk.parameter_count,
            "reasons": list(plan.overfitting_risk.reasons),
        },
        "stop_conditions": [
            {
                "condition_type": sc.condition_type,
                "value": sc.value,
                "description": sc.description,
            }
            for sc in plan.stop_conditions
        ],
        "confidence": plan.confidence,
        "source_pattern_id": plan.source_pattern_id,
        "tasks": [
            {
                "task_id": t.task_id,
                "hypothesis_id": t.hypothesis_id,
                "instrument": t.instrument,
                "dataset_id": t.dataset_id,
                "regime_filter": t.regime_filter,
                "parameters": dict(t.parameters),
            }
            for t in plan.tasks
        ],
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# ExperimentPlanner
# ---------------------------------------------------------------------------

class ExperimentPlanner:
    """Layer 3 RESEARCH Agent — deterministic experiment proposal generator.

    Reads KnowledgeSnapshot and datasets list; emits ExperimentPlan objects.
    Does NOT run experiments.  Does NOT modify Research Service.
    Does NOT make autonomous decisions.

    Plans are saved to {data_dir}/research_programs/plans/{plan_id}.json and
    returned as tuple[ExperimentPlan, ...] in AgentResult.output.
    """

    agent_id = _AGENT_ID
    agent_type = _AGENT_TYPE
    version = _VERSION

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def run(
        self,
        knowledge_snapshot: KnowledgeSnapshot,
        datasets: list[str],
        campaign_id: str = "default",
        _clock: Optional[Callable[[], datetime]] = None,
    ) -> AgentResult:
        """Generate experiment plans from a KnowledgeSnapshot.

        Parameters
        ----------
        knowledge_snapshot: output of KnowledgeAgent — the evidence base
        datasets:           list of available dataset_ids to assign to tasks
        campaign_id:        label for this planning session (used in input_summary)
        _clock:             injected clock for deterministic created_at
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")

        plans = _plans_from_snapshot(knowledge_snapshot, datasets)

        for plan in plans:
            _write_plan(self._data_dir, plan)

        evidence = [
            EvidenceRef(
                source=f"knowledge/{knowledge_snapshot.campaign_id}",
                reference=knowledge_snapshot.snapshot_id,
                timestamp=created_at,
            )
        ]

        conf_value = (
            round(sum(p.confidence for p in plans) / len(plans), 6)
            if plans else 0.0
        )

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"planning {knowledge_snapshot.campaign_id}: "
                f"{len(knowledge_snapshot.patterns)} patterns "
                f"{len(knowledge_snapshot.connections)} connections "
                f"{len(knowledge_snapshot.contradictions)} contradictions "
                f"→ {len(plans)} plans"
            ),
            output=tuple(plans),
            evidence=tuple(evidence),
            confidence=ConfidenceScore(
                value=conf_value,
                reason=(
                    f"{len(plans)} plans from "
                    f"{len(knowledge_snapshot.patterns)} patterns + "
                    f"{len(knowledge_snapshot.connections)} connections + "
                    f"{len(knowledge_snapshot.contradictions)} contradictions"
                ),
            ),
            created_at=created_at,
        )
