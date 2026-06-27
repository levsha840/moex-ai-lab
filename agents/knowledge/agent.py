"""KnowledgeAgent — Layer 3 KNOWLEDGE Agent.

Reads existing research artifacts and builds a next-generation Knowledge Base:

  1. Aggregation     — extracts structured KnowledgeFact from reports / KB entries
  2. Pattern Discovery — detects recurring regime-hypothesis and performance patterns
  3. Connection Graph  — links entities (hypotheses ↔ regimes) with relation + strength
  4. Knowledge Report  — contradictions, strong/weak facts, recommendations

No ML. No LLM. No new hypothesis generation. No modifications to Research Service.

Input dict format for reports:
    {
        "report_id":    "h13_sber_2023",       # required str
        "hypothesis_id":"H-13",                # required str
        "instrument":   "SBER",                # required str
        "period":       "2023",                # required str
        "pass_rate":    0.239,                 # required float
        "passed":       False,                 # required bool
        "confidence":   0.85,                  # required float [0,1]
        "regime_label": "TREND_UP",            # optional str, "" if absent
        "source_ref":   "reports/h13.json",   # required str
        "features":     ["ADX"],               # optional list[str]
    }

Input dict format for KB entries:
    {
        "entry_id":      "kb_001",
        "hypothesis_id": "H-13",
        "finding":       "ADX threshold <= 25 has zero effect",
        "confidence":    0.9,
        "source_ref":    "knowledge_base/entry_001.json",
    }

Results saved to:
    {data_dir}/knowledge/snapshots/{campaign_id}.json
    {data_dir}/knowledge/graph/{campaign_id}.json
    {data_dir}/knowledge/patterns/{campaign_id}.json
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
    EvidenceRef,
    KnowledgeConnection,
    KnowledgeFact,
    KnowledgePattern,
    KnowledgeSnapshot,
)

_AGENT_ID = "knowledge-agent"
_AGENT_TYPE = "KNOWLEDGE"
_VERSION = "1.0"

_STRONG_THRESHOLD = 0.7
_WEAK_THRESHOLD = 0.4
_MIN_PATTERN_OCCURRENCES = 2
_UNDERPERFORMANCE_THRESHOLD = 0.4
_OUTPERFORMANCE_THRESHOLD = 0.7
_PASS_FRACTION_POSITIVE = 0.6   # ≥ this → positive connection
_PASS_FRACTION_NEGATIVE = 0.4   # ≤ this → negative connection


# ---------------------------------------------------------------------------
# Source implementations
# ---------------------------------------------------------------------------

class FileKnowledgeSource:
    """Reads research report JSON files from disk.

    reports_dir: directory tree where {campaign_id}/*.json are report files
    kb_dir:      optional directory tree for knowledge-base entry JSON files
    """

    def __init__(
        self,
        reports_dir: Path,
        kb_dir: Optional[Path] = None,
    ) -> None:
        self._reports_dir = reports_dir
        self._kb_dir = kb_dir

    def load_reports(self, campaign_id: str) -> list[dict]:
        target = self._reports_dir / campaign_id
        if not target.exists():
            return []
        result: list[dict] = []
        for f in sorted(target.glob("*.json")):
            with open(f, encoding="utf-8") as fp:
                result.append(json.load(fp))
        return result

    def load_kb_entries(self, campaign_id: str) -> list[dict]:
        if self._kb_dir is None:
            return []
        target = self._kb_dir / campaign_id
        if not target.exists():
            return []
        result: list[dict] = []
        for f in sorted(target.glob("*.json")):
            with open(f, encoding="utf-8") as fp:
                result.append(json.load(fp))
        return result


class FixtureKnowledgeSource:
    """Pre-baked reports and KB entries — no file I/O.  Use in tests."""

    def __init__(
        self,
        reports: list[dict],
        kb_entries: Optional[list[dict]] = None,
    ) -> None:
        self._reports = list(reports)
        self._kb_entries = list(kb_entries or [])

    def load_reports(self, campaign_id: str) -> list[dict]:
        return list(self._reports)

    def load_kb_entries(self, campaign_id: str) -> list[dict]:
        return list(self._kb_entries)


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------

def _facts_from_report(report: dict, idx: int) -> list[KnowledgeFact]:
    """Convert one research report dict to a KnowledgeFact."""
    hyp_id = str(report.get("hypothesis_id", ""))
    instrument = str(report.get("instrument", ""))
    period = str(report.get("period", ""))
    regime = str(report.get("regime_label", ""))
    raw_pr = report.get("pass_rate")
    pass_rate = float(raw_pr) if raw_pr is not None else math.nan
    raw_passed = report.get("passed")
    passed: Optional[bool] = bool(raw_passed) if raw_passed is not None else None
    confidence = float(report.get("confidence", 0.5))
    source_ref = str(report.get("source_ref", f"report_{idx}"))
    features: list[str] = [str(f) for f in report.get("features", [])]

    safe_hyp = hyp_id.lower().replace("-", "").replace(" ", "_")
    regime_tag = regime.lower() if regime else "any"
    fact_id = f"fact_{idx:04d}_{safe_hyp}_{instrument.lower()}_{regime_tag}"

    return [KnowledgeFact(
        fact_id=fact_id,
        source_type="research_report",
        source_ref=source_ref,
        hypothesis_id=hyp_id,
        instrument=instrument,
        period=period,
        regime=regime,
        metric="pass_rate",
        value=pass_rate,
        passed=passed,
        confidence=confidence,
        tags=tuple(features),
    )]


def _facts_from_kb_entry(entry: dict, idx: int) -> list[KnowledgeFact]:
    """Convert one KB entry dict to a KnowledgeFact."""
    hyp_id = str(entry.get("hypothesis_id", ""))
    confidence = float(entry.get("confidence", 0.5))
    source_ref = str(entry.get("source_ref", f"kb_{idx}"))
    finding = str(entry.get("finding", ""))

    safe_hyp = hyp_id.lower().replace("-", "").replace(" ", "_")
    fact_id = f"kb_{idx:04d}_{safe_hyp}"

    return [KnowledgeFact(
        fact_id=fact_id,
        source_type="knowledge_base",
        source_ref=source_ref,
        hypothesis_id=hyp_id,
        instrument="",
        period="",
        regime="",
        metric="kb_finding",
        value=confidence,
        passed=None,
        confidence=confidence,
        tags=(finding[:80],) if finding else (),
    )]


# ---------------------------------------------------------------------------
# Connection graph
# ---------------------------------------------------------------------------

def _build_connections(facts: list[KnowledgeFact]) -> list[KnowledgeConnection]:
    """Build hypothesis ↔ regime connections from facts that have both fields."""
    groups: dict[tuple[str, str], list[KnowledgeFact]] = {}
    for f in facts:
        if f.hypothesis_id and f.regime:
            groups.setdefault((f.hypothesis_id, f.regime), []).append(f)

    connections: list[KnowledgeConnection] = []
    for (hyp_id, regime), group in sorted(groups.items()):
        pass_count = sum(1 for f in group if f.passed is True)
        fail_count = sum(1 for f in group if f.passed is False)
        total = len(group)

        pass_fraction = pass_count / total if total > 0 else 0.5

        if pass_fraction >= _PASS_FRACTION_POSITIVE:
            relation = "positive"
        elif pass_fraction <= _PASS_FRACTION_NEGATIVE:
            relation = "negative"
        else:
            relation = "neutral"

        strength = round(abs(pass_fraction - 0.5) * 2.0, 6)
        safe = hyp_id.lower().replace("-", "").replace(" ", "_")
        conn_id = f"conn_{safe}_{regime.lower()}"

        connections.append(KnowledgeConnection(
            connection_id=conn_id,
            entity_a=hyp_id,
            entity_b=regime,
            relation=relation,
            strength=strength,
            support_count=total,
            evidence=tuple(f.fact_id for f in group),
        ))

    return connections


# ---------------------------------------------------------------------------
# Pattern discovery
# ---------------------------------------------------------------------------

def _discover_patterns(facts: list[KnowledgeFact]) -> list[KnowledgePattern]:
    """Find recurring patterns across facts using deterministic rules."""
    patterns: list[KnowledgePattern] = []
    pat_idx = 0

    # --- 1. Regime-hypothesis patterns (need ≥ MIN occurrences) ---
    rg_groups: dict[tuple[str, str], list[KnowledgeFact]] = {}
    for f in facts:
        if f.hypothesis_id and f.regime:
            rg_groups.setdefault((f.hypothesis_id, f.regime), []).append(f)

    for (hyp_id, regime), group in sorted(rg_groups.items()):
        if len(group) < _MIN_PATTERN_OCCURRENCES:
            continue

        all_fail = all(f.passed is False for f in group)
        all_pass = all(f.passed is True for f in group)

        if all_fail or all_pass:
            pat_idx += 1
            outcome = "FAILS" if all_fail else "PASSES"
            patterns.append(KnowledgePattern(
                pattern_id=f"pat_{pat_idx:04d}",
                description=f"{hyp_id} consistently {outcome} in {regime}",
                pattern_type="regime_hypothesis",
                entities=(hyp_id, regime),
                occurrence_count=len(group),
                confidence=round(min(1.0, len(group) / 5.0), 6),
                supporting_facts=tuple(f.fact_id for f in group),
                contradicting_facts=(),
            ))

    # --- 2. Underperformance / outperformance across hypothesis ---
    hyp_groups: dict[str, list[KnowledgeFact]] = {}
    for f in facts:
        if f.hypothesis_id and f.metric == "pass_rate" and not math.isnan(f.value):
            hyp_groups.setdefault(f.hypothesis_id, []).append(f)

    for hyp_id, group in sorted(hyp_groups.items()):
        if len(group) < _MIN_PATTERN_OCCURRENCES:
            continue
        avg_pr = sum(f.value for f in group) / len(group)

        if avg_pr < _UNDERPERFORMANCE_THRESHOLD:
            pat_idx += 1
            patterns.append(KnowledgePattern(
                pattern_id=f"pat_{pat_idx:04d}",
                description=(
                    f"{hyp_id} consistently underperforms "
                    f"(avg pass_rate={avg_pr:.2f})"
                ),
                pattern_type="underperformance",
                entities=(hyp_id,),
                occurrence_count=len(group),
                confidence=round(
                    min(1.0, (_UNDERPERFORMANCE_THRESHOLD - avg_pr) * 2.5), 6
                ),
                supporting_facts=tuple(f.fact_id for f in group),
                contradicting_facts=(),
            ))
        elif avg_pr > _OUTPERFORMANCE_THRESHOLD:
            pat_idx += 1
            patterns.append(KnowledgePattern(
                pattern_id=f"pat_{pat_idx:04d}",
                description=(
                    f"{hyp_id} consistently outperforms "
                    f"(avg pass_rate={avg_pr:.2f})"
                ),
                pattern_type="outperformance",
                entities=(hyp_id,),
                occurrence_count=len(group),
                confidence=round(
                    min(1.0, (avg_pr - _OUTPERFORMANCE_THRESHOLD) * 3.0), 6
                ),
                supporting_facts=tuple(f.fact_id for f in group),
                contradicting_facts=(),
            ))

    return patterns


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------

def _detect_contradictions(facts: list[KnowledgeFact]) -> list[str]:
    """Return descriptions of fact groups with conflicting passed values.

    Groups facts by (hypothesis_id, regime, instrument).  Flags groups
    where both passed=True and passed=False appear.
    """
    groups: dict[tuple[str, str, str], list[KnowledgeFact]] = {}
    for f in facts:
        if f.hypothesis_id and f.passed is not None:
            groups.setdefault((f.hypothesis_id, f.regime, f.instrument), []).append(f)

    contradictions: list[str] = []
    for (hyp_id, regime, instrument), group in sorted(groups.items()):
        has_pass = any(f.passed is True for f in group)
        has_fail = any(f.passed is False for f in group)
        if has_pass and has_fail:
            regime_part = f" in {regime}" if regime else ""
            instr_part = f" for {instrument}" if instrument else ""
            contradictions.append(
                f"Contradiction: {hyp_id}{regime_part}{instr_part} "
                f"shows conflicting results"
            )

    return sorted(contradictions)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _make_recommendations(
    patterns: list[KnowledgePattern],
    contradictions: list[str],
) -> list[str]:
    recs: list[str] = []

    for p in sorted(patterns, key=lambda x: x.pattern_id):
        ent = list(p.entities)
        if p.pattern_type == "regime_hypothesis":
            if "FAILS" in p.description:
                recs.append(
                    f"Avoid {ent[0]} strategy in {ent[1]} conditions"
                )
            else:
                recs.append(
                    f"Prioritize {ent[0]} when regime is {ent[1]}"
                )
        elif p.pattern_type == "underperformance":
            recs.append(
                f"Review and revise {ent[0]} — consistently underperforms"
            )
        elif p.pattern_type == "outperformance":
            recs.append(
                f"Expand {ent[0]} testing across more instruments and periods"
            )

    for c in contradictions:
        recs.append(f"Resolve conflicting evidence: {c}")

    # Deduplicate preserving insertion order
    seen: set[str] = set()
    unique: list[str] = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return sorted(unique)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _write_snapshot(data_dir: Path, snap: KnowledgeSnapshot) -> Path:
    out = data_dir / "knowledge" / "snapshots"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{snap.campaign_id}.json"

    def _fact(f: KnowledgeFact) -> dict:
        return {
            "fact_id": f.fact_id,
            "source_type": f.source_type,
            "source_ref": f.source_ref,
            "hypothesis_id": f.hypothesis_id,
            "instrument": f.instrument,
            "period": f.period,
            "regime": f.regime,
            "metric": f.metric,
            "value": None if math.isnan(f.value) else f.value,
            "passed": f.passed,
            "confidence": f.confidence,
            "tags": list(f.tags),
        }

    payload = {
        "snapshot_id": snap.snapshot_id,
        "campaign_id": snap.campaign_id,
        "facts": [_fact(f) for f in snap.facts],
        "strong_facts": list(snap.strong_facts),
        "weak_facts": list(snap.weak_facts),
        "contradictions": list(snap.contradictions),
        "recommendations": list(snap.recommendations),
        "confidence_value": snap.confidence.value,
        "confidence_reason": snap.confidence.reason,
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    return path


def _write_graph(data_dir: Path, snap: KnowledgeSnapshot) -> Path:
    out = data_dir / "knowledge" / "graph"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{snap.campaign_id}.json"

    payload = {
        "campaign_id": snap.campaign_id,
        "connections": [
            {
                "connection_id": c.connection_id,
                "entity_a": c.entity_a,
                "entity_b": c.entity_b,
                "relation": c.relation,
                "strength": c.strength,
                "support_count": c.support_count,
                "evidence": list(c.evidence),
            }
            for c in snap.connections
        ],
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    return path


def _write_patterns(data_dir: Path, snap: KnowledgeSnapshot) -> Path:
    out = data_dir / "knowledge" / "patterns"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{snap.campaign_id}.json"

    payload = {
        "campaign_id": snap.campaign_id,
        "patterns": [
            {
                "pattern_id": p.pattern_id,
                "description": p.description,
                "pattern_type": p.pattern_type,
                "entities": list(p.entities),
                "occurrence_count": p.occurrence_count,
                "confidence": p.confidence,
                "supporting_facts": list(p.supporting_facts),
                "contradicting_facts": list(p.contradicting_facts),
            }
            for p in snap.patterns
        ],
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# KnowledgeAgent
# ---------------------------------------------------------------------------

class KnowledgeAgent:
    """Layer 3 KNOWLEDGE Agent — deterministic knowledge aggregation.

    Reads research reports and KB entries via injected source, extracts
    structured facts, builds a connection graph and discovers patterns,
    then saves the full KnowledgeSnapshot to disk.

    Inject FixtureKnowledgeSource for deterministic tests.
    """

    agent_id = _AGENT_ID
    agent_type = _AGENT_TYPE
    version = _VERSION

    def __init__(
        self,
        data_dir: Path,
        source: Optional[object] = None,
    ) -> None:
        self._data_dir = data_dir
        self._source = source or FileKnowledgeSource(data_dir / "reports")

    def run(
        self,
        campaign_id: str,
        _clock: Optional[Callable[[], datetime]] = None,
    ) -> AgentResult:
        """Aggregate knowledge for campaign_id and return a KnowledgeSnapshot.

        Parameters
        ----------
        campaign_id: identifier used in snapshot_id and file names
        _clock:      injected clock for reproducible created_at timestamps
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")

        # --- load ---
        reports = self._source.load_reports(campaign_id)
        kb_entries = self._source.load_kb_entries(campaign_id)

        # --- aggregate facts ---
        all_facts: list[KnowledgeFact] = []
        for i, r in enumerate(reports):
            all_facts.extend(_facts_from_report(r, i))
        for i, e in enumerate(kb_entries):
            all_facts.extend(_facts_from_kb_entry(e, i))

        # --- build knowledge structures ---
        connections = _build_connections(all_facts)
        patterns = _discover_patterns(all_facts)
        contradictions = _detect_contradictions(all_facts)
        recommendations = _make_recommendations(patterns, contradictions)

        # --- classify facts ---
        strong = tuple(f.fact_id for f in all_facts if f.confidence >= _STRONG_THRESHOLD)
        weak = tuple(f.fact_id for f in all_facts if f.confidence < _WEAK_THRESHOLD)

        # --- evidence refs ---
        evidence: list[EvidenceRef] = [
            EvidenceRef(
                source=f"campaign/{campaign_id}",
                reference=f"reports/{campaign_id}",
                timestamp=created_at,
            )
        ]
        if kb_entries:
            evidence.append(EvidenceRef(
                source="knowledge_base",
                reference=f"knowledge_base/{campaign_id}",
                timestamp=created_at,
            ))

        # --- snapshot confidence ---
        if all_facts:
            mean_conf = sum(f.confidence for f in all_facts) / len(all_facts)
            pattern_boost = min(0.2, 0.05 * len(patterns))
            conf_value = round(min(1.0, mean_conf + pattern_boost), 6)
        else:
            conf_value = 0.0

        snapshot = KnowledgeSnapshot(
            snapshot_id=f"knowledge_{campaign_id}",
            campaign_id=campaign_id,
            facts=tuple(all_facts),
            connections=tuple(connections),
            patterns=tuple(patterns),
            strong_facts=strong,
            weak_facts=weak,
            contradictions=tuple(contradictions),
            recommendations=tuple(recommendations),
            source_refs=tuple(evidence),
            confidence=ConfidenceScore(
                value=conf_value,
                reason=(
                    f"{len(all_facts)} facts, "
                    f"{len(patterns)} patterns, "
                    f"{len(connections)} connections"
                ),
            ),
        )

        _write_snapshot(self._data_dir, snapshot)
        _write_graph(self._data_dir, snapshot)
        _write_patterns(self._data_dir, snapshot)

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"knowledge {campaign_id} "
                f"{len(reports)} reports "
                f"{len(kb_entries)} kb_entries"
            ),
            output=snapshot,
            evidence=tuple(evidence),
            confidence=snapshot.confidence,
            created_at=created_at,
        )
