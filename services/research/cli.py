from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.research.config import ServiceConfig
from services.research.runner import ResearchRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m services.research",
        description="MOEX AI LAB — Research Service",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # ── run ──────────────────────────────────────────────────────────────────
    run_p = subparsers.add_parser("run", help="Execute a full research cycle")
    run_p.add_argument("--dataset", required=True, metavar="ID",
                       help="Dataset ID (directory name under data_dir/datasets/)")
    run_p.add_argument("--data-dir", type=Path, default=Path("data"), metavar="PATH",
                       help="Root directory for datasets (default: data)")
    run_p.add_argument("--max-candidates", type=int, default=5, metavar="N",
                       help="Max hypothesis candidates to generate (default: 5)")
    run_p.add_argument("--pass-threshold", type=float, default=0.80, metavar="F",
                       help="Validation pass threshold 0<f<=1 (default: 0.80)")
    run_p.add_argument("--max-failures", type=int, default=3, metavar="N",
                       help="Max consecutive pipeline failures before abort (default: 3)")
    run_p.add_argument("--output-dir", type=Path, default=Path("."), metavar="PATH",
                       help="Root directory for output artifacts (default: .)")
    run_p.add_argument("--description", default="", metavar="TEXT",
                       help="Human-readable session description")
    run_p.add_argument("--train-size", type=int, default=60, metavar="N",
                       help="WalkForward train window size in bars (default: 60)")
    run_p.add_argument("--test-size", type=int, default=20, metavar="N",
                       help="WalkForward test window size in bars (default: 20)")
    run_p.add_argument("--step-size", type=int, default=20, metavar="N",
                       help="WalkForward step size in bars (default: 20)")

    # ── show ─────────────────────────────────────────────────────────────────
    show_p = subparsers.add_parser("show", help="Display artifacts for a session")
    show_p.add_argument("session_id", metavar="SESSION_ID")
    show_p.add_argument("--output-dir", type=Path, default=Path("."), metavar="PATH")

    # ── list-sessions ─────────────────────────────────────────────────────────
    list_p = subparsers.add_parser("list-sessions", help="List completed sessions")
    list_p.add_argument("--output-dir", type=Path, default=Path("."), metavar="PATH")

    args = parser.parse_args()

    if args.command == "run":
        _cmd_run(args)
    elif args.command == "show":
        _cmd_show(args)
    elif args.command == "list-sessions":
        _cmd_list_sessions(args)


def _cmd_run(args: argparse.Namespace) -> None:
    try:
        config = ServiceConfig(
            dataset_id=args.dataset,
            data_dir=args.data_dir,
            max_candidates=args.max_candidates,
            pass_threshold=args.pass_threshold,
            max_consecutive_failures=args.max_failures,
            output_dir=args.output_dir,
            description=args.description,
            train_size=args.train_size,
            test_size=args.test_size,
            step_size=args.step_size,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        run_result = ResearchRunner().run(config)
        sys.exit(run_result.exit_code)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise


def _cmd_show(args: argparse.Namespace) -> None:
    report_path = args.output_dir / "reports" / args.session_id / "report.json"
    summary_path = args.output_dir / "reports" / args.session_id / "summary.txt"

    if summary_path.exists():
        print(summary_path.read_text(encoding="utf-8"))
    elif report_path.exists():
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)
        print(json.dumps(data["summary"], indent=2))
    else:
        print(f"No artifacts found for session: {args.session_id}", file=sys.stderr)
        sys.exit(1)


def _cmd_list_sessions(args: argparse.Namespace) -> None:
    sessions_dir = args.output_dir / "sessions"
    if not sessions_dir.exists():
        print("No sessions found (sessions/ directory does not exist)")
        return

    sessions = sorted(sessions_dir.iterdir())
    if not sessions:
        print("No sessions found")
        return

    for session_dir in sessions:
        meta_path = session_dir / "session_meta.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            status = meta.get("status", "?")
            duration = meta.get("duration_seconds", 0)
            dataset = meta.get("dataset_id", "?")
            print(f"{session_dir.name}  [{status}]  {dataset}  {duration:.1f}s")
        else:
            print(f"{session_dir.name}  [?]")
