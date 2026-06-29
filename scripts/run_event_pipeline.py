"""M12 Autonomous Pipeline CLI.

Fires ResearchFinished and lets the full chain run automatically:
  ResearchFinished → KnowledgeUpdated → ValidationCompleted
  → AlphaPlannerUpdated → LearningUpdated → DashboardUpdated

Usage:
    python scripts/run_event_pipeline.py
    python scripts/run_event_pipeline.py --strategy BB_SQUEEZE --outcome FAIL
    python scripts/run_event_pipeline.py --report reports/uuid/report.json
    python scripts/run_event_pipeline.py --status
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _status() -> None:
    queue_path = ROOT / "data" / "alpha" / "queue.json"
    runtime_path = ROOT / "runtime" / "status.json"

    print("\n=== Autonomous Pipeline Status ===\n")

    if runtime_path.exists():
        status = json.loads(runtime_path.read_text(encoding="utf-8"))
        last = status.get("pipeline_last_completed", "never")
        print(f"  Last pipeline run:  {last}")
        print(f"  Pipeline completed: {status.get('pipeline_completed', False)}")
    else:
        print("  No runtime/status.json found — pipeline has not run yet")

    print()
    if queue_path.exists():
        doc = json.loads(queue_path.read_text(encoding="utf-8"))
        entries = doc.get("entries", [])
        stats = doc.get("stats", {})
        pending = sum(1 for e in entries if e["status"] == "pending")
        done = sum(1 for e in entries if e["status"] == "done")
        print(f"  Alpha Queue:  {len(entries)} total, {pending} pending, {done} done")
        print(f"  Queue stats:  added={stats.get('total_added', 0)} "
              f"completed={stats.get('total_completed', 0)} "
              f"failed={stats.get('total_failed', 0)}")
        if entries:
            top = next((e for e in entries if e["status"] == "pending"), None)
            if top:
                print(f"  Next target:  {top['strategy_or_instrument']} [{top['priority']}]")
    else:
        print("  Alpha Queue:  not initialized (queue.json not found)")

    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="M12 Autonomous Pipeline")
    parser.add_argument("--strategy", default="UNKNOWN", help="Strategy ID that finished research")
    parser.add_argument("--outcome", default="FAIL", choices=["PASS", "FAIL"], help="Research outcome")
    parser.add_argument("--report", default="", help="Path to completed report.json")
    parser.add_argument("--session", default="", help="Session UUID")
    parser.add_argument("--findings", type=int, default=0, help="Number of findings in report")
    parser.add_argument("--status", action="store_true", help="Show pipeline status and exit")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    if args.status:
        _status()
        return 0

    from services.event_pipeline.pipeline import AutonomousPipeline

    pipeline = AutonomousPipeline(verbose=args.verbose)
    result = pipeline.run(
        strategy_id=args.strategy,
        outcome=args.outcome,
        report_path=args.report,
        session_id=args.session,
        findings_count=args.findings,
    )

    print(f"\n=== Pipeline Result ===")
    print(f"  Events emitted: {result['events_emitted']}")
    print(f"  Stages:         {result['stages']}")
    print(f"  Success:        {result['success']}")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
