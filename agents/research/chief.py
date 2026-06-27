"""ChiefScientist v1 — Layer 3 CHIEF_SCIENTIST Agent.

Rule-based coordinator for the Intelligence Era research process.
Reads KnowledgeSnapshot and ExperimentPlans; produces ResearchDecision objects.

Does NOT: generate hypotheses, call Research Service, modify plans, make trading decisions.
Does NOT: use ML or LLM — all rules are deterministic.

Rule table:
  R01  STOP_RESEARCH_LINE    critical  — previous ValidationBatchResult has stop_triggered=True
  R02  ARCHIVE_HYPOTHESIS    high      — hypothesis has ≥N FAIL facts and low avg_pass_rate
  R03  RUN_PLAN (critical)   critical  — contradictions exist and contradiction_replication plan available
  R04  RUN_PLAN (high)       high      — negative connection ≥0.6 and matching regime_filter plan
  R05  REQUEST_MORE_EVIDENCE medium    — hypothesis has <N KnowledgeFacts (too few runs)
  R06  SKIP_PLAN             low       — plan has high overfitting_risk and policy does not allow
  R07  RUN_PLAN (expansion)  high      — outperformance plan with sufficient confidence

Decisions are sorted critical → high → medium → low, then capped by policy.max_decisions_per_run.
Decisions are written individually to {data_dir}/research_programs/decisions/{decision_id}.json.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.models import (
    AgentResult,
    ConfidenceScore,
    DecisionReason,
    EvidenceRef,
    ExperimentPlan,
    KnowledgeFact,
    KnowledgeSnapshot,
    ResearchDecision,
    ResearchPolicy,
    ValidationBatchResult,
)

_AGENT_ID = "chief-scientist"
_AGENT_TYPE = "CHIEF_SCIENTIST"
_VERSION = "1.0"

# Rule IDs — stable constants for tests and auditing
_R01_STOP = "R01_stop_condition_triggered"
_R02_ARCHIVE = "R02_archive_hypothesis"
_R03_CONTRADICTION = "R03_contradiction_replication"
_R04_NEGATIVE_CONN = "R04_negative_connection_filter"
_R05_EVIDENCE = "R05_insufficient_evidence"
_R06_SKIP_RISK = "R06_skip_high_overfitting_risk"
_R07_EXPANSION = "R07_outperformance_expansion"

_PRIORITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_NEGATIVE_CONN_STRENGTH_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_id(raw: str) -> str:
    """Lowercase, strip hyphens/spaces for use in decision_id."""
    return raw.lower().replace("-", "").replace(" ", "_")


def _hypothesis_stats(
    facts: tuple[KnowledgeFact, ...],
) -> tuple[dict[str, int], dict[str, float]]:
    """Compute (fail_counts, avg_pass_rates) per hypothesis_id from KnowledgeFacts.

    fail_counts:    number of KnowledgeFacts with passed=False per hypothesis
    avg_pass_rates: mean of fact.value where metric="pass_rate" per hypothesis
    """
    fails: dict[str, int] = {}
    rate_sums: dict[str, list[float]] = {}

    for fact in facts:
        if not fact.hypothesis_id:
            continue
        hyp = fact.hypothesis_id
        if fact.passed is False:
            fails[hyp] = fails.get(hyp, 0) + 1
        if fact.metric == "pass_rate" and not math.isnan(fact.value):
            rate_sums.setdefault(hyp, []).append(fact.value)

    avg_rates = {
        hyp: sum(vals) / len(vals)
        for hyp, vals in rate_sums.items()
    }
    return fails, avg_rates


def _fact_counts_per_hypothesis(facts: tuple[KnowledgeFact, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fact in facts:
        if fact.hypothesis_id:
            counts[fact.hypothesis_id] = counts.get(fact.hypothesis_id, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Rule evaluators
# ---------------------------------------------------------------------------

def _r01_stop_conditions(
    previous_results: list[ValidationBatchResult],
    idx_start: int,
    created_at: str,
) -> list[ResearchDecision]:
    """R01: STOP_RESEARCH_LINE — stop condition already triggered in a previous run."""
    decisions = []
    idx = idx_start
    for result in previous_results:
        if result.stop_triggered:
            idx += 1
            decisions.append(ResearchDecision(
                decision_id=f"dec_{idx:04d}_stop_{_safe_id(result.plan_id)[:20]}",
                decision_type="STOP_RESEARCH_LINE",
                priority="critical",
                plan_id=result.plan_id,
                hypothesis_id="",
                reason=DecisionReason(
                    rule_id=_R01_STOP,
                    description=(
                        f"Stop condition already triggered for plan {result.plan_id}: "
                        f"{result.stop_reason}"
                    ),
                    evidence=(
                        f"plan={result.plan_id}",
                        f"stop_reason={result.stop_reason}",
                        f"completed_tasks={result.completed_tasks}",
                    ),
                ),
                confidence=1.0,
                created_at=created_at,
            ))
    return decisions


def _r02_archive_hypothesis(
    snapshot: KnowledgeSnapshot,
    policy: ResearchPolicy,
    idx_start: int,
    created_at: str,
) -> list[ResearchDecision]:
    """R02: ARCHIVE_HYPOTHESIS — hypothesis repeatedly fails with very low pass_rate."""
    decisions = []
    idx = idx_start
    fail_counts, avg_rates = _hypothesis_stats(snapshot.facts)

    for hyp_id, fail_count in sorted(fail_counts.items()):
        avg_pr = avg_rates.get(hyp_id, 0.0)
        if (
            fail_count >= policy.archive_fail_threshold
            and avg_pr < policy.archive_pass_rate_ceiling
        ):
            idx += 1
            decisions.append(ResearchDecision(
                decision_id=f"dec_{idx:04d}_archive_{_safe_id(hyp_id)}",
                decision_type="ARCHIVE_HYPOTHESIS",
                priority="high",
                plan_id="",
                hypothesis_id=hyp_id,
                reason=DecisionReason(
                    rule_id=_R02_ARCHIVE,
                    description=(
                        f"{hyp_id} archived: {fail_count} FAIL facts, "
                        f"avg_pass_rate={avg_pr:.3f} "
                        f"(threshold≥{policy.archive_fail_threshold}, "
                        f"ceiling<{policy.archive_pass_rate_ceiling})"
                    ),
                    evidence=(
                        f"fail_count={fail_count}",
                        f"avg_pass_rate={avg_pr:.3f}",
                        f"archive_fail_threshold={policy.archive_fail_threshold}",
                        f"archive_pass_rate_ceiling={policy.archive_pass_rate_ceiling}",
                    ),
                ),
                confidence=0.9,
                created_at=created_at,
            ))
    return decisions


def _r03_contradiction_replication(
    snapshot: KnowledgeSnapshot,
    plans: list[ExperimentPlan],
    idx_start: int,
    created_at: str,
) -> list[ResearchDecision]:
    """R03: RUN_PLAN (critical) — contradiction detected, replication plan available."""
    if not snapshot.contradictions:
        return []

    contradiction_plans = [p for p in plans if p.plan_type == "contradiction_replication"]
    if not contradiction_plans:
        return []

    decisions = []
    idx = idx_start
    for plan in contradiction_plans:
        idx += 1
        contra_sample = tuple(snapshot.contradictions[:3])
        decisions.append(ResearchDecision(
            decision_id=f"dec_{idx:04d}_run_contradiction_{_safe_id(plan.hypothesis_id)}",
            decision_type="RUN_PLAN",
            priority="critical",
            plan_id=plan.plan_id,
            hypothesis_id=plan.hypothesis_id,
            reason=DecisionReason(
                rule_id=_R03_CONTRADICTION,
                description=(
                    f"Contradiction detected — run {plan.plan_id} "
                    f"to resolve {len(snapshot.contradictions)} conflict(s)"
                ),
                evidence=contra_sample + (f"plan={plan.plan_id}",),
            ),
            confidence=plan.confidence,
            created_at=created_at,
        ))
    return decisions


def _r04_negative_connection_filter(
    snapshot: KnowledgeSnapshot,
    plans: list[ExperimentPlan],
    idx_start: int,
    created_at: str,
) -> list[ResearchDecision]:
    """R04: RUN_PLAN (high) — strong negative connection found, regime_filter plan available."""
    strong_negatives = [
        c for c in snapshot.connections
        if c.relation == "negative" and c.strength >= _NEGATIVE_CONN_STRENGTH_THRESHOLD
    ]
    if not strong_negatives:
        return []

    decisions = []
    idx = idx_start
    for conn in sorted(strong_negatives, key=lambda c: -c.strength):
        matching = [
            p for p in plans
            if p.plan_type == "regime_filter" and p.hypothesis_id == conn.entity_a
        ]
        for plan in matching:
            idx += 1
            decisions.append(ResearchDecision(
                decision_id=f"dec_{idx:04d}_run_filter_{_safe_id(conn.entity_a)}",
                decision_type="RUN_PLAN",
                priority="high",
                plan_id=plan.plan_id,
                hypothesis_id=plan.hypothesis_id,
                reason=DecisionReason(
                    rule_id=_R04_NEGATIVE_CONN,
                    description=(
                        f"Negative connection {conn.entity_a}↔{conn.entity_b} "
                        f"(strength={conn.strength:.2f}, support={conn.support_count}) "
                        f"→ test regime filter {plan.plan_id}"
                    ),
                    evidence=(
                        f"connection={conn.connection_id}",
                        f"entity_a={conn.entity_a}",
                        f"entity_b={conn.entity_b}",
                        f"strength={conn.strength:.2f}",
                        f"support_count={conn.support_count}",
                        f"plan={plan.plan_id}",
                    ),
                ),
                confidence=plan.confidence,
                created_at=created_at,
            ))
    return decisions


def _r05_insufficient_evidence(
    snapshot: KnowledgeSnapshot,
    plans: list[ExperimentPlan],
    policy: ResearchPolicy,
    idx_start: int,
    created_at: str,
) -> list[ResearchDecision]:
    """R05: REQUEST_MORE_EVIDENCE — hypothesis has too few KnowledgeFacts to decide."""
    fact_counts = _fact_counts_per_hypothesis(snapshot.facts)
    decisions = []
    idx = idx_start
    seen_hypotheses: set[str] = set()

    for plan in plans:
        hyp_id = plan.hypothesis_id
        if hyp_id in seen_hypotheses:
            continue
        count = fact_counts.get(hyp_id, 0)
        if count < policy.min_runs_for_evidence:
            seen_hypotheses.add(hyp_id)
            idx += 1
            decisions.append(ResearchDecision(
                decision_id=f"dec_{idx:04d}_evidence_{_safe_id(hyp_id)}",
                decision_type="REQUEST_MORE_EVIDENCE",
                priority="medium",
                plan_id=plan.plan_id,
                hypothesis_id=hyp_id,
                reason=DecisionReason(
                    rule_id=_R05_EVIDENCE,
                    description=(
                        f"{hyp_id} has {count} facts — need "
                        f"{policy.min_runs_for_evidence} before deciding. "
                        f"Run {plan.plan_id} to gather baseline evidence."
                    ),
                    evidence=(
                        f"fact_count={count}",
                        f"min_runs_for_evidence={policy.min_runs_for_evidence}",
                        f"plan={plan.plan_id}",
                    ),
                ),
                confidence=0.5,
                created_at=created_at,
            ))
    return decisions


def _r06_skip_high_risk(
    plans: list[ExperimentPlan],
    policy: ResearchPolicy,
    idx_start: int,
    created_at: str,
) -> list[ResearchDecision]:
    """R06: SKIP_PLAN — high overfitting_risk and policy.allow_high_risk=False."""
    if policy.allow_high_risk:
        return []

    decisions = []
    idx = idx_start
    for plan in plans:
        if plan.overfitting_risk.level == "high":
            idx += 1
            decisions.append(ResearchDecision(
                decision_id=f"dec_{idx:04d}_skip_{_safe_id(plan.plan_id)[:20]}",
                decision_type="SKIP_PLAN",
                priority="low",
                plan_id=plan.plan_id,
                hypothesis_id=plan.hypothesis_id,
                reason=DecisionReason(
                    rule_id=_R06_SKIP_RISK,
                    description=(
                        f"Plan {plan.plan_id} skipped — high overfitting_risk "
                        f"({plan.overfitting_risk.parameter_count} parameter(s) changed). "
                        f"Set policy.allow_high_risk=True to override."
                    ),
                    evidence=(
                        f"overfitting_level={plan.overfitting_risk.level}",
                        f"parameter_count={plan.overfitting_risk.parameter_count}",
                        f"plan={plan.plan_id}",
                    ),
                ),
                confidence=0.9,
                created_at=created_at,
            ))
    return decisions


def _r07_outperformance_expansion(
    plans: list[ExperimentPlan],
    policy: ResearchPolicy,
    idx_start: int,
    created_at: str,
) -> list[ResearchDecision]:
    """R07: RUN_PLAN (high) — outperformance pattern confirmed, expand to more instruments."""
    decisions = []
    idx = idx_start
    for plan in plans:
        if plan.plan_type == "expansion" and plan.confidence >= policy.min_confidence:
            idx += 1
            decisions.append(ResearchDecision(
                decision_id=f"dec_{idx:04d}_run_expand_{_safe_id(plan.hypothesis_id)}",
                decision_type="RUN_PLAN",
                priority="high",
                plan_id=plan.plan_id,
                hypothesis_id=plan.hypothesis_id,
                reason=DecisionReason(
                    rule_id=_R07_EXPANSION,
                    description=(
                        f"Outperformance pattern — expand {plan.hypothesis_id} "
                        f"to additional instruments (confidence={plan.confidence:.2f})"
                    ),
                    evidence=(
                        f"plan={plan.plan_id}",
                        f"confidence={plan.confidence:.2f}",
                        f"min_confidence_threshold={policy.min_confidence}",
                    ),
                ),
                confidence=plan.confidence,
                created_at=created_at,
            ))
    return decisions


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def _evaluate_rules(
    snapshot: KnowledgeSnapshot,
    plans: list[ExperimentPlan],
    previous_results: list[ValidationBatchResult],
    policy: ResearchPolicy,
    created_at: str,
) -> list[ResearchDecision]:
    """Apply all rules in order; sort by priority; cap by policy.max_decisions_per_run."""
    decisions: list[ResearchDecision] = []

    # R01 — Stop condition (no idx sharing issue; each rule has its own counter)
    decisions += _r01_stop_conditions(previous_results, len(decisions), created_at)
    decisions += _r02_archive_hypothesis(snapshot, policy, len(decisions), created_at)
    decisions += _r03_contradiction_replication(snapshot, plans, len(decisions), created_at)
    decisions += _r04_negative_connection_filter(snapshot, plans, len(decisions), created_at)
    decisions += _r05_insufficient_evidence(snapshot, plans, policy, len(decisions), created_at)
    decisions += _r06_skip_high_risk(plans, policy, len(decisions), created_at)
    decisions += _r07_outperformance_expansion(plans, policy, len(decisions), created_at)

    # Sort: critical → high → medium → low; stable (insertion order within same priority)
    decisions.sort(key=lambda d: (_PRIORITY_ORDER.get(d.priority, 4), d.decision_id))

    return decisions[: policy.max_decisions_per_run]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _write_decision(data_dir: Path, decision: ResearchDecision) -> Path:
    out = data_dir / "research_programs" / "decisions"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{decision.decision_id}.json"
    payload = {
        "decision_id": decision.decision_id,
        "decision_type": decision.decision_type,
        "priority": decision.priority,
        "plan_id": decision.plan_id,
        "hypothesis_id": decision.hypothesis_id,
        "reason": {
            "rule_id": decision.reason.rule_id,
            "description": decision.reason.description,
            "evidence": list(decision.reason.evidence),
        },
        "confidence": decision.confidence,
        "created_at": decision.created_at,
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# ChiefScientist
# ---------------------------------------------------------------------------

class ChiefScientist:
    """Layer 3 CHIEF_SCIENTIST Agent — rule-based research coordinator.

    Reads accumulated evidence (KnowledgeSnapshot) and proposed plans
    (list[ExperimentPlan]) together with prior execution outcomes
    (list[ValidationBatchResult]) and emits prioritised ResearchDecision objects.

    Seven deterministic rules — no ML, no LLM, no trading decisions.
    Decisions are saved individually and returned as tuple[ResearchDecision, ...].
    """

    agent_id = _AGENT_ID
    agent_type = _AGENT_TYPE
    version = _VERSION

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def run(
        self,
        knowledge_snapshot: KnowledgeSnapshot,
        plans: list[ExperimentPlan],
        previous_results: Optional[list[ValidationBatchResult]] = None,
        policy: Optional[ResearchPolicy] = None,
        campaign_id: str = "default",
        _clock: Optional[Callable[[], datetime]] = None,
    ) -> AgentResult:
        """Evaluate all research rules and produce prioritised decisions.

        Parameters
        ----------
        knowledge_snapshot: output of KnowledgeAgent — the evidence base.
        plans:              ExperimentPlans from ExperimentPlanner.
        previous_results:   ValidationBatchResult from prior ValidationAgentAdapter runs.
        policy:             rule thresholds (defaults to conservative ResearchPolicy()).
        campaign_id:        label for logging.
        _clock:             injected clock for deterministic created_at.
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")
        eff_policy = policy if policy is not None else ResearchPolicy()
        eff_results = previous_results or []

        decisions = _evaluate_rules(
            snapshot=knowledge_snapshot,
            plans=plans,
            previous_results=eff_results,
            policy=eff_policy,
            created_at=created_at,
        )

        for dec in decisions:
            _write_decision(self._data_dir, dec)

        evidence = EvidenceRef(
            source=f"knowledge/{knowledge_snapshot.campaign_id}",
            reference=knowledge_snapshot.snapshot_id,
            timestamp=created_at,
        )

        n_facts = len(knowledge_snapshot.facts)
        n_plans = len(plans)
        n_prev = len(eff_results)

        conf_value = (
            round(
                sum(d.confidence for d in decisions) / len(decisions), 6
            )
            if decisions else 0.0
        )

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"{campaign_id}: "
                f"{n_facts} facts "
                f"{n_plans} plans "
                f"{len(knowledge_snapshot.contradictions)} contradictions "
                f"{n_prev} prior_results "
                f"→ {len(decisions)} decisions"
            ),
            output=tuple(decisions),
            evidence=(evidence,),
            confidence=ConfidenceScore(
                value=max(0.0, min(1.0, conf_value)),
                reason=(
                    f"{len(decisions)} decisions from "
                    f"{n_facts} facts / {n_plans} plans"
                ),
            ),
            created_at=created_at,
        )
