#!/usr/bin/env python3
"""M12 Sprint 2 — Autonomous Runtime CLI.

Usage:
  python scripts/run_autonomous_runtime.py --dry-run
  python scripts/run_autonomous_runtime.py --dry-run --cycles 3
  python scripts/run_autonomous_runtime.py --live --run-once
  python scripts/run_autonomous_runtime.py --status
  python scripts/run_autonomous_runtime.py --journal --tail 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.runtime.orchestrator import RuntimeOrchestrator
from services.runtime.health import LabHealthCheck
from services.alpha_discovery.persistent_queue import PersistentAlphaQueue


def cmd_status(args) -> None:
    orch = RuntimeOrchestrator(project_root=ROOT, dry_run=True)
    print(json.dumps(orch.status(), indent=2, ensure_ascii=False))


def cmd_journal(args) -> None:
    from services.runtime.journal import RuntimeJournal
    journal_path = ROOT / "runtime" / "orchestrator_journal.jsonl"
    journal = RuntimeJournal(journal_path)
    entries = journal.tail(args.tail)
    if not entries:
        print("Journal is empty.")
        return
    for entry in entries:
        ts   = entry.get("ts", "")[:19]
        evt  = entry.get("event", "")
        why  = entry.get("reason", "")
        print(f"[{ts}] {evt:<28} {why}")
    print(f"\n({len(entries)} entries shown, total={journal.count()})")


def cmd_health(args) -> None:
    queue = PersistentAlphaQueue(ROOT / "data" / "alpha" / "queue.json")
    queue.load()
    checker = LabHealthCheck(ROOT)
    reports = checker.check_all(queue, ROOT / "runtime" / "orchestrator_state.json")
    for name, r in reports.items():
        icon = {"OK": "✓", "WARNING": "!", "CRITICAL": "✗"}.get(r.status, "?")
        print(f"  {icon} {r.name:<22} {r.status:<10} {r.message}")
    healthy = checker.is_healthy(reports)
    print(f"\nOverall: {'HEALTHY' if healthy else 'UNHEALTHY'}")


def cmd_run(args) -> None:
    dry_run = not args.live

    if dry_run:
        print("[dry-run mode] Orchestrator will simulate pipeline, no queue mutations.")
    else:
        print("[LIVE mode] Orchestrator will execute real AutonomousPipeline.")

    orch = RuntimeOrchestrator(
        project_root=ROOT,
        dry_run=dry_run,
        max_error_count=3,
        lease_minutes=30,
    )

    if args.run_once or args.cycles == 1:
        result = orch.run_once()
        _print_result(result)
    else:
        max_cycles = args.cycles if args.cycles > 0 else None
        results = orch.run_continuous(max_cycles=max_cycles)
        for r in results:
            _print_result(r)
        print(f"\nCompleted {len(results)} cycle(s).")


def _print_result(r) -> None:
    status = "SKIP" if r.no_task else ("OK" if r.final_state == "IDLE" else "ERR")
    dur    = f"{r.duration_s:.2f}s"
    strat  = r.strategy_id or "(none)"
    print(f"  [{status}] {r.cycle_id} strategy={strat} duration={dur} dry={r.dry_run}")
    if r.error:
        print(f"         ERROR: {r.error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MOEX AI Lab — Autonomous Runtime")
    sub = parser.add_subparsers(dest="cmd")

    # --status
    p_status = sub.add_parser("status", help="Show orchestrator status")
    p_status.set_defaults(func=cmd_status)

    # --journal
    p_journal = sub.add_parser("journal", help="Show recent journal entries")
    p_journal.add_argument("--tail", type=int, default=20)
    p_journal.set_defaults(func=cmd_journal)

    # --health
    p_health = sub.add_parser("health", help="Run health checks")
    p_health.set_defaults(func=cmd_health)

    # run (default command)
    p_run = sub.add_parser("run", help="Execute orchestrator cycle(s)")
    p_run.add_argument("--dry-run", dest="dry_run", action="store_true",
                       help="Simulate pipeline (default)")
    p_run.add_argument("--live", action="store_true",
                       help="Run real AutonomousPipeline")
    p_run.add_argument("--run-once", action="store_true",
                       help="Execute exactly one cycle")
    p_run.add_argument("--cycles", type=int, default=1,
                       help="Number of cycles (0 = continuous)")
    p_run.set_defaults(func=cmd_run)

    # Convenience top-level flags (shortcut: no subcommand needed)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--journal", action="store_true")
    parser.add_argument("--tail", type=int, default=20)
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-once", dest="run_once", action="store_true")
    parser.add_argument("--cycles", type=int, default=1)

    args = parser.parse_args()

    if args.cmd:
        args.func(args)
    elif args.status:
        cmd_status(args)
    elif args.journal:
        cmd_journal(args)
    elif args.health:
        cmd_health(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
