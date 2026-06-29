"""
M11.5 Architecture Bridge — ContinuousLearning Persistence

PROBLEM:
  ContinuousLearningPipeline.run_cycle() updates KnowledgeUpdater._facts
  in memory only. On next run, all learned facts are lost.
  The real KnowledgeStore (data/knowledge/evolution/store.json) never
  receives these updates → Continuous Learning is effectively stateless.

FIX (without modifying core services):
  This bridge script runs a learning cycle, reads the resulting facts
  from KnowledgeUpdater, and merges them into store.json using the
  same schema as knowledge_evolution.py.

Usage:
  python scripts/persist_learning_cycle.py --strategy BB_SQUEEZE --outcome FAIL
  python scripts/persist_learning_cycle.py --strategy DUAL_MA_TREND --outcome FAIL
  python scripts/persist_learning_cycle.py --status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

STORE_PATH = PROJECT_ROOT / "data" / "knowledge" / "evolution" / "store.json"


# ---------------------------------------------------------------------------
# Store I/O
# ---------------------------------------------------------------------------

def _load_store() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "ingestion_count": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "facts": {},
    }


def _save_store(store: dict) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Fact conversion: KnowledgeFact → store.json schema
# ---------------------------------------------------------------------------

def _kf_to_store_fact(kf, existing: dict | None = None) -> dict:
    """Convert KnowledgeFact dataclass to store.json fact schema."""
    now = datetime.now(timezone.utc).isoformat()
    fact_key = f"{kf.strategy_id}__{kf.instrument}__{kf.period}__{kf.metric}"

    if existing:
        # Increment evidence counters
        evidence_count = existing["score"]["evidence_count"] + 1
        if kf.value > 0:
            success_count = existing["score"]["success_count"] + 1
            failure_count = existing["score"]["failure_count"]
        else:
            success_count = existing["score"]["success_count"]
            failure_count = existing["score"]["failure_count"] + 1
        confidence = round(min(1.0, kf.confidence * (evidence_count / max(evidence_count, 3))), 5)
        source_refs = list(set(existing.get("source_refs", []) + [kf.source]))
        created_at = existing.get("created_at", now)
    else:
        evidence_count = 1
        success_count = 1 if kf.value > 0 else 0
        failure_count = 0 if kf.value > 0 else 1
        confidence = round(kf.confidence, 5)
        source_refs = [kf.source]
        created_at = now

    return {
        "fact_key": fact_key,
        "hypothesis_id": kf.strategy_id,
        "instrument": kf.instrument,
        "period": kf.period,
        "regime": "",
        "metric": kf.metric,
        "score": {
            "confidence": confidence,
            "evidence_count": evidence_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "last_seen": now,
            "decay_score": 1.0,
            "stability_score": round(1.0 - abs(kf.value - 0.5), 3),
        },
        "source_refs": source_refs,
        "archived": False,
        "created_at": created_at,
        "last_value": round(kf.value, 6),
        "last_passed": kf.value > 0.3,
        "updated_by": "persist_learning_cycle.py",
    }


# ---------------------------------------------------------------------------
# Run and persist
# ---------------------------------------------------------------------------

def run_cycle_and_persist(strategy_id: str, outcome: str) -> dict:
    """
    Run ContinuousLearningPipeline for one strategy, persist facts to store.json.
    Returns summary dict.
    """
    from services.continuous_learning.pipeline import ContinuousLearningPipeline

    pipeline = ContinuousLearningPipeline(PROJECT_ROOT)
    cycle = pipeline.simulate_post_research_update(strategy_id, outcome)

    ku = pipeline.get_knowledge_updater()
    new_facts = ku.get_all_facts()

    store = _load_store()
    facts_dict = store["facts"]

    added = 0
    updated = 0
    for kf in new_facts:
        fact_key = f"{kf.strategy_id}__{kf.instrument}__{kf.period}__{kf.metric}"
        existing = facts_dict.get(fact_key)
        facts_dict[fact_key] = _kf_to_store_fact(kf, existing)
        if existing:
            updated += 1
        else:
            added += 1

    store["version"] = store.get("version", 0) + 1
    store["ingestion_count"] = store.get("ingestion_count", 0) + 1
    store["updated_at"] = datetime.now(timezone.utc).isoformat()
    store["facts"] = facts_dict

    _save_store(store)

    summary = {
        "strategy_id": strategy_id,
        "outcome": outcome,
        "cycle_id": cycle.cycle_id,
        "events_processed": cycle.events_processed,
        "knowledge_facts_in_memory": ku.fact_count(),
        "facts_added_to_store": added,
        "facts_updated_in_store": updated,
        "store_total_facts": len(facts_dict),
        "store_version": store["version"],
    }
    return summary


def print_status() -> None:
    store = _load_store()
    print(f"Knowledge Store: {STORE_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  version:          {store['version']}")
    print(f"  ingestion_count:  {store['ingestion_count']}")
    print(f"  total_facts:      {len(store['facts'])}")
    print(f"  updated_at:       {store['updated_at']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Persist ContinuousLearning cycle to KnowledgeStore")
    parser.add_argument("--strategy", help="Strategy ID (e.g. BB_SQUEEZE)")
    parser.add_argument("--outcome", choices=["PASS", "FAIL"], default="FAIL")
    parser.add_argument("--status", action="store_true", help="Show current store status")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if not args.strategy:
        parser.error("--strategy is required unless --status is used")

    summary = run_cycle_and_persist(args.strategy, args.outcome)
    print(f"Cycle {summary['cycle_id']} completed:")
    print(f"  Events processed:     {summary['events_processed']}")
    print(f"  Facts in memory:      {summary['knowledge_facts_in_memory']}")
    print(f"  Added to store:       {summary['facts_added_to_store']}")
    print(f"  Updated in store:     {summary['facts_updated_in_store']}")
    print(f"  Store total facts:    {summary['store_total_facts']}")
    print(f"  Store version:        {summary['store_version']}")


if __name__ == "__main__":
    main()
