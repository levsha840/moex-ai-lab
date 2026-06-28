"""MOEX AI LAB — Unified Operational Runner.

Usage:
    python scripts/run_lab.py --mode operational
    python scripts/run_lab.py --mode operational --budget 100 --verbose
    python scripts/run_lab.py --mode operational --dry-run     # plan only, no runs

Safety constraints enforced at startup:
  - MOEX_ENABLE_LIVE_TRADING must be unset or false
  - T_INVEST_EXECUTE must be unset or false
  - No token logging in DEBUG mode
  - max_research_runs per session (default 100)
  - max_paper_orders per session (default 0 — paper trading gated on APPROVED_FOR_PAPER)

PROHIBITED in this runner:
  - git commit / git push
  - File deletion
  - Code changes
  - Research Service code changes
  - Real broker API calls (T-Invest or any live exchange)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Ensure project root is in sys.path when run as a script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.research.campaign import CampaignRunner, CampaignResult, P1_INSTRUMENTS, P1_PERIODS
from services.research.hypothesis_registry import HypothesisTemplateRegistry
from services.research.safety import SafetyConfig, SafetyGuard, SafetyViolation
from trading.models import StrategyCandidate, StrategyCandidateStatus


# ─────────────────────────────────────────────────────────────────────────────
# Operational Report
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OperationalReport:
    session_id: str
    mode: str
    hypotheses_registered: int
    hypotheses_tested: int
    hypotheses_skipped: int
    research_runs_completed: int
    research_runs_budget: int
    research_runs_errored: int
    candidates_created: int
    candidates_approved_for_paper: int
    paper_trades: int
    paper_pnl: float
    errors: list[str]
    campaign_summaries: list[dict]
    next_action: str
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "hypothesis_registry": {
                "total": self.hypotheses_registered,
                "tested": self.hypotheses_tested,
                "skipped": self.hypotheses_skipped,
            },
            "research_phase": {
                "budget": self.research_runs_budget,
                "completed": self.research_runs_completed,
                "errored": self.research_runs_errored,
            },
            "candidates": {
                "created": self.candidates_created,
                "approved_for_paper": self.candidates_approved_for_paper,
            },
            "paper_trading": {
                "trades": self.paper_trades,
                "pnl": self.paper_pnl,
            },
            "errors": self.errors,
            "campaigns": self.campaign_summaries,
            "next_action": self.next_action,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Archived Hypotheses Store
# ─────────────────────────────────────────────────────────────────────────────

def _load_archived(data_dir: Path) -> set[str]:
    """Load template_ids of archived/disabled hypotheses."""
    path = data_dir / "archived_hypotheses.json"
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _load_approved_candidates(data_dir: Path) -> list[StrategyCandidate]:
    """Load StrategyCandidate objects with APPROVED_FOR_PAPER status."""
    cand_dir = data_dir / "candidates"
    if not cand_dir.exists():
        return []
    approved = []
    for path in sorted(cand_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            status = StrategyCandidateStatus(data.get("status", ""))
            if status == StrategyCandidateStatus.APPROVED_FOR_PAPER:
                approved.append(StrategyCandidate(**{
                    k: v for k, v in data.items()
                    if k in StrategyCandidate.__dataclass_fields__
                }))
        except Exception:
            continue
    return approved


# ─────────────────────────────────────────────────────────────────────────────
# Lab Runner
# ─────────────────────────────────────────────────────────────────────────────

class LabRunner:
    """Executes an Operational Research + Paper Trading session.

    Session lifecycle:
      1. Safety pre-flight checks (hard-blocked on violations)
      2. Load Hypothesis Registry (10 templates)
      3. For each non-archived hypothesis (budget permitting):
         a. Run CampaignRunner across P1 Universe
         b. Apply AlphaLibraryGate (pass_rate >= 0.40)
         c. Collect StrategyCandidate (CANDIDATE_RESEARCH_PASSED)
      4. Paper Trading phase:
         a. Load APPROVED_FOR_PAPER candidates from disk
         b. (None expected on first run — requires manual risk review)
      5. Generate Operational Report
    """

    def __init__(
        self,
        budget: int = 100,
        instruments: list[str] | None = None,
        periods: list[str] | None = None,
        timeframe: str = "1h",
        data_dir: Path | None = None,
        output_dir: Path | None = None,
        verbose: bool = True,
        dry_run: bool = False,
    ) -> None:
        self._budget = budget
        self._instruments = instruments or P1_INSTRUMENTS
        self._periods = periods or P1_PERIODS
        self._timeframe = timeframe
        self._data_dir = Path(data_dir) if data_dir else Path("data")
        self._output_dir = Path(output_dir) if output_dir else Path("operational_reports")
        self._verbose = verbose
        self._dry_run = dry_run
        self._session_id = uuid4().hex[:12]
        self._guard = SafetyGuard(SafetyConfig(
            max_research_runs=budget,
            max_paper_orders=0,
            real_trading_blocked=True,
            sandbox_execute_disabled=True,
        ))

    def run(self) -> OperationalReport:
        if self._verbose:
            self._banner()

        # ── Safety pre-flight ──────────────────────────────────────────────
        self._guard.check_all()
        if self._verbose:
            self._log("[SAFETY] All pre-flight checks passed.")

        # ── Load registry ──────────────────────────────────────────────────
        registry = HypothesisTemplateRegistry()
        all_templates = registry.list()
        archived = _load_archived(self._data_dir)
        if self._verbose:
            self._log(f"[REGISTRY] {len(all_templates)} hypotheses loaded, "
                      f"{len(archived)} archived.")

        # ── Research Phase ─────────────────────────────────────────────────
        all_candidates: list[StrategyCandidate] = []
        all_errors: list[str] = []
        campaign_summaries: list[dict] = []
        hypotheses_tested = 0
        hypotheses_skipped = 0
        runs_completed = 0
        runs_errored = 0

        for template in all_templates:
            if self._guard.budget_exhausted():
                if self._verbose:
                    self._log(f"[BUDGET] Research budget exhausted ({self._budget} runs). "
                              "Stopping research phase.")
                break

            if template.template_id in archived:
                if self._verbose:
                    self._log(f"[SKIP] {template.template_id} is archived.")
                hypotheses_skipped += 1
                continue

            remaining = self._guard.budget_remaining()
            if self._verbose:
                self._log(
                    f"[CAMPAIGN] {template.template_id}  "
                    f"budget_remaining={remaining}"
                )

            if self._dry_run:
                if self._verbose:
                    self._log(f"[DRY-RUN] Skipping actual run for {template.template_id}.")
                hypotheses_skipped += 1
                continue

            campaign_dir = self._output_dir / "campaigns" / template.template_id
            try:
                runner = CampaignRunner(
                    hypothesis_template_id=template.template_id,
                    data_dir=self._data_dir,
                    output_dir=campaign_dir,
                    pass_threshold=0.80,
                    max_candidates=3,
                    train_size=60,
                    test_size=20,
                    step_size=20,
                    verbose=self._verbose,
                )
                result: CampaignResult = runner.run(
                    self._instruments,
                    self._periods,
                    timeframe=self._timeframe,
                    max_runs=remaining,
                )
                runs_this = result.total - result.error_count
                runs_completed += runs_this
                runs_errored += result.error_count
                hypotheses_tested += 1
                self._guard.record_research_run(runs_this)
                all_candidates.extend(result.candidates)

                for item in result.items:
                    if item.error:
                        all_errors.append(
                            f"{template.template_id}/{item.dataset_id}: {item.error}"
                        )

                campaign_summaries.append({
                    "template_id": template.template_id,
                    "name": template.name,
                    "runs": result.total,
                    "alpha_passed": result.alpha_passed_count,
                    "alpha_failed": result.alpha_failed_count,
                    "errored": result.error_count,
                    "candidates": len(result.candidates),
                })

            except SafetyViolation:
                raise
            except Exception as exc:
                msg = f"{template.template_id}: {type(exc).__name__}: {exc}"
                all_errors.append(msg)
                if self._verbose:
                    self._log(f"[ERROR] {msg}")

        # ── Paper Trading Phase ────────────────────────────────────────────
        approved = _load_approved_candidates(self._data_dir)
        paper_trades = 0
        paper_pnl = 0.0

        if self._verbose:
            self._log(
                f"\n[PAPER] Checking APPROVED_FOR_PAPER candidates in {self._data_dir}/candidates/"
            )
            self._log(f"[PAPER] Found: {len(approved)} approved candidates.")

        if approved:
            if self._verbose:
                self._log("[PAPER] Approved candidates exist but paper execution "
                          "is deferred (requires live or latest-period data).")
        else:
            if self._verbose:
                self._log("[PAPER] No APPROVED_FOR_PAPER candidates yet. "
                          "Promote candidates via manual risk review to enable paper trading.")

        # ── Determine next action ──────────────────────────────────────────
        next_action = self._compute_next_action(
            all_candidates, hypotheses_tested, runs_completed, all_errors
        )

        # ── Build and save report ──────────────────────────────────────────
        report = OperationalReport(
            session_id=self._session_id,
            mode="dry_run" if self._dry_run else "operational",
            hypotheses_registered=len(all_templates),
            hypotheses_tested=hypotheses_tested,
            hypotheses_skipped=hypotheses_skipped,
            research_runs_completed=runs_completed,
            research_runs_budget=self._budget,
            research_runs_errored=runs_errored,
            candidates_created=len(all_candidates),
            candidates_approved_for_paper=len(approved),
            paper_trades=paper_trades,
            paper_pnl=paper_pnl,
            errors=all_errors,
            campaign_summaries=campaign_summaries,
            next_action=next_action,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._save_report(report)
        if self._verbose:
            self._print_report(report)

        return report

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _compute_next_action(
        self,
        candidates: list[StrategyCandidate],
        tested: int,
        runs: int,
        errors: list[str],
    ) -> str:
        if runs == 0 and not self._dry_run:
            return ("LOAD_DATA: No datasets found. Run MarketAgent to download "
                    "P1 Universe data (14 tickers × 3 periods × 1H).")
        if candidates:
            return (
                f"RISK_REVIEW: {len(candidates)} candidates with CANDIDATE_RESEARCH_PASSED status. "
                "Perform manual risk review and promote to APPROVED_FOR_PAPER via "
                f"`data/candidates/<id>.json` status field. "
                "Paper trading will activate on next operational run."
            )
        if tested > 0 and not candidates:
            return (
                "TUNE_HYPOTHESES: All hypotheses tested, 0 candidates passed Alpha Gate "
                "(pass_rate threshold 0.40). Options: "
                "(1) Loosen hypothesis parameters in YAML, "
                "(2) Add new hypotheses to hypotheses/ directory, "
                "(3) Try different timeframes or instruments."
            )
        if errors:
            return (
                f"FIX_ERRORS: {len(errors)} errors during research. "
                "Check operational report for details."
            )
        return "RUN_COMPLETE: No immediate action required. Schedule next run in 24h."

    def _save_report(self, report: OperationalReport) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"session_{report.session_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        if self._verbose:
            self._log(f"\n[REPORT] Saved to {path}")

    def _banner(self) -> None:
        print("\n" + "=" * 65)
        print("  MOEX AI LAB - Operational Research + Paper Trading Mode")
        print(f"  Session: {self._session_id}")
        print(f"  Budget:  {self._budget} research runs")
        print(f"  Dry-run: {self._dry_run}")
        print("=" * 65)

    def _log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    def _print_report(self, r: OperationalReport) -> None:
        print("\n" + "=" * 65)
        print("  OPERATIONAL REPORT")
        print("=" * 65)
        print(f"  Session ID       : {r.session_id}")
        print(f"  Mode             : {r.mode}")
        print(f"  Generated        : {r.generated_at}")
        print()
        print("  HYPOTHESIS REGISTRY")
        print(f"    Registered     : {r.hypotheses_registered}")
        print(f"    Tested         : {r.hypotheses_tested}")
        print(f"    Skipped/Arch.  : {r.hypotheses_skipped}")
        print()
        print("  RESEARCH PHASE")
        print(f"    Budget         : {r.research_runs_budget}")
        print(f"    Completed      : {r.research_runs_completed}")
        print(f"    Errored        : {r.research_runs_errored}")
        print()
        print("  CANDIDATES")
        print(f"    Created        : {r.candidates_created}  (status=CANDIDATE_RESEARCH_PASSED)")
        print(f"    Approved/Paper : {r.candidates_approved_for_paper}  (status=APPROVED_FOR_PAPER)")
        print()
        print("  PAPER TRADING")
        print(f"    Trades         : {r.paper_trades}")
        print(f"    PnL            : {r.paper_pnl:.2f}")
        print()
        if r.campaign_summaries:
            print("  CAMPAIGN RESULTS")
            header = f"  {'Hypothesis':<35} {'Runs':>4} {'Pass':>4} {'Fail':>4} {'Err':>4} {'Cand':>4}"
            print(header)
            print("  " + "-" * 63)
            for s in r.campaign_summaries:
                tid = s["template_id"].replace("tmpl_", "")[:35]
                print(
                    f"  {tid:<35} {s['runs']:>4} {s['alpha_passed']:>4} "
                    f"{s['alpha_failed']:>4} {s['errored']:>4} {s['candidates']:>4}"
                )
            print()
        if r.errors:
            print(f"  ERRORS ({len(r.errors)})")
            for i, e in enumerate(r.errors[:5], 1):
                print(f"    [{i}] {e[:80]}")
            if len(r.errors) > 5:
                print(f"    ... and {len(r.errors) - 5} more (see report JSON)")
            print()
        print(f"  NEXT ACTION: {r.next_action}")
        print("=" * 65 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MOEX AI LAB — Operational Research + Paper Trading Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--mode", choices=["operational"], default="operational",
        help="Run mode (only 'operational' supported).",
    )
    p.add_argument(
        "--budget", type=int, default=100, metavar="N",
        help="Max research runs for this session (default 100).",
    )
    p.add_argument(
        "--data-dir", default="data", metavar="PATH",
        help="Directory containing OHLCV datasets (default: data/).",
    )
    p.add_argument(
        "--output-dir", default="operational_reports", metavar="PATH",
        help="Directory for session reports (default: operational_reports/).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Plan-only mode: list hypotheses and budget without running research.",
    )
    p.add_argument(
        "--verbose", action="store_true", default=True,
        help="Verbose output (default: True).",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Suppress verbose output.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    verbose = args.verbose and not args.quiet

    runner = LabRunner(
        budget=args.budget,
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
        verbose=verbose,
        dry_run=args.dry_run,
    )

    try:
        runner.run()
    except SafetyViolation as exc:
        print(f"\n[SAFETY VIOLATION] {exc}", file=sys.stderr)
        print("Operational run aborted. Fix safety constraint and retry.", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Operational run interrupted by user.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
