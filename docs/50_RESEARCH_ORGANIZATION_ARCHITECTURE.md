# 50_RESEARCH_ORGANIZATION_ARCHITECTURE
# Research Organization Era — Architecture Design

> Status: **DESIGN** — approved for implementation.
> Era: Research Organization Era (RO), following Intelligence Era v1.
> Date: 2026-06-27
> Baseline: `v0.9-intelligence-alpha` — all IE Phase 1–8 agents validated.

---

## Purpose

Intelligence Era v1 validated the core autonomous cycle.
The Research Organization Era formalises MOEX AI LAB as a **team of specialised agents**,
each with defined contracts, KPIs, and governance constraints.

The goal is not a single AI: it is a **research institution** where agents have roles,
departments have mandates, and the ChiefScientist coordinates across all departments.

---

## Freeze Policy

**Until this document is approved and RO-1 is complete, the following are PROHIBITED:**

| Rule | Scope |
|------|-------|
| No new agents | Any agent beyond IE Phase 1–8 |
| No Agent Protocol changes | `agents/protocols.py`, `AgentResult` contract |
| No Research Service changes | `services/research/` (requires ADR) |
| No ChiefScientist changes | `agents/research/chief.py` |
| No ML/LLM in v1 | All agents must use deterministic rules only |

**Permitted:** bug fixes with tests, documentation updates, roadmap revisions.

---

## 1. Research Departments

The system is divided into **7 research departments**. Each department owns a set of agents
and is responsible for a specific class of intelligence production.

```
+------------------------------------------------------------------+
|                   RESEARCH ORGANIZATION ERA                       |
+------------------------------------------------------------------+
|                                                                    |
|  [Data Intelligence]      Raw signals from the world              |
|  [Analysis Intelligence]  Structure discovered in raw signals     |
|  [Discovery Intelligence] New hypotheses and features found       |
|  [Validation Intelligence] Hypothesis execution and safety        |
|  [Knowledge Intelligence] Accumulation and synthesis              |
|  [Strategy Intelligence]  Research direction and prioritisation   |
|  [Meta Intelligence]      System-level learning and policy        |
|                                                                    |
+------------------------------------------------------------------+
```

### 1.1 Data Intelligence

**Mandate:** Collect, normalise, and persist raw time-series data from all external sources.
No analysis. No hypothesis generation. Only acquisition.

**Existing agents:** MarketAgent, MacroAgent
**Candidate agents:** NewsAgent (RO-2), DividendsAgent (RO-3), CorporateEventsAgent (future)

### 1.2 Analysis Intelligence

**Mandate:** Transform raw data into structured analytical signals (correlations, regimes,
sector context). No hypothesis generation. No trading decisions.

**Existing agents:** CorrelationAgent, RegimeDetectionAgent
**Candidate agents:** SectorBreadthAgent (RO-4), StatisticalSignificanceAgent (RO-7)

### 1.3 Discovery Intelligence

**Mandate:** Generate candidate hypotheses and identify novel features.
May inspect accumulated KnowledgeSnapshot. Must not run Research Service.

**Candidate agents:** FeatureDiscoveryAgent (RO-5), NoveltyDetector (RO-6)

### 1.4 Validation Intelligence

**Mandate:** Translate approved ExperimentPlans into Research Service runs.
All safety guards enforced here. Cannot override policy without explicit override flag.

**Existing agents:** ExperimentPlanner, ValidationAgentAdapter
**Candidate agents:** RiskOfficer (RO-8)

### 1.5 Knowledge Intelligence

**Mandate:** Aggregate evidence, detect patterns, maintain the Knowledge Graph.
Read-only access to Research Service reports. Writes only to KnowledgeSnapshot.

**Existing agents:** KnowledgeAgent
**Candidate agents:** MetaKnowledgeAgent (RO-9)

### 1.6 Strategy Intelligence

**Mandate:** Prioritise research directions. Decide what to investigate next.
Consumes KnowledgeSnapshot and all department outputs. Never runs Research Service directly.

**Existing agents:** ChiefScientist v1
**Candidate agents:** PolicyEvolutionAgent (RO-10)

### 1.7 Meta Intelligence

**Mandate:** Monitor system-level health: KPI tracking, decision audit, policy improvement.
Reads all AgentResult logs. Never modifies other agents. Proposes policy changes as documents.

**Candidate agents:** PolicyEvolutionAgent (RO-10), architecture review tooling

---

## 2. Agent Roles

### DATA INTELLIGENCE

---

#### MarketAgent
- **Purpose:** Fetch and persist OHLCV data from MOEX ISS for equity instruments.
- **Input:** ticker, timeframe (1h/2h/4h/1d), date range, session filter
- **Output:** `AgentResult[DatasetManifest]` — path to ohlcv.csv + metadata.json
- **Dependencies:** MOEX ISS API (equity candles endpoint)
- **Constraints:** No inferred signals. No regime labelling. Data only.
- **KPI:** data_completeness (bars / expected_bars), freshness_lag_days, error_rate

---

#### MacroAgent
- **Purpose:** Collect macro context series: IMOEX index, USDRUB FX, RGBI bond index.
- **Input:** period (year), symbols, timeframe (1d)
- **Output:** `AgentResult[MacroSnapshot]` — tuple of MacroSeries with CSV paths
- **Dependencies:** MOEX ISS API (index and FX candle endpoints)
- **Constraints:** Graceful degradation if offline. No correlation computation.
- **KPI:** symbols_fetched / symbols_requested, missing_value_rate, daily_freshness

---

#### NewsAgent *(RO-2 — candidate)*
- **Purpose:** Collect MOEX-relevant news headlines and sentiment signals.
- **Input:** tickers list, date range, news source config
- **Output:** `AgentResult[NewsSnapshot]` — headlines, sentiment label, source_ref
- **Dependencies:** News API or RSS feed (TBD in RO-2 ADR)
- **Constraints:** No ML sentiment. Rule-based labelling only in v1.
  Labels: POSITIVE / NEGATIVE / NEUTRAL based on keyword matching.
- **KPI:** headlines_per_day, coverage_rate (days with ≥1 headline), false_label_rate

---

#### DividendsAgent *(RO-3 — candidate)*
- **Purpose:** Collect dividend calendars and ex-dividend dates for MOEX tickers.
- **Input:** tickers list, date range
- **Output:** `AgentResult[DividendSnapshot]` — ex_date, amount, yield_pct per ticker
- **Dependencies:** MOEX ISS securities/dividends endpoint
- **Constraints:** Historical data only. No forecasting.
- **KPI:** tickers_covered, yield_accuracy (vs actuals), calendar_completeness

---

### ANALYSIS INTELLIGENCE

---

#### CorrelationAgent
- **Purpose:** Compute Pearson correlation between instrument daily returns and macro series.
- **Input:** instrument, period — reads from `data/datasets/` + `data/context/macro/`
- **Output:** `AgentResult[CorrelationSnapshot]` — pairs with lags 0, ±1, ±5
- **Dependencies:** MarketAgent output, MacroAgent output (graceful if absent)
- **Constraints:** stdlib math only. No external stats libraries.
- **KPI:** pairs_computed, macro_alignment_rate, nan_rate (missing overlap)

---

#### RegimeDetectionAgent
- **Purpose:** Classify market regime (trend/volatility/risk) in rolling 21-day windows.
- **Input:** instrument, period — reads OHLCV + optional macro
- **Output:** `AgentResult[RegimeSnapshot]` — RegimeSegment list with labels
- **Dependencies:** MarketAgent output, MacroAgent output (optional)
- **Constraints:** Deterministic classification only. Labels: TREND_UP/DOWN/RANGE,
  LOW_VOL/NORMAL_VOL/HIGH_VOL, RISK_ON/RISK_OFF/NEUTRAL.
- **KPI:** segments_per_period, label_entropy (diversity of assigned labels), coverage_pct

---

#### SectorBreadthAgent *(RO-4 — candidate)*
- **Purpose:** Measure sector-level breadth: percentage of sector members in uptrend,
  average sector momentum, sector rotation signal.
- **Input:** sector definition map (ticker → sector), period
- **Output:** `AgentResult[SectorBreadthSnapshot]` — per-sector breadth metrics
- **Dependencies:** MarketAgent output for each sector member
- **Constraints:** No trading signals. Breadth metrics only. Deterministic.
- **KPI:** sectors_covered, breadth_stability (variance across windows), freshness

---

#### StatisticalSignificanceAgent *(RO-7 — candidate)*
- **Purpose:** Compute p-values and effect sizes for ExperimentPlan results.
  Prevents ChiefScientist from acting on statistically weak evidence.
- **Input:** `ValidationBatchResult` + historical pass_rate distribution
- **Output:** `AgentResult[SignificanceReport]` — p_value, effect_size, sample_n,
  is_significant (bool, threshold p < 0.05)
- **Dependencies:** ValidationAgentAdapter output, KnowledgeAgent (historical baseline)
- **Constraints:** stdlib statistics only. No scipy/numpy.
- **KPI:** false_positive_rate, power_estimate, coverage_of_decisions

---

### DISCOVERY INTELLIGENCE

---

#### FeatureDiscoveryAgent *(RO-5 — candidate)*
- **Purpose:** Identify technical feature candidates that correlate with regime or
  pass_rate by scanning KnowledgeSnapshot patterns.
- **Input:** `KnowledgeSnapshot`, list of available feature names
- **Output:** `AgentResult[FeatureCandidateList]` — ranked feature names with
  supporting evidence refs
- **Dependencies:** KnowledgeAgent output
- **Constraints:** No feature generation. Ranking only from existing features.
  No ML. Evidence-based ranking using support_count.
- **KPI:** novel_candidates_per_run, evidence_depth (avg support_count),
  false_discovery_rate (how many get validated)

---

#### NoveltyDetector *(RO-6 — candidate)*
- **Purpose:** Flag when incoming KnowledgeFacts deviate from established patterns.
  Detects regime shifts, unexpected pass_rate improvements, emerging contradictions.
- **Input:** `KnowledgeSnapshot` (current) + `KnowledgeSnapshot` (previous baseline)
- **Output:** `AgentResult[NoveltyReport]` — list of NoveltySignal with
  deviation_score, description, affected_hypothesis_ids
- **Dependencies:** KnowledgeAgent output (two snapshots)
- **Constraints:** Deterministic anomaly scoring (z-score style, stdlib math).
  No ML. No trading signals.
- **KPI:** novelty_recall (did it catch real regime shifts), false_alarm_rate,
  lead_time_days (how early it detected a shift)

---

### VALIDATION INTELLIGENCE

---

#### ExperimentPlanner
- **Purpose:** Generate reproducible ExperimentPlan objects from KnowledgeSnapshot.
- **Input:** `KnowledgeSnapshot`, available datasets, campaign_id
- **Output:** `AgentResult[tuple[ExperimentPlan, ...]]` — one plan per detected pattern
- **Dependencies:** KnowledgeAgent output
- **Constraints:** 4 plan types only: regime_exploration, regime_filter,
  contradiction_replication, expansion. Max 5 tasks per plan.
  No new hypothesis generation. No ML.
- **KPI:** plans_per_snapshot, plans_executed_pct, plan_quality_score
  (pct of plans that produced useful evidence per ChiefScientist)

---

#### ValidationAgentAdapter
- **Purpose:** Safe bridge between ExperimentPlan and Research Service.
  Enforces dry_run default, overfitting guard, stop conditions.
- **Input:** `ExperimentPlan`, execute flag, allow_high_risk flag
- **Output:** `AgentResult[ValidationBatchResult]`
- **Dependencies:** Research Service (deferred import, execute=True only)
- **Constraints:** dry_run by default. High overfitting_risk blocked without override.
  Missing datasets abort run. Stop conditions checked before each task.
  Never modifies Research Service or DatasetLoader.
- **KPI:** dry_run_rate, blocked_rate, stop_trigger_rate, task_success_rate

---

#### RiskOfficer *(RO-8 — candidate)*
- **Purpose:** Pre-flight check before ValidationAgentAdapter executes any plan.
  Assesses portfolio-level experiment risk: concentration, capital-at-risk, drawdown exposure.
- **Input:** `ExperimentPlan`, current `ResearchPolicy`, system resource snapshot
- **Output:** `AgentResult[RiskAssessment]` — approved / rejected / conditional,
  with risk_score and blocking_reasons
- **Dependencies:** ExperimentPlanner output, ResearchPolicy
- **Constraints:** Advisory only in v1. Future v2: blocking authority.
  No trading signals. No capital allocation decisions.
- **KPI:** false_block_rate (blocked valid plans), miss_rate (approved risky plans),
  assessment_latency_ms

---

### KNOWLEDGE INTELLIGENCE

---

#### KnowledgeAgent
- **Purpose:** Aggregate research reports into structured KnowledgeSnapshot:
  facts, connections, patterns, contradictions, recommendations.
- **Input:** campaign_id — reads `reports/{campaign_id}/*.json` + kb entries
- **Output:** `AgentResult[KnowledgeSnapshot]`
- **Dependencies:** ValidationAgentAdapter output (via filesystem bridge)
- **Constraints:** Read-only on reports. Writes only to knowledge/snapshots/.
  Deterministic aggregation. No ML.
- **KPI:** fact_count_growth, contradiction_detection_rate, pattern_diversity,
  recommendation_usefulness (pct acted on by ChiefScientist)

---

#### MetaKnowledgeAgent *(RO-9 — candidate)*
- **Purpose:** Synthesise learning across campaigns and eras. Detects which hypotheses
  survive across instruments, which research strategies are productive, which
  KB patterns are persistent vs transient.
- **Input:** multiple `KnowledgeSnapshot` objects (cross-campaign), decision audit log
- **Output:** `AgentResult[MetaKnowledgeReport]` — persistent_patterns, dead_ends,
  productive_strategies, recommended_policy_updates
- **Dependencies:** KnowledgeAgent (multiple runs)
- **Constraints:** No new hypotheses. Synthesis and meta-analysis only.
  Reports as documents, not executable plans.
- **KPI:** persistent_pattern_recall, dead_end_identification_rate,
  policy_recommendation_adoption_rate

---

### STRATEGY INTELLIGENCE

---

#### ChiefScientist v1
- **Purpose:** Rule-based research coordinator. Selects next ExperimentPlan based on
  accumulated evidence. Issues prioritised ResearchDecision objects.
- **Input:** `KnowledgeSnapshot`, `list[ExperimentPlan]`, `list[ValidationBatchResult]`,
  `ResearchPolicy`
- **Output:** `AgentResult[tuple[ResearchDecision, ...]]` — sorted critical→low
- **Dependencies:** KnowledgeAgent, ExperimentPlanner, ValidationAgentAdapter (results)
- **Constraints:** 7 deterministic rules only. No ML. No trading decisions.
  No direct Research Service calls. No ExperimentPlan modification.
- **KPI:** decision_accuracy (pct of RUN_PLAN decisions that produce useful evidence),
  archive_precision (pct of archived hypotheses correctly identified as dead ends),
  stop_trigger_false_positive_rate

---

#### PolicyEvolutionAgent *(RO-10 — candidate)*
- **Purpose:** Propose updates to ResearchPolicy based on accumulated evidence of
  what thresholds and rules work. Outputs policy proposals as ADR documents,
  not code changes. Human approval required before policy changes take effect.
- **Input:** `MetaKnowledgeReport`, decision audit log, current `ResearchPolicy`
- **Output:** `AgentResult[PolicyProposal]` — proposed_policy delta,
  supporting_evidence, expected_impact
- **Dependencies:** MetaKnowledgeAgent, ChiefScientist audit log
- **Constraints:** Outputs documents only. Never modifies code. Never self-applies.
  Human-in-the-loop required for all policy changes.
- **KPI:** proposals_adopted_rate, policy_improvement_delta (before/after KPI comparison)

---

## 3. Agent Contracts

Every agent in MOEX AI LAB must conform to the following contract.

### 3.1 AgentResult Envelope

```python
@dataclass(frozen=True)
class AgentResult:
    agent_id:      str            # stable, kebab-case: "market-agent"
    agent_type:    str            # "DATA"|"ANALYSIS"|"DISCOVERY"|"VALIDATION"
                                  # "KNOWLEDGE"|"STRATEGY"|"META"
    version:       str            # "1.0", "2.0" — bumped on breaking output change
    input_summary: str            # brief description of what the agent consumed
    output:        object         # domain-specific payload (frozen dataclass or tuple)
    evidence:      tuple[EvidenceRef, ...]
    confidence:    ConfidenceScore  # value in [0.0, 1.0] with reason
    created_at:    str            # ISO-format from injected clock
```

### 3.2 EvidenceRef

Every `AgentResult` must include at least one `EvidenceRef` pointing to the data source
that produced the output. This is the audit trail.

```python
@dataclass(frozen=True)
class EvidenceRef:
    source:    str   # "MOEX ISS API", "filesystem", "knowledge_snapshot", "fixture"
    reference: str   # URL, file path, or snapshot_id
    timestamp: str   # ISO-format datetime of evidence collection
```

### 3.3 Confidence

Confidence is a normalised score in `[0.0, 1.0]` with a mandatory `reason` string.

| Score range | Meaning |
|-------------|---------|
| 0.0–0.29 | Very low — insufficient data or high uncertainty |
| 0.30–0.59 | Low — some evidence but not conclusive |
| 0.60–0.79 | Medium — consistent evidence across ≥3 sources |
| 0.80–1.00 | High — strong, replicated evidence |

### 3.4 Version Contract

- `version` must be bumped when the **output schema** changes (breaking).
- Minor internal changes (bug fixes, performance) do not bump version.
- Version `"1.0"` is the baseline for all IE Phase 1–8 agents.
- All versions must remain importable (no deleting old output models).

### 3.5 Deterministic Mode

Every agent must accept `_clock: Optional[Callable[[], datetime]] = None`.
When `_clock` is injected, all `created_at` timestamps use it.
This enables fully reproducible test runs with no time-dependent output.

### 3.6 Fixture Mode

Every agent must accept an injectable source via `__init__`:

```python
def __init__(self, data_dir: Path, source: Optional[SomeSource] = None) -> None:
    self._source = source or FileXxxSource(data_dir)
```

- `FileXxxSource`: production, reads from disk / network
- `FixtureXxxSource`: test, returns pre-configured data

No agent may import `FixtureXxxSource` in production paths.

### 3.7 Persistence

- Data agents write to `data/` subtree.
- Analysis agents write to `data/context/` subtree.
- Knowledge agents write to `knowledge/` subtree.
- Validation agents write to `research_programs/` subtree.
- Strategy agents (decisions) write to `research_programs/decisions/` subtree.
- Meta agents write to `docs/` subtree (proposals as Markdown).
- **No agent may write outside its designated subtree.**

---

## 4. Data Flow

```
                        RESEARCH ORGANIZATION ERA — DATA FLOW
                        =====================================

  [DATA INTELLIGENCE]
  MarketAgent          ──> DatasetManifest   ──> data/datasets/{id}/
  MacroAgent           ──> MacroSnapshot     ──> data/context/macro/
  NewsAgent            ──> NewsSnapshot      ──> data/context/news/
  DividendsAgent       ──> DividendSnapshot  ──> data/context/dividends/
         |
         v
  [ANALYSIS INTELLIGENCE]
  CorrelationAgent     ──> CorrelationSnapshot   ──> data/context/correlation/
  RegimeDetectionAgent ──> RegimeSnapshot        ──> data/context/regime/
  SectorBreadthAgent   ──> SectorBreadthSnapshot ──> data/context/sector/
         |
         v
  [DISCOVERY INTELLIGENCE]
  FeatureDiscoveryAgent ──> FeatureCandidateList  ──> research_programs/features/
  NoveltyDetector       ──> NoveltyReport         ──> research_programs/novelty/
         |
         v
  [KNOWLEDGE INTELLIGENCE — pre-planning]
  KnowledgeAgent       ──> KnowledgeSnapshot  ──> knowledge/snapshots/
         |
         v
  [VALIDATION INTELLIGENCE — planning]
  ExperimentPlanner    ──> tuple[ExperimentPlan]  ──> research_programs/plans/
  RiskOfficer          ──> RiskAssessment         ──> (advisory, in memory)
         |
         v
  [STRATEGY INTELLIGENCE]
  ChiefScientist       ──> tuple[ResearchDecision] ──> research_programs/decisions/
         |
         | (RUN_PLAN decision)
         v
  [VALIDATION INTELLIGENCE — execution]
  ValidationAgentAdapter ──> ValidationBatchResult ──> research_programs/validation_runs/
         |
         v
  [Research Service]   ──> ResearchReport (session) ──> reports/{session_id}/
         |
         | (filesystem bridge: session report -> IE fact JSONs)
         v
  [KNOWLEDGE INTELLIGENCE — post-run]
  KnowledgeAgent       ──> KnowledgeSnapshot (updated) ──> knowledge/snapshots/
         |
         v
  [META INTELLIGENCE]
  MetaKnowledgeAgent   ──> MetaKnowledgeReport ──> knowledge/meta/
  StatSignificanceAgent ──> SignificanceReport  ──> research_programs/significance/
  PolicyEvolutionAgent ──> PolicyProposal      ──> docs/policy_proposals/
         |
         v
  [STRATEGY INTELLIGENCE — next cycle]
  ChiefScientist       ──> next ResearchDecision
```

### Key invariants

1. **Data flows downward.** No agent reads from a department below it.
2. **Research Service is a black box.** Only ValidationAgentAdapter calls it.
3. **Knowledge accumulates monotonically.** KnowledgeAgent never deletes facts.
4. **ChiefScientist never runs Research Service directly.** All execution via ValidationAdapter.
5. **Meta agents never modify other agents.** They produce documents, not code changes.

---

## 5. Governance Rules

### G-01: Research Service Immutability
`services/research/` may not be modified without an Architecture Decision Record (ADR)
approved and committed to `docs/30_ARCHITECTURE_DECISION_LOG.md`.
Rationale: Research Service is the validated execution layer. Changes invalidate baseline.

### G-02: Overfitting Guard
No ExperimentPlan with `overfitting_risk.level == "high"` may be executed via
ValidationAgentAdapter without `allow_high_risk=True` explicitly set.
The RiskOfficer (RO-8) must log a `RiskAssessment` for all high-risk plans.

### G-03: No ML/LLM in v1
All agents must use deterministic, rule-based logic only.
No scikit-learn, no PyTorch, no OpenAI/Anthropic API calls in agent code.
ML/LLM may be considered in Research Organization Era v2 after KPI baselines are established.

### G-04: Test Coverage Required
Every new agent must ship with:
- Protocol compliance tests (agent_id, agent_type, version, run() returns AgentResult)
- At least one determinism test (same input → same output)
- At least one persistence test (output written to correct path)
- At least one fixture mode test (no I/O, fast)
- Target: ≥6 tests per agent, ≥90% of public functions covered

### G-05: KPI Required Before Ship
Every new agent must have at least 2 measurable KPIs defined in this document
and tracked in `docs/99_PROJECT_DASHBOARD.md`.

### G-06: Additive Agent Mandate
Every new agent must add one of:
- A new external data source (not previously captured)
- A new type of reasoning (not performed by any existing agent)

Agents that duplicate existing capabilities are rejected.

### G-07: Freeze Window
No new agents are added while:
- An Architecture Decision Record is open
- A phase has failing tests
- The Freeze Policy (section 8) is active

### G-08: Knowledge Base Monotonicity
No agent may delete KnowledgeFact entries. Archiving a hypothesis means setting its
status in the ResearchDecision log, not deleting its evidence.

### G-09: Persistence Namespace Isolation
Each department owns its filesystem namespace (see Section 3.7).
Cross-namespace writes require an explicit ADR.

---

## 6. KPI System

### Data Intelligence KPIs

| Agent | KPI | Definition | Target |
|-------|-----|------------|--------|
| MarketAgent | `data_completeness` | bars_fetched / bars_expected | ≥ 0.95 |
| MarketAgent | `freshness_lag_days` | today - latest_bar_date | ≤ 1 |
| MarketAgent | `error_rate` | failed_fetches / total_fetches | ≤ 0.02 |
| MacroAgent | `symbols_coverage` | fetched_symbols / requested_symbols | ≥ 0.90 |
| MacroAgent | `missing_value_rate` | null_values / total_values | ≤ 0.05 |
| NewsAgent | `headlines_per_day` | avg headlines per trading day | ≥ 5 |
| NewsAgent | `coverage_rate` | days_with_news / trading_days | ≥ 0.80 |
| DividendsAgent | `calendar_completeness` | ex_dates_found / ex_dates_expected | ≥ 0.95 |

### Analysis Intelligence KPIs

| Agent | KPI | Definition | Target |
|-------|-----|------------|--------|
| CorrelationAgent | `pairs_computed` | correlation pairs per instrument run | ≥ 15 |
| CorrelationAgent | `nan_rate` | nan_pairs / total_pairs | ≤ 0.10 |
| RegimeDetectionAgent | `coverage_pct` | classified_bars / total_bars | ≥ 0.90 |
| RegimeDetectionAgent | `label_entropy` | Shannon entropy of label distribution | ≥ 1.0 |
| SectorBreadthAgent | `sectors_covered` | sectors_with_breadth / total_sectors | ≥ 0.85 |
| StatSignificanceAgent | `false_positive_rate` | significant but non-replicable | ≤ 0.05 |

### Discovery Intelligence KPIs

| Agent | KPI | Definition | Target |
|-------|-----|------------|--------|
| FeatureDiscoveryAgent | `novel_candidates_per_run` | new features per KnowledgeSnapshot | ≥ 1 |
| FeatureDiscoveryAgent | `false_discovery_rate` | candidates not validated | ≤ 0.50 |
| NoveltyDetector | `novelty_recall` | detected_shifts / actual_shifts | ≥ 0.80 |
| NoveltyDetector | `false_alarm_rate` | false_alerts / total_alerts | ≤ 0.20 |
| NoveltyDetector | `lead_time_days` | avg days ahead of human detection | ≥ 2 |

### Validation Intelligence KPIs

| Agent | KPI | Definition | Target |
|-------|-----|------------|--------|
| ExperimentPlanner | `plans_executed_pct` | executed_plans / generated_plans | ≥ 0.70 |
| ExperimentPlanner | `plan_quality_score` | plans_with_useful_evidence / executed | ≥ 0.50 |
| ValidationAgentAdapter | `dry_run_rate` | dry_runs / total_runs | tracked |
| ValidationAgentAdapter | `blocked_rate` | blocked_tasks / total_tasks | tracked |
| ValidationAgentAdapter | `task_success_rate` | success / total_executed | ≥ 0.85 |
| RiskOfficer | `false_block_rate` | blocked_valid / total_blocked | ≤ 0.10 |
| RiskOfficer | `miss_rate` | approved_risky / total_approved | ≤ 0.05 |

### Knowledge Intelligence KPIs

| Agent | KPI | Definition | Target |
|-------|-----|------------|--------|
| KnowledgeAgent | `fact_count_growth` | facts_after / facts_before per run | ≥ 1.05 |
| KnowledgeAgent | `contradiction_detection_rate` | contradictions_found / actual | ≥ 0.80 |
| KnowledgeAgent | `recommendation_usefulness` | recommendations acted on by CS | ≥ 0.40 |
| MetaKnowledgeAgent | `persistent_pattern_recall` | persistent detected / actual | ≥ 0.75 |
| MetaKnowledgeAgent | `policy_adoption_rate` | proposals adopted / proposed | ≥ 0.30 |

### Strategy Intelligence KPIs

| Agent | KPI | Definition | Target |
|-------|-----|------------|--------|
| ChiefScientist | `decision_accuracy` | RUN_PLAN with useful evidence / total | ≥ 0.60 |
| ChiefScientist | `archive_precision` | correctly_archived / total_archived | ≥ 0.85 |
| ChiefScientist | `stop_false_positive_rate` | false STOP_RESEARCH_LINE / total | ≤ 0.05 |
| PolicyEvolutionAgent | `proposals_adopted_rate` | adopted / total_proposed | ≥ 0.30 |

---

## 7. Roadmap — Research Organization Era

Each phase is atomic: one agent, one commit, one set of tests.
No phase begins until the previous phase has all tests passing.

### RO-1: Architecture + Governance *(this document)*

**Deliverable:** `docs/50_RESEARCH_ORGANIZATION_ARCHITECTURE.md`
**Actions:**
- Define all departments, roles, contracts, KPIs, governance rules
- Update CONTROL_CENTER docs
- Freeze Policy: no new agents until RO-1 approved
- No code changes

**Exit criteria:** Document approved, no open questions in Freeze Policy.

---

### RO-2: NewsAgent

**Department:** Data Intelligence
**Deliverable:** `agents/data/news.py`, `agents/models.py` (+NewsSnapshot, NewsItem),
tests in `tests/agents/test_news_agent.py`
**Data source:** RSS feed or MOEX news API (ADR required)
**KPI baseline:** headlines_per_day ≥ 5, coverage_rate ≥ 0.80
**Constraint:** Rule-based sentiment only (keyword matching). No ML.

---

### RO-3: DividendsAgent

**Department:** Data Intelligence
**Deliverable:** `agents/data/dividends.py`, `agents/models.py` (+DividendSnapshot),
tests in `tests/agents/test_dividends_agent.py`
**Data source:** MOEX ISS securities/dividends endpoint
**KPI baseline:** calendar_completeness ≥ 0.95
**Constraint:** Historical data only. No dividend forecasting.

---

### RO-4: SectorBreadthAgent

**Department:** Analysis Intelligence
**Deliverable:** `agents/analysis/sector_breadth.py`,
`agents/models.py` (+SectorBreadthSnapshot),
tests in `tests/agents/test_sector_breadth_agent.py`
**Data source:** MarketAgent output for MOEX sector members (10 standard sectors)
**KPI baseline:** sectors_covered ≥ 0.85, label_entropy ≥ 0.8
**Constraint:** Breadth metrics only. No sector rotation trading signals.

---

### RO-5: FeatureDiscoveryAgent

**Department:** Discovery Intelligence
**Deliverable:** `agents/discovery/feature_discovery.py`,
`agents/models.py` (+FeatureCandidateList, FeatureCandidate),
tests in `tests/agents/test_feature_discovery_agent.py`
**Data source:** KnowledgeSnapshot (tags field of KnowledgeFact)
**KPI baseline:** novel_candidates_per_run ≥ 1
**Constraint:** Ranks existing features only. Does not invent new feature names.

---

### RO-6: NoveltyDetector

**Department:** Discovery Intelligence
**Deliverable:** `agents/discovery/novelty_detector.py`,
`agents/models.py` (+NoveltyReport, NoveltySignal),
tests in `tests/agents/test_novelty_detector.py`
**Data source:** Two KnowledgeSnapshot objects (current vs baseline)
**KPI baseline:** novelty_recall ≥ 0.80, false_alarm_rate ≤ 0.20
**Constraint:** Z-score based deviation. No ML anomaly detection.

---

### RO-7: StatisticalSignificanceAgent

**Department:** Analysis Intelligence
**Deliverable:** `agents/analysis/significance.py`,
`agents/models.py` (+SignificanceReport),
tests in `tests/agents/test_significance_agent.py`
**Data source:** ValidationBatchResult + KnowledgeSnapshot (historical baseline)
**KPI baseline:** false_positive_rate ≤ 0.05
**Constraint:** stdlib statistics module only. No scipy.

---

### RO-8: RiskOfficer

**Department:** Validation Intelligence
**Deliverable:** `agents/research/risk_officer.py`,
`agents/models.py` (+RiskAssessment),
tests in `tests/agents/test_risk_officer.py`
**Data source:** ExperimentPlan, ResearchPolicy, system resource snapshot
**KPI baseline:** false_block_rate ≤ 0.10, miss_rate ≤ 0.05
**Constraint:** Advisory in v1. Cannot block ValidationAdapter without explicit integration.

---

### RO-9: MetaKnowledgeAgent

**Department:** Knowledge Intelligence
**Deliverable:** `agents/knowledge/meta.py`,
`agents/models.py` (+MetaKnowledgeReport, PersistentPattern),
tests in `tests/agents/test_meta_knowledge_agent.py`
**Data source:** Multiple KnowledgeSnapshot objects, decision audit log
**KPI baseline:** persistent_pattern_recall ≥ 0.75
**Constraint:** Synthesis only. No new hypothesis generation. Writes to `knowledge/meta/`.

---

### RO-10: PolicyEvolutionAgent

**Department:** Meta Intelligence
**Deliverable:** `agents/meta/policy_evolution.py`,
`agents/models.py` (+PolicyProposal),
tests in `tests/agents/test_policy_evolution_agent.py`
**Data source:** MetaKnowledgeReport, ChiefScientist decision log, current ResearchPolicy
**KPI baseline:** proposals_adopted_rate ≥ 0.30
**Constraint:** Outputs Markdown ADR documents only. Never modifies code or policy files.
Human approval required for all policy changes.

---

### Roadmap Summary

| Phase | Agent | Department | New Data Source / New Reasoning |
|-------|-------|------------|----------------------------------|
| RO-1 | Architecture | — | Governance framework |
| RO-2 | NewsAgent | Data | MOEX news / sentiment signals |
| RO-3 | DividendsAgent | Data | Dividend calendar / corporate events |
| RO-4 | SectorBreadthAgent | Analysis | Sector-level breadth and rotation |
| RO-5 | FeatureDiscoveryAgent | Discovery | Evidence-based feature ranking |
| RO-6 | NoveltyDetector | Discovery | Regime shift / surprise detection |
| RO-7 | StatSignificanceAgent | Analysis | p-value and effect size computation |
| RO-8 | RiskOfficer | Validation | Pre-execution risk assessment |
| RO-9 | MetaKnowledgeAgent | Knowledge | Cross-campaign pattern synthesis |
| RO-10 | PolicyEvolutionAgent | Meta | Policy proposal generation |

---

## 8. Architecture Decisions Required Before Implementation

The following ADRs must be filed in `docs/30_ARCHITECTURE_DECISION_LOG.md`
before the corresponding phase begins:

| ADR | Required For | Question |
|-----|-------------|---------|
| ADR-RO-02 | RO-2 (NewsAgent) | Which news source API? Rate limits? Licensing? |
| ADR-RO-04 | RO-4 (SectorBreadthAgent) | Which MOEX sector taxonomy? |
| ADR-RO-07 | RO-7 (StatSignificanceAgent) | Minimum sample size for significance? |
| ADR-RO-08 | RO-8 (RiskOfficer) | When does advisory become blocking? |
| ADR-RO-10 | RO-10 (PolicyEvolutionAgent) | Human-in-the-loop approval process? |

---

## 9. Agent Directory Layout

```
agents/
  data/
    market.py          # MarketAgent     — IE Phase 1
    macro.py           # MacroAgent      — IE Phase 2
    news.py            # NewsAgent       — RO-2
    dividends.py       # DividendsAgent  — RO-3

  analysis/
    correlation.py     # CorrelationAgent     — IE Phase 3
    regime.py          # RegimeDetectionAgent — IE Phase 4
    sector_breadth.py  # SectorBreadthAgent   — RO-4
    significance.py    # StatSignificanceAgent — RO-7

  discovery/
    feature_discovery.py  # FeatureDiscoveryAgent — RO-5
    novelty_detector.py   # NoveltyDetector       — RO-6

  knowledge/
    agent.py   # KnowledgeAgent     — IE Phase 5
    meta.py    # MetaKnowledgeAgent — RO-9

  research/
    planner.py     # ExperimentPlanner        — IE Phase 6
    adapter.py     # ValidationAgentAdapter   — IE Phase 7
    chief.py       # ChiefScientist v1        — IE Phase 8
    risk_officer.py  # RiskOfficer            — RO-8

  meta/
    policy_evolution.py  # PolicyEvolutionAgent — RO-10

  models.py      # All domain models — shared
  protocols.py   # AgentProtocol + Source protocols — shared
```

---

## 10. Intelligence Era v1 — Preserved Contracts

The following are **frozen** for the duration of Research Organization Era:

| Component | File | Status |
|-----------|------|--------|
| AgentProtocol | `agents/protocols.py` | FROZEN |
| AgentResult | `agents/models.py` | FROZEN (additive changes only) |
| MarketAgent API | `agents/data/market.py` | FROZEN |
| MacroAgent API | `agents/data/macro.py` | FROZEN |
| CorrelationAgent API | `agents/analysis/correlation.py` | FROZEN |
| RegimeDetectionAgent API | `agents/analysis/regime.py` | FROZEN |
| KnowledgeAgent API | `agents/knowledge/agent.py` | FROZEN |
| ExperimentPlanner API | `agents/research/planner.py` | FROZEN |
| ValidationAgentAdapter API | `agents/research/adapter.py` | FROZEN |
| ChiefScientist v1 API | `agents/research/chief.py` | FROZEN |
| Research Service | `services/research/` | FROZEN (ADR required) |

"Additive changes only" means: new frozen dataclasses may be added to `models.py`,
but existing dataclass fields may not be removed or renamed.

---

*Document status: DESIGN — approved for RO-1.*
*Next action: RO-2 NewsAgent ADR.*
