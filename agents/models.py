"""Domain models shared across all Intelligence Era agents.

All models are frozen dataclasses — immutable and serialisable.
MacroSnapshot contains a tuple[tuple[str, int], ...] for missing_values
to remain hashable (dict fields would break hashability).

No external dependencies: stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class EvidenceRef:
    """Pointer to the evidence backing an agent's output.

    source:    human-readable name of the data origin
               ("MOEX ISS API", "fixture", "calculation")
    reference: URL, file path, or free-form description
    timestamp: ISO-format datetime string — when evidence was collected
    """

    source: str
    reference: str
    timestamp: str


@dataclass(frozen=True)
class ConfidenceScore:
    """Normalised confidence in an agent's output.

    value: float in [0.0, 1.0]
    reason: short explanation of the score
    """

    value: float
    reason: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(
                f"ConfidenceScore.value must be in [0.0, 1.0], got {self.value}"
            )


@dataclass(frozen=True)
class AgentResult:
    """Universal envelope returned by every agent.

    Carries identity, provenance, and the domain-specific payload (output).
    Matches the agent contract from docs/30_INTELLIGENCE_ARCHITECTURE.md.
    """

    agent_id: str
    agent_type: str        # "DATA" | "ANALYSIS" | "RESEARCH" | "KNOWLEDGE" | "CHIEF_SCIENTIST"
    version: str
    input_summary: str     # brief description of what the agent consumed
    output: object         # domain-specific payload (e.g. DatasetManifest)
    evidence: tuple[EvidenceRef, ...]
    confidence: ConfidenceScore
    created_at: str        # ISO-format timestamp from injected clock


@dataclass(frozen=True)
class MarketSnapshot:
    """Lightweight summary of available market data — not the data itself."""

    ticker: str
    timeframe: str
    bar_count: int
    date_from: str
    date_to: str
    session_filter: str    # "main" | "full"


@dataclass(frozen=True)
class MacroSeries:
    """One macro time series stored by MacroAgent.

    path points to the CSV file in data/context/macro/{period}/{symbol}_{timeframe}.csv.
    CSV columns: date, open, high, low, close, volume
    """

    symbol: str        # "IMOEX" | "USDRUB" | "RGBI"
    timeframe: str     # "1d" | "1h"
    date_from: str
    date_to: str
    value_count: int
    path: str          # absolute path to saved CSV


@dataclass(frozen=True)
class MacroSnapshot:
    """Output of MacroAgent — a collection of macro time series.

    missing_values: tuple of (symbol, 0) pairs for symbols that returned
    no data. Use dict(snapshot.missing_values) to convert to dict.
    Stored as tuple-of-tuples to keep MacroSnapshot hashable.
    """

    snapshot_id: str
    period: str
    observations: tuple[MacroSeries, ...]
    source_refs: tuple[EvidenceRef, ...]
    missing_values: tuple[tuple[str, int], ...]   # (symbol, missing_count)
    confidence: ConfidenceScore


@dataclass(frozen=True)
class KnowledgeFact:
    """One structured fact extracted from research artifacts.

    source_type: "research_report" | "knowledge_base" | "regime_snapshot" | "correlation_snapshot"
    hypothesis_id: "" if not hypothesis-related
    regime:  RegimeLabel string or "" when no regime context
    metric:  "pass_rate" | "sharpe" | "correlation" | "realized_vol" | "kb_finding"
    value:   numeric; math.nan if not applicable
    passed:  True = positive outcome, False = negative, None = not applicable
    tags:    feature names, categories — any free-form strings
    """

    fact_id: str
    source_type: str
    source_ref: str
    hypothesis_id: str
    instrument: str
    period: str
    regime: str
    metric: str
    value: float
    passed: Optional[bool]
    confidence: float
    tags: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeConnection:
    """A link between two knowledge entities derived from accumulated facts.

    entity_a / entity_b: hypothesis IDs, regime labels, or instrument names
    relation: "positive" | "negative" | "neutral" | "similar" | "contradicts"
    strength: 0.0–1.0 — how consistently the relation holds across facts
    evidence: fact_ids that support this connection
    """

    connection_id: str
    entity_a: str
    entity_b: str
    relation: str
    strength: float
    support_count: int
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgePattern:
    """A recurring pattern discovered across multiple KnowledgeFact entries.

    pattern_type:
      "regime_hypothesis"  — specific regime correlates with consistent outcome
      "underperformance"   — hypothesis avg pass_rate < threshold
      "outperformance"     — hypothesis avg pass_rate > threshold
      "contradiction"      — conflicting outcomes for the same conditions
    supporting_facts:   fact_ids that confirm the pattern
    contradicting_facts: fact_ids that go against the pattern
    """

    pattern_id: str
    description: str
    pattern_type: str
    entities: tuple[str, ...]
    occurrence_count: int
    confidence: float
    supporting_facts: tuple[str, ...]
    contradicting_facts: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeSnapshot:
    """Output of KnowledgeAgent — full knowledge analysis for one campaign.

    strong_facts:   fact_ids with confidence >= 0.7
    weak_facts:     fact_ids with confidence < 0.4
    contradictions: human-readable descriptions of conflicting evidence
    recommendations: suggestions for future research directions
    Saved to knowledge/snapshots/{campaign_id}.json
    """

    snapshot_id: str
    campaign_id: str
    facts: tuple[KnowledgeFact, ...]
    connections: tuple[KnowledgeConnection, ...]
    patterns: tuple[KnowledgePattern, ...]
    strong_facts: tuple[str, ...]
    weak_facts: tuple[str, ...]
    contradictions: tuple[str, ...]
    recommendations: tuple[str, ...]
    source_refs: tuple[EvidenceRef, ...]
    confidence: ConfidenceScore


@dataclass(frozen=True)
class StopCondition:
    """Criterion for terminating an experiment before exhausting all planned runs.

    condition_type: "max_experiments" | "min_pass_rate" | "max_drawdown" | "time_limit"
    value:          numeric threshold at which the experiment stops
    description:    human-readable rationale for this guard rail
    """

    condition_type: str
    value: float
    description: str


@dataclass(frozen=True)
class OverfittingRisk:
    """Overfitting risk assessment attached to every ExperimentPlan.

    level:           "low" | "medium" | "high"
    parameter_count: number of hypothesis parameters being changed simultaneously
                     (>1 → high risk of curve fitting)
    reasons:         explicit risk factors justifying the level
    """

    level: str
    parameter_count: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentTask:
    """One atomic experiment run within an ExperimentPlan.

    parameters:    (name, value_str) pairs — values as strings for serialisability
    regime_filter: "" if no filter; e.g. "EXCLUDE_TREND_UP" for regime-filtered runs
    """

    task_id: str
    hypothesis_id: str
    instrument: str
    dataset_id: str
    regime_filter: str
    parameters: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ExperimentPlan:
    """A reproducible experiment proposal generated by ExperimentPlanner.

    NOT a trading signal. NOT a strategy selection. A structured, documented
    proposal for the next controlled experiment derived from KnowledgeSnapshot.

    plan_type:
      "regime_exploration"       — underperformance pattern → explore alternative regimes
      "regime_filter"            — negative connection → exclude the failing regime
      "contradiction_replication"— contradicting evidence → clean controlled replication
      "expansion"                — outperformance pattern → broaden instrument coverage

    priority:    "low" | "medium" | "high" | "critical"
    confidence:  0.0–1.0 derived from evidence support_count
    source_pattern_id: pattern_id or connection_id that triggered this plan
    """

    plan_id: str
    plan_type: str
    objective: str
    hypothesis_id: str
    instruments: tuple[str, ...]
    datasets: tuple[str, ...]
    regime_filter: str
    tasks: tuple[ExperimentTask, ...]
    parameters: tuple[tuple[str, str], ...]
    expected_evidence: tuple[str, ...]
    rationale: str
    priority: str
    overfitting_risk: OverfittingRisk
    stop_conditions: tuple[StopCondition, ...]
    confidence: float
    source_pattern_id: str


@dataclass(frozen=True)
class ValidationTaskResult:
    """Result for one ExperimentTask executed (or dry-run) by ValidationAgentAdapter.

    status:
      "dry_run" — plan was validated but task was not executed (default safe mode)
      "success" — Research Service completed with exit_code=0
      "error"   — Research Service raised an exception or returned non-zero
      "stopped" — task was not reached because a stop_condition fired
      "blocked" — task was not reached because high overfitting_risk was not overridden

    exit_code:
       0  — success
       1  — error from Research Service
      -1  — not run (dry_run)
      -2  — stopped by stop_condition
      -3  — blocked by safety guard

    pass_rate: None when status != "success" or when Research Service did not
               produce a measurable pass_rate for this single run.
    report_path: absolute path to the Research Report JSON, "" when not produced.
    """

    task_id: str
    hypothesis_id: str
    dataset_id: str
    status: str
    exit_code: int
    pass_rate: Optional[float]
    report_path: str
    error: str
    duration_seconds: float


@dataclass(frozen=True)
class ValidationRun:
    """Full execution trace for one ExperimentPlan run by ValidationAgentAdapter.

    mode: "dry_run" | "execute" | "fixture"
    stop_triggered: True if any stop_condition fired before all tasks completed.
    stop_reason:    human-readable description of the triggered stop_condition, "" otherwise.
    Saved to research_programs/validation_runs/{run_id}.json
    """

    run_id: str
    plan_id: str
    campaign_id: str
    mode: str
    task_results: tuple[ValidationTaskResult, ...]
    stop_triggered: bool
    stop_reason: str
    created_at: str


@dataclass(frozen=True)
class ValidationBatchResult:
    """Aggregate statistics over all ValidationTaskResult entries for one plan run.

    Output of ValidationAgentAdapter — returned as AgentResult.output.
    report_paths: paths to all Research Report JSON files produced (empty in dry_run).
    validation_run_path: path to the ValidationRun JSON.
    avg_pass_rate: None when no tasks reported a pass_rate.
    """

    batch_id: str
    plan_id: str
    campaign_id: str
    total_tasks: int
    completed_tasks: int
    stopped_tasks: int
    error_tasks: int
    dry_run_tasks: int
    blocked_tasks: int
    avg_pass_rate: Optional[float]
    stop_triggered: bool
    stop_reason: str
    report_paths: tuple[str, ...]
    validation_run_path: str
    created_at: str


@dataclass(frozen=True)
class DecisionReason:
    """Explanation for one ResearchDecision — which rule fired and why.

    rule_id:     stable identifier for the triggered rule (e.g. "R01_stop_condition")
    description: human-readable explanation of the decision
    evidence:    tuple of supporting facts (fact_id, connection_id, pass_rate strings, etc.)
    """

    rule_id: str
    description: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class ResearchPolicy:
    """Configuration for ChiefScientist rule evaluation.

    All fields have conservative defaults — no ML, no LLM, no trading.
    allow_high_risk:          if True, high overfitting_risk plans are not skipped.
    min_confidence:           plans below this threshold are skipped (R06 complement).
    archive_fail_threshold:   consecutive FAIL KnowledgeFacts to trigger ARCHIVE_HYPOTHESIS.
    archive_pass_rate_ceiling: avg pass_rate must be below this to trigger archive.
    min_runs_for_evidence:    min KnowledgeFact count before a RUN_PLAN decision is allowed.
    max_decisions_per_run:    cap on total decisions returned (highest priority wins).
    """

    allow_high_risk: bool = False
    min_confidence: float = 0.3
    archive_fail_threshold: int = 3
    archive_pass_rate_ceiling: float = 0.2
    min_runs_for_evidence: int = 3
    max_decisions_per_run: int = 10


@dataclass(frozen=True)
class ResearchDecision:
    """A single research decision produced by ChiefScientist.

    decision_type:
      "RUN_PLAN"             — execute a specific ExperimentPlan next
      "SKIP_PLAN"            — skip a plan (high risk, low confidence, or policy)
      "ARCHIVE_HYPOTHESIS"   — hypothesis has failed too many times — stop pursuing it
      "REQUEST_MORE_EVIDENCE"— insufficient data to decide; run more baseline experiments
      "STOP_RESEARCH_LINE"   — stop condition already triggered — do not continue

    priority: "low" | "medium" | "high" | "critical"
    plan_id:  ExperimentPlan.plan_id this decision refers to; "" if not plan-specific.
    hypothesis_id: hypothesis this decision refers to; "" if not hypothesis-specific.
    confidence: 0.0–1.0 derived from evidence count and rule certainty.

    Saved individually to research_programs/decisions/{decision_id}.json.
    """

    decision_id: str
    decision_type: str
    priority: str
    plan_id: str
    hypothesis_id: str
    reason: DecisionReason
    confidence: float
    created_at: str


class RegimeLabel:
    """String constants for every possible regime label.

    Three regime dimensions:
      trend      — TREND_UP | TREND_DOWN | RANGE
      volatility — LOW_VOL  | NORMAL_VOL | HIGH_VOL
      risk       — RISK_ON  | RISK_OFF   | NEUTRAL
    """

    # Trend
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"

    # Volatility
    LOW_VOL = "LOW_VOL"
    NORMAL_VOL = "NORMAL_VOL"
    HIGH_VOL = "HIGH_VOL"

    # Risk (macro-derived)
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"

    _TREND = frozenset([TREND_UP, TREND_DOWN, RANGE])
    _VOLATILITY = frozenset([LOW_VOL, NORMAL_VOL, HIGH_VOL])
    _RISK = frozenset([RISK_ON, RISK_OFF, NEUTRAL])


@dataclass(frozen=True)
class RegimeSegment:
    """One classified window in a regime analysis.

    regime_type: "trend" | "volatility" | "risk"
    metrics:     (name, value) pairs — all named indicators used for classification
    evidence:    short text strings explaining why this label was assigned
    confidence:  0.0–1.0, derived from signal strength
    """

    regime_type: str
    label: str
    date_from: str
    date_to: str
    confidence: float
    metrics: tuple[tuple[str, float], ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RegimeSnapshot:
    """Output of RegimeDetectionAgent.

    segments contains RegimeSegment entries for each regime type × each
    time window in the period.
    Saved to data/context/regime/{instrument.lower()}_{period}.json.
    """

    snapshot_id: str
    instrument: str
    period: str
    segments: tuple[RegimeSegment, ...]
    source_refs: tuple[EvidenceRef, ...]
    confidence: ConfidenceScore


@dataclass(frozen=True)
class CorrelationPair:
    """Pearson correlation of daily returns between one instrument and one macro series.

    lag > 0: macro leads instrument by lag trading days
    lag < 0: instrument leads macro by abs(lag) trading days
    lag == 0: same-period correlation

    correlation is math.nan when observation_count < 3 or variance is zero.
    """

    instrument: str          # e.g. "SBER"
    macro_symbol: str        # "IMOEX" | "USDRUB" | "RGBI"
    lag: int
    correlation: float       # Pearson r in [-1.0, 1.0] or math.nan
    observation_count: int   # number of aligned return pairs used


@dataclass(frozen=True)
class CorrelationSnapshot:
    """Output of CorrelationAgent — full correlation analysis for one instrument.

    Saved to data/context/correlation/{instrument.lower()}_{period}.json.
    """

    snapshot_id: str
    instrument: str
    period: str
    pairs: tuple[CorrelationPair, ...]
    total_instrument_bars: int   # daily close count in instrument series
    aligned_dates: int           # instrument dates also present in macro series
    missing_alignment: int       # total_instrument_bars - aligned_dates
    source_refs: tuple[EvidenceRef, ...]
    confidence: ConfidenceScore


@dataclass(frozen=True)
class DatasetManifest:
    """Describes a dataset written to disk — compatible with DatasetLoader.

    ohlcv_path and metadata_path are absolute paths.
    All fields required by DatasetLoader are present.
    """

    dataset_id: str
    dataset_path: str
    ohlcv_path: str
    metadata_path: str
    ticker: str
    timeframe: str
    bar_count: int
    date_from: str
    date_to: str
    session_filter: str
    source: str
