"""Knowledge Evolution Layer — M4 Sprint 2.

Transforms the Knowledge Base from a passive fact store into a self-learning
working memory: facts accumulate evidence, confidence drifts with outcomes,
weak facts are archived, conflicts are surfaced, and every ingest creates a
versioned snapshot so the history of the knowledge base is preserved.

Public API:
    store = KnowledgeStore(directory)
    delta = store.ingest(knowledge_snapshot)   # after each campaign
    report = store.build_report()
    diff   = store.diff(v_old, v_new)

No ML. No LLM. No broker calls. No git operations. No UI changes.
Reads only KnowledgeSnapshot (output of existing KnowledgeAgent).
Does NOT modify KnowledgeAgent, ResearchService, or AutonomousRuntime.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4


# ─────────────────────────────────────────────────────────────────────────────
# Tuning constants
# ─────────────────────────────────────────────────────────────────────────────

ARCHIVE_THRESHOLD: float = 0.15   # auto-archive fact below this confidence
DECAY_PER_DAY:     float = 0.02   # confidence loss per idle day (applied on read)
CONFIRM_BOOST:     float = 0.08   # confidence gain per confirmation (passed=True)
REFUTE_PENALTY:    float = 0.12   # confidence loss per refutation (passed=False)
MAX_CONFIDENCE:    float = 0.99


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FactScore:
    """Evolving quality metrics attached to one EnrichedFact."""
    confidence:     float  # current belief [0..1]
    evidence_count: int    # total observations merged
    success_count:  int    # observations where passed=True
    failure_count:  int    # observations where passed=False
    last_seen:      str    # ISO-8601 timestamp of most recent merge
    decay_score:    float  # 1.0 = freshly updated; decays with idle time
    stability_score: float # |pass - fail| / total; 1.0 = perfectly consistent


@dataclass
class EnrichedFact:
    """A KnowledgeFact merged with its accumulated FactScore."""
    fact_key:     str          # canonical merge key
    hypothesis_id: str
    instrument:   str
    period:       str
    regime:       str
    metric:       str

    score:        FactScore
    source_refs:  list         # all source_refs seen (for audit trail)
    archived:     bool         # True when confidence < ARCHIVE_THRESHOLD
    created_at:   str          # ISO-8601 of first observation
    last_value:   Optional[float]
    last_passed:  Optional[bool]
    updated_by:   str = ""     # audit trail: which script last wrote this fact


@dataclass
class ConflictRecord:
    """Two observations for the same phenomenon that disagree on `passed`."""
    conflict_id:   str
    fact_key:      str
    hypothesis_id: str
    instrument:    str
    period:        str
    regime:        str
    evidence_a:    str         # source_ref of earlier evidence
    evidence_b:    str         # source_ref of conflicting evidence
    passed_a:      Optional[bool]
    passed_b:      Optional[bool]
    detected_at:   str
    resolved:      bool = False
    resolution_note: str = ""


@dataclass
class EvolutionDelta:
    """Result of one KnowledgeStore.ingest() call."""
    version:              int
    ingested_at:          str
    campaign_id:          str
    facts_new:            int
    facts_updated:        int
    facts_archived:       int
    conflicts_new:        int
    avg_confidence_before: float
    avg_confidence_after:  float
    knowledge_score_delta: float    # (after − before) total knowledge score
    new_fact_keys:        list
    updated_fact_keys:    list
    archived_fact_keys:   list
    new_conflict_ids:     list


@dataclass
class EvolutionReport:
    """Comprehensive snapshot of the current state and evolution of the KB."""
    generated_at:          str
    store_version:         int
    total_facts:           int
    active_facts:          int
    archived_facts:        int
    total_conflicts:       int
    unresolved_conflicts:  int
    avg_confidence:        float
    total_knowledge_score: float    # sum of confidence × stability across active facts
    ingestion_count:       int
    recent_facts_added:    int      # last 5 ingestions
    recent_facts_updated:  int
    recent_facts_archived: int
    top_by_confidence:     list     # top-5 active facts
    bottom_by_confidence:  list     # bottom-5 active facts
    active_conflicts:      list
    recommendations:       list


@dataclass
class EvolutionDiff:
    """Comparison between two versioned snapshots."""
    version_from:    int
    version_to:      int
    generated_at:    str
    added_keys:      list      # fact_keys new in v_new
    removed_keys:    list      # fact_keys gone from v_new (archived)
    changed_keys:    list      # fact_keys present in both but different
    confidence_delta: dict     # fact_key -> {"before": x, "after": y, "delta": z}
    summary: str


# ─────────────────────────────────────────────────────────────────────────────
# Fact key helper
# ─────────────────────────────────────────────────────────────────────────────

def _fact_key(hypothesis_id: str, instrument: str, period: str, regime: str) -> str:
    """Canonical merge key — same phenomenon across campaigns."""
    parts = [
        hypothesis_id.strip() or "unknown",
        instrument.strip()    or "all",
        period.strip()        or "all",
        regime.strip()        or "any",
    ]
    return "__".join(parts)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _days_since(iso_ts: str) -> float:
    try:
        past = datetime.fromisoformat(iso_ts)
        if past.tzinfo is None:
            past = past.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - past
        return delta.total_seconds() / 86400.0
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Merge logic
# ─────────────────────────────────────────────────────────────────────────────

def _create_enriched(fact_key: str, kf_dict: dict, now: str) -> EnrichedFact:
    """Create a brand-new EnrichedFact from a raw KnowledgeFact-like dict."""
    passed = kf_dict.get("passed")
    success = 1 if passed is True  else 0
    failure = 1 if passed is False else 0

    return EnrichedFact(
        fact_key      = fact_key,
        hypothesis_id = kf_dict.get("hypothesis_id", ""),
        instrument    = kf_dict.get("instrument", ""),
        period        = kf_dict.get("period", ""),
        regime        = kf_dict.get("regime", ""),
        metric        = kf_dict.get("metric", "pass_rate"),
        score         = FactScore(
            confidence      = float(kf_dict.get("confidence", 0.5)),
            evidence_count  = 1,
            success_count   = success,
            failure_count   = failure,
            last_seen       = now,
            decay_score     = 1.0,
            stability_score = 1.0,
        ),
        source_refs  = [str(kf_dict.get("source_ref", ""))],
        archived     = False,
        created_at   = now,
        last_value   = kf_dict.get("value"),
        last_passed  = passed,
    )


def _merge_into(existing: EnrichedFact, kf_dict: dict, now: str) -> tuple[EnrichedFact, bool]:
    """Merge new observation into existing EnrichedFact.

    Returns (updated_fact, was_archived_this_merge).
    """
    passed      = kf_dict.get("passed")
    new_conf    = float(kf_dict.get("confidence", 0.5))
    old_conf    = existing.score.confidence
    ev_count    = existing.score.evidence_count
    success     = existing.score.success_count
    failure     = existing.score.failure_count

    # ── Update confidence based on outcome ────────────────────────────────
    if passed is True:
        updated_conf = min(MAX_CONFIDENCE, old_conf + CONFIRM_BOOST * (1.0 - old_conf))
        success += 1
    elif passed is False:
        updated_conf = max(0.0, old_conf - REFUTE_PENALTY * old_conf)
        failure += 1
    else:
        # Neutral: weighted average with new observation
        updated_conf = (old_conf * ev_count + new_conf) / (ev_count + 1)

    ev_count += 1

    # ── Stability: how consistently passed/failed ──────────────────────────
    total = success + failure
    stability = abs(success - failure) / total if total > 0 else 0.5

    # ── Auto-archive ──────────────────────────────────────────────────────
    newly_archived = not existing.archived and (updated_conf < ARCHIVE_THRESHOLD)

    # ── Source refs dedup ─────────────────────────────────────────────────
    src = existing.source_refs.copy()
    new_src = str(kf_dict.get("source_ref", ""))
    if new_src and new_src not in src:
        src.append(new_src)

    updated = EnrichedFact(
        fact_key      = existing.fact_key,
        hypothesis_id = existing.hypothesis_id,
        instrument    = existing.instrument,
        period        = existing.period,
        regime        = existing.regime,
        metric        = existing.metric,
        score         = FactScore(
            confidence      = round(updated_conf, 6),
            evidence_count  = ev_count,
            success_count   = success,
            failure_count   = failure,
            last_seen       = now,
            decay_score     = 1.0,
            stability_score = round(stability, 6),
        ),
        source_refs  = src,
        archived     = existing.archived or newly_archived,
        created_at   = existing.created_at,
        last_value   = kf_dict.get("value", existing.last_value),
        last_passed  = passed if passed is not None else existing.last_passed,
    )
    return updated, newly_archived


# ─────────────────────────────────────────────────────────────────────────────
# Conflict detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_conflicts(
    existing: dict,                 # fact_key -> EnrichedFact
    new_facts: list,                # list of (fact_key, kf_dict)
    now: str,
) -> list[ConflictRecord]:
    """Find facts where existing.last_passed contradicts new observation."""
    conflicts: list[ConflictRecord] = []

    for fkey, kf in new_facts:
        new_passed = kf.get("passed")
        if new_passed is None:
            continue
        ef = existing.get(fkey)
        if ef is None or ef.last_passed is None:
            continue
        if ef.last_passed != new_passed:
            conflicts.append(ConflictRecord(
                conflict_id    = f"conflict_{uuid4().hex[:8]}",
                fact_key       = fkey,
                hypothesis_id  = kf.get("hypothesis_id", ef.hypothesis_id),
                instrument     = kf.get("instrument", ef.instrument),
                period         = kf.get("period", ef.period),
                regime         = kf.get("regime", ef.regime),
                evidence_a     = ef.source_refs[-1] if ef.source_refs else "",
                evidence_b     = str(kf.get("source_ref", "")),
                passed_a       = ef.last_passed,
                passed_b       = new_passed,
                detected_at    = now,
            ))

    return conflicts


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _score_to_dict(s: FactScore) -> dict:
    return asdict(s)


def _ef_to_dict(ef: EnrichedFact) -> dict:
    d = asdict(ef)
    return d


def _ef_from_dict(d: dict) -> EnrichedFact:
    score = FactScore(**d["score"])
    d2 = dict(d)
    d2["score"] = score
    return EnrichedFact(**d2)


def _cr_to_dict(c: ConflictRecord) -> dict:
    return asdict(c)


def _cr_from_dict(d: dict) -> ConflictRecord:
    return ConflictRecord(**d)


def _delta_to_dict(delta: EvolutionDelta) -> dict:
    return asdict(delta)


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Score aggregate
# ─────────────────────────────────────────────────────────────────────────────

def _total_knowledge_score(facts: dict) -> float:
    """Sum of confidence × stability for all active (non-archived) facts."""
    total = 0.0
    for ef in facts.values():
        if not ef.archived:
            total += ef.score.confidence * ef.score.stability_score
    return round(total, 4)


def _avg_confidence(facts: dict) -> float:
    active = [ef for ef in facts.values() if not ef.archived]
    if not active:
        return 0.0
    return round(sum(ef.score.confidence for ef in active) / len(active), 6)


# ─────────────────────────────────────────────────────────────────────────────
# KnowledgeStore
# ─────────────────────────────────────────────────────────────────────────────

_STORE_FILE      = "store.json"
_CONFLICTS_FILE  = "conflicts.json"
_DELTAS_FILE     = "deltas.json"
_VERSIONS_SUBDIR = "versions"
_REPORTS_SUBDIR  = "evolution_reports"


class KnowledgeStore:
    """Persistent evolving knowledge store for the MOEX AI research system.

    Directory layout::

        {store_dir}/
          store.json            — current enriched facts (dict by fact_key)
          conflicts.json        — all ConflictRecords ever detected
          deltas.json           — list of EvolutionDeltas (one per ingest)
          versions/
            knowledge_snapshot_v001.json
            knowledge_snapshot_v002.json
          evolution_reports/
            {timestamp}.json
            {timestamp}.md

    Usage::

        store = KnowledgeStore(Path("data/knowledge/evolution"))
        delta = store.ingest(knowledge_snapshot)   # after each campaign
        report = store.build_report()
        diff   = store.diff(41, 42)
    """

    def __init__(self, store_dir: Path) -> None:
        self._dir = store_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / _VERSIONS_SUBDIR).mkdir(exist_ok=True)
        (self._dir / _REPORTS_SUBDIR).mkdir(exist_ok=True)

        self._facts:     dict            = {}      # fact_key -> EnrichedFact
        self._conflicts: list            = []      # ConflictRecord list
        self._deltas:    list            = []      # EvolutionDelta list
        self._version:   int             = 0
        self._ingestion_count: int       = 0

        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def version(self) -> int:
        return self._version

    @property
    def ingestion_count(self) -> int:
        return self._ingestion_count

    def ingest(self, snapshot) -> EvolutionDelta:
        """Process a KnowledgeSnapshot, updating the store.

        Accepts either a `KnowledgeSnapshot` object (from KnowledgeAgent) or
        a plain list of fact-dicts for testability.

        Returns an EvolutionDelta describing what changed.
        """
        now = _now_iso()

        # ── Normalise input ───────────────────────────────────────────────
        if isinstance(snapshot, list):
            raw_facts = snapshot
            campaign_id = "manual"
        else:
            # KnowledgeSnapshot from KnowledgeAgent
            campaign_id = getattr(snapshot, "campaign_id", "unknown")
            raw_facts = [self._kf_to_dict(f) for f in snapshot.facts]

        if not raw_facts:
            # Nothing to ingest — still bump version for audit trail
            delta = EvolutionDelta(
                version=self._version,
                ingested_at=now,
                campaign_id=campaign_id,
                facts_new=0, facts_updated=0, facts_archived=0, conflicts_new=0,
                avg_confidence_before=_avg_confidence(self._facts),
                avg_confidence_after=_avg_confidence(self._facts),
                knowledge_score_delta=0.0,
                new_fact_keys=[], updated_fact_keys=[],
                archived_fact_keys=[], new_conflict_ids=[],
            )
            return delta

        # ── Pre-snapshot metrics ──────────────────────────────────────────
        avg_conf_before = _avg_confidence(self._facts)
        ks_before       = _total_knowledge_score(self._facts)

        # ── Build keyed list for conflict detection ───────────────────────
        keyed: list[tuple[str, dict]] = []
        for kf in raw_facts:
            k = _fact_key(
                kf.get("hypothesis_id", ""),
                kf.get("instrument", ""),
                kf.get("period", ""),
                kf.get("regime", ""),
            )
            keyed.append((k, kf))

        # ── Detect conflicts BEFORE merging (compare against current state) ─
        new_conflicts = _detect_conflicts(self._facts, keyed, now)
        self._conflicts.extend(new_conflicts)

        # ── Merge facts ───────────────────────────────────────────────────
        new_keys:      list = []
        updated_keys:  list = []
        archived_keys: list = []

        for fkey, kf in keyed:
            if fkey in self._facts:
                updated, newly_archived = _merge_into(self._facts[fkey], kf, now)
                self._facts[fkey] = updated
                updated_keys.append(fkey)
                if newly_archived:
                    archived_keys.append(fkey)
            else:
                self._facts[fkey] = _create_enriched(fkey, kf, now)
                new_keys.append(fkey)

        # ── Post-snapshot metrics ─────────────────────────────────────────
        avg_conf_after = _avg_confidence(self._facts)
        ks_after       = _total_knowledge_score(self._facts)

        # ── Version bump + snapshot ───────────────────────────────────────
        self._version        += 1
        self._ingestion_count += 1
        self._write_version_snapshot(now)

        # ── Build delta ───────────────────────────────────────────────────
        delta = EvolutionDelta(
            version               = self._version,
            ingested_at           = now,
            campaign_id           = campaign_id,
            facts_new             = len(new_keys),
            facts_updated         = len(updated_keys),
            facts_archived        = len(archived_keys),
            conflicts_new         = len(new_conflicts),
            avg_confidence_before = avg_conf_before,
            avg_confidence_after  = avg_conf_after,
            knowledge_score_delta = round(ks_after - ks_before, 4),
            new_fact_keys         = new_keys,
            updated_fact_keys     = updated_keys,
            archived_fact_keys    = archived_keys,
            new_conflict_ids      = [c.conflict_id for c in new_conflicts],
        )
        self._deltas.append(delta)

        # ── Persist ───────────────────────────────────────────────────────
        self._save()

        return delta

    def build_report(self) -> EvolutionReport:
        """Generate a comprehensive EvolutionReport from current store state."""
        now    = _now_iso()
        active = [ef for ef in self._facts.values() if not ef.archived]
        arch   = [ef for ef in self._facts.values() if ef.archived]
        unconfl = [c for c in self._conflicts if not c.resolved]

        avg_conf = _avg_confidence(self._facts)
        ks       = _total_knowledge_score(self._facts)

        # Recent 5 ingestions summary
        recent = self._deltas[-5:]
        r_added   = sum(d.facts_new      for d in recent)
        r_updated = sum(d.facts_updated  for d in recent)
        r_archived= sum(d.facts_archived for d in recent)

        # Top/bottom by confidence
        sorted_active = sorted(active, key=lambda e: e.score.confidence, reverse=True)
        top5   = [self._ef_summary(e) for e in sorted_active[:5]]
        bottom5= [self._ef_summary(e) for e in sorted_active[-5:] if sorted_active]

        recs = self._build_recommendations(active, unconfl)

        report = EvolutionReport(
            generated_at          = now,
            store_version         = self._version,
            total_facts           = len(self._facts),
            active_facts          = len(active),
            archived_facts        = len(arch),
            total_conflicts       = len(self._conflicts),
            unresolved_conflicts  = len(unconfl),
            avg_confidence        = avg_conf,
            total_knowledge_score = ks,
            ingestion_count       = self._ingestion_count,
            recent_facts_added    = r_added,
            recent_facts_updated  = r_updated,
            recent_facts_archived = r_archived,
            top_by_confidence     = top5,
            bottom_by_confidence  = bottom5,
            active_conflicts      = [_cr_to_dict(c) for c in unconfl[:10]],
            recommendations       = recs,
        )

        self._write_report(report)
        return report

    def diff(self, v_old: int, v_new: int) -> EvolutionDiff:
        """Compare two versioned snapshots and return an EvolutionDiff."""
        snap_old = self._load_version(v_old)
        snap_new = self._load_version(v_new)

        if snap_old is None:
            raise FileNotFoundError(f"Version snapshot v{v_old:03d} not found")
        if snap_new is None:
            raise FileNotFoundError(f"Version snapshot v{v_new:03d} not found")

        facts_old: dict = snap_old.get("facts", {})
        facts_new: dict = snap_new.get("facts", {})

        keys_old = set(facts_old)
        keys_new = set(facts_new)

        added   = sorted(keys_new - keys_old)
        removed = sorted(keys_old - keys_new)
        common  = keys_old & keys_new
        changed = sorted(
            k for k in common
            if facts_old[k].get("score", {}).get("confidence")
            != facts_new[k].get("score", {}).get("confidence")
        )

        conf_delta: dict = {}
        for k in changed:
            before = facts_old[k].get("score", {}).get("confidence", 0.0)
            after  = facts_new[k].get("score", {}).get("confidence", 0.0)
            conf_delta[k] = {
                "before": round(before, 4),
                "after":  round(after,  4),
                "delta":  round(after - before, 4),
            }

        summary_parts = [
            f"v{v_old} -> v{v_new}:",
            f"+{len(added)} new facts,",
            f"-{len(removed)} archived,",
            f"~{len(changed)} changed",
        ]
        if conf_delta:
            avg_d = sum(v["delta"] for v in conf_delta.values()) / len(conf_delta)
            summary_parts.append(f"(avg confidence delta {avg_d:+.3f})")

        return EvolutionDiff(
            version_from     = v_old,
            version_to       = v_new,
            generated_at     = _now_iso(),
            added_keys       = added,
            removed_keys     = removed,
            changed_keys     = changed,
            confidence_delta = conf_delta,
            summary          = " ".join(summary_parts),
        )

    def get_fact(self, fact_key: str) -> Optional[EnrichedFact]:
        return self._facts.get(fact_key)

    def all_facts(self) -> dict:
        return dict(self._facts)

    def active_facts(self) -> list:
        return [ef for ef in self._facts.values() if not ef.archived]

    def archived_facts(self) -> list:
        return [ef for ef in self._facts.values() if ef.archived]

    def all_conflicts(self) -> list:
        return list(self._conflicts)

    def unresolved_conflicts(self) -> list:
        return [c for c in self._conflicts if not c.resolved]

    def resolve_conflict(self, conflict_id: str, note: str = "") -> bool:
        for c in self._conflicts:
            if c.conflict_id == conflict_id:
                c.resolved = True
                c.resolution_note = note
                self._save()
                return True
        return False

    def apply_decay(self) -> dict:
        """Apply time-based confidence decay to all facts not seen recently.

        Returns {fact_key: days_idle} for every fact that was decayed.
        """
        now    = _now_iso()
        decayed: dict = {}
        for key, ef in self._facts.items():
            if ef.archived:
                continue
            days = _days_since(ef.score.last_seen)
            if days < 1.0:
                continue
            decay      = DECAY_PER_DAY * days
            new_conf   = max(0.0, ef.score.confidence - decay)
            new_decay  = max(0.0, ef.score.decay_score - decay)
            newly_arch = not ef.archived and (new_conf < ARCHIVE_THRESHOLD)
            updated    = EnrichedFact(
                **{**asdict(ef),
                   "score": FactScore(
                       **{**asdict(ef.score),
                          "confidence":  round(new_conf,  6),
                          "decay_score": round(new_decay, 6),
                       }),
                   "archived": ef.archived or newly_arch,
                })
            self._facts[key] = updated
            decayed[key] = round(days, 1)
        if decayed:
            self._save()
        return decayed

    # ── Private: serialisation ────────────────────────────────────────────────

    def _load(self) -> None:
        sp = self._dir / _STORE_FILE
        if sp.exists():
            data = json.loads(sp.read_text(encoding="utf-8"))
            self._version         = data.get("version", 0)
            self._ingestion_count = data.get("ingestion_count", 0)
            self._facts = {
                k: _ef_from_dict(v) for k, v in data.get("facts", {}).items()
            }

        cp = self._dir / _CONFLICTS_FILE
        if cp.exists():
            raw = json.loads(cp.read_text(encoding="utf-8"))
            self._conflicts = [_cr_from_dict(c) for c in raw]

        dp = self._dir / _DELTAS_FILE
        if dp.exists():
            raw = json.loads(dp.read_text(encoding="utf-8"))
            self._deltas = [EvolutionDelta(**d) for d in raw]

    def _save(self) -> None:
        # store.json
        payload: dict = {
            "version":         self._version,
            "ingestion_count": self._ingestion_count,
            "updated_at":      _now_iso(),
            "facts":           {k: _ef_to_dict(v) for k, v in self._facts.items()},
        }
        (self._dir / _STORE_FILE).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # conflicts.json
        (self._dir / _CONFLICTS_FILE).write_text(
            json.dumps([_cr_to_dict(c) for c in self._conflicts], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # deltas.json
        (self._dir / _DELTAS_FILE).write_text(
            json.dumps([_delta_to_dict(d) for d in self._deltas], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_version_snapshot(self, now: str) -> None:
        active = [ef for ef in self._facts.values() if not ef.archived]
        snap = {
            "version":        self._version,
            "generated_at":   now,
            "total_facts":    len(self._facts),
            "active_facts":   len(active),
            "archived_facts": len(self._facts) - len(active),
            "avg_confidence": _avg_confidence(self._facts),
            "knowledge_score":_total_knowledge_score(self._facts),
            "facts":          {k: _ef_to_dict(v) for k, v in self._facts.items()},
        }
        fname = f"knowledge_snapshot_v{self._version:03d}.json"
        (self._dir / _VERSIONS_SUBDIR / fname).write_text(
            json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load_version(self, v: int) -> Optional[dict]:
        fname = f"knowledge_snapshot_v{v:03d}.json"
        path  = self._dir / _VERSIONS_SUBDIR / fname
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_report(self, report: EvolutionReport) -> None:
        rdir   = self._dir / _REPORTS_SUBDIR
        ts     = report.generated_at.replace(":", "").replace("+", "")[:15]
        jpath  = rdir / f"{ts}.json"
        mdpath = rdir / f"{ts}.md"

        jpath.write_text(
            json.dumps(asdict(report), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        mdpath.write_text(self._build_report_md(report), encoding="utf-8")

    # ── Private: report helpers ───────────────────────────────────────────────

    @staticmethod
    def _ef_summary(ef: EnrichedFact) -> dict:
        return {
            "fact_key":      ef.fact_key,
            "hypothesis_id": ef.hypothesis_id,
            "instrument":    ef.instrument,
            "period":        ef.period,
            "confidence":    ef.score.confidence,
            "evidence_count":ef.score.evidence_count,
            "success_count": ef.score.success_count,
            "failure_count": ef.score.failure_count,
            "stability":     ef.score.stability_score,
            "last_seen":     ef.score.last_seen,
        }

    @staticmethod
    def _build_recommendations(
        active: list,
        conflicts: list,
    ) -> list:
        recs: list = []
        low_conf = [e for e in active if e.score.confidence < 0.3]
        high_ev  = [e for e in active if e.score.evidence_count >= 5]
        unstable = [e for e in active
                    if e.score.stability_score < 0.4 and e.score.evidence_count >= 3]

        if low_conf:
            recs.append(
                f"{len(low_conf)} fact(s) have confidence < 0.3 — consider more evidence "
                "or manual archiving."
            )
        if high_ev:
            top_ev = sorted(high_ev, key=lambda e: e.score.confidence, reverse=True)[:3]
            recs.append(
                f"High-evidence facts to promote: "
                + ", ".join(e.hypothesis_id + "/" + e.instrument for e in top_ev)
            )
        if conflicts:
            recs.append(
                f"{len(conflicts)} unresolved conflict(s) — ChiefScientist should review "
                "and run contradiction-replication experiments."
            )
        if unstable:
            hyp_ids = sorted(set(e.hypothesis_id for e in unstable))
            recs.append(
                f"Unstable hypotheses (inconsistent pass/fail): {', '.join(hyp_ids[:4])}"
            )
        if not recs:
            recs.append(
                "Knowledge Base looks healthy. Continue accumulating evidence."
            )
        return recs

    @staticmethod
    def _build_report_md(r: EvolutionReport) -> str:
        lines = [
            f"# Knowledge Evolution Report — v{r.store_version}",
            f"*Generated: {r.generated_at}*",
            "",
            "## Overview",
            "",
            f"| Metric                  | Value |",
            f"| ----------------------- | ----- |",
            f"| Store version           | {r.store_version} |",
            f"| Total facts             | {r.total_facts} |",
            f"| Active facts            | {r.active_facts} |",
            f"| Archived facts          | {r.archived_facts} |",
            f"| Total conflicts         | {r.total_conflicts} |",
            f"| Unresolved conflicts    | {r.unresolved_conflicts} |",
            f"| Average confidence      | {r.avg_confidence:.4f} |",
            f"| Total knowledge score   | {r.total_knowledge_score:.4f} |",
            f"| Total ingestions        | {r.ingestion_count} |",
            "",
            "## Recent Activity (last 5 ingestions)",
            "",
            f"| Metric   | Count |",
            f"| -------- | ----- |",
            f"| Added    | {r.recent_facts_added} |",
            f"| Updated  | {r.recent_facts_updated} |",
            f"| Archived | {r.recent_facts_archived} |",
            "",
            "## Top Facts by Confidence",
            "",
            "| Fact Key | Hypothesis | Confidence | Evidence | Stability |",
            "| -------- | ---------- | ---------- | -------- | --------- |",
        ]
        for f in r.top_by_confidence:
            lines.append(
                f"| {f['fact_key'][:35]} | {f['hypothesis_id'][:20]} | "
                f"{f['confidence']:.4f} | {f['evidence_count']} | {f['stability']:.2f} |"
            )

        if r.active_conflicts:
            lines += [
                "",
                "## Active Conflicts",
                "",
                "| ID | Fact Key | passed_a | passed_b |",
                "| -- | -------- | -------- | -------- |",
            ]
            for c in r.active_conflicts[:10]:
                lines.append(
                    f"| {c['conflict_id'][:20]} | {c['fact_key'][:35]} | "
                    f"{c['passed_a']} | {c['passed_b']} |"
                )

        if r.recommendations:
            lines += ["", "## Recommendations", ""]
            for rec in r.recommendations:
                lines.append(f"- {rec}")

        lines += ["", "---", f"*Knowledge Evolution Layer — M4 Sprint 2*"]
        return "\n".join(lines)

    # ── Private: KnowledgeFact → dict ─────────────────────────────────────────

    @staticmethod
    def _kf_to_dict(kf) -> dict:
        """Convert a KnowledgeFact dataclass to the canonical dict format."""
        return {
            "hypothesis_id": getattr(kf, "hypothesis_id", ""),
            "instrument":    getattr(kf, "instrument", ""),
            "period":        getattr(kf, "period", ""),
            "regime":        getattr(kf, "regime", ""),
            "metric":        getattr(kf, "metric", "pass_rate"),
            "value":         None if math.isnan(getattr(kf, "value", 0.0) or 0.0)
                             else getattr(kf, "value", None),
            "passed":        getattr(kf, "passed", None),
            "confidence":    getattr(kf, "confidence", 0.5),
            "source_ref":    getattr(kf, "source_ref", ""),
        }
