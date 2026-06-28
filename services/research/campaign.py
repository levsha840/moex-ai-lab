"""Research Campaign Runner.

Orchestrates a research campaign: runs H-REV-VOL-REG (or any registered
hypothesis) across multiple instruments and periods, applies the Alpha Library
gate, and produces StrategyCandidate objects for hypotheses that pass.

Flow:
  dataset_ids → ResearchRunner → report.json → AlphaLibraryGate → StrategyCandidate

StrategyCandidate lifecycle after this module:
  CANDIDATE_RESEARCH_PASSED  →  (manual risk review)  →  APPROVED_FOR_PAPER
"""
from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.research.alpha_gate import AlphaGateResult, AlphaLibraryGate
from services.research.config import ServiceConfig
from services.research.runner import ResearchRunner, RunResult
from trading.models import StrategyCandidateStatus, StrategyCandidate


# P1 Universe — 14 instruments used in research campaigns
P1_INSTRUMENTS: list[str] = [
    "ALRS", "CHMF", "GAZP", "GMKN", "LKOH", "MAGN",
    "MGNT", "NLMK", "NVTK", "PLZL", "ROSN", "SBER",
    "TATN", "VTBR",
]

P1_PERIODS: list[str] = ["2019", "2021", "2023"]

_TIMEFRAME = "1H"


def p1_dataset_id(ticker: str, period: str, timeframe: str = "1h") -> str:
    """Standard dataset-id naming convention for P1 Universe."""
    return f"{ticker.lower()}_{timeframe}_{period}_main"


# ─────────────────────────────────────────────────────────────────────────────
# Result models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CampaignRunItem:
    """Result of one (instrument × period) run."""

    dataset_id: str
    instrument: str
    period: str
    timeframe: str = _TIMEFRAME
    pass_rate: float | None = None
    windows_total: int = 0
    outcome: str = ""
    alpha_gate: AlphaGateResult | None = None
    candidate: StrategyCandidate | None = None
    error: str = ""

    @property
    def alpha_passed(self) -> bool:
        return self.alpha_gate is not None and self.alpha_gate.passed

    @property
    def errored(self) -> bool:
        return bool(self.error)


@dataclass
class CampaignResult:
    """Aggregated result of a full research campaign."""

    campaign_id: str
    hypothesis_template_id: str
    items: list[CampaignRunItem]
    candidates: list[StrategyCandidate]
    generated_at: str

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def alpha_passed_count(self) -> int:
        return sum(1 for i in self.items if i.alpha_passed)

    @property
    def alpha_failed_count(self) -> int:
        return sum(1 for i in self.items if not i.alpha_passed and not i.errored)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.items if i.errored)


# ─────────────────────────────────────────────────────────────────────────────
# CampaignRunner
# ─────────────────────────────────────────────────────────────────────────────

class CampaignRunner:
    """Runs a hypothesis across multiple datasets and promotes passing results.

    Usage:
        runner = CampaignRunner(
            hypothesis_template_id="tmpl_h_rev_vol_reg",
            data_dir=Path("data"),
            output_dir=Path("campaigns/h_rev_vol_reg_2026"),
        )
        result = runner.run(P1_INSTRUMENTS, P1_PERIODS)
    """

    def __init__(
        self,
        hypothesis_template_id: str,
        data_dir: Path,
        output_dir: Path,
        alpha_gate: AlphaLibraryGate | None = None,
        max_candidates: int = 1,
        pass_threshold: float = 0.80,
        train_size: int = 60,
        test_size: int = 20,
        step_size: int = 20,
        verbose: bool = True,
    ) -> None:
        self._hypothesis_template_id = hypothesis_template_id
        self._data_dir = Path(data_dir)
        self._output_dir = Path(output_dir)
        self._alpha_gate = alpha_gate or AlphaLibraryGate()
        self._max_candidates = max_candidates
        self._pass_threshold = pass_threshold
        self._train_size = train_size
        self._test_size = test_size
        self._step_size = step_size
        self._verbose = verbose
        self._runner = ResearchRunner()

    def run(
        self,
        instruments: list[str],
        periods: list[str],
        timeframe: str = "1h",
        max_runs: int | None = None,
    ) -> CampaignResult:
        """Run the campaign.

        Args:
            instruments: Ticker list.
            periods: Year-period list.
            timeframe: Candle timeframe string (default "1h").
            max_runs: Optional hard cap on successful (non-error) runs to
                      support session-level research budget management.
        """
        campaign_id = uuid4().hex[:12]
        generated_at = datetime.now(timezone.utc).isoformat()
        items: list[CampaignRunItem] = []

        total = len(instruments) * len(periods)
        cap = min(total, max_runs) if max_runs is not None else total
        if self._verbose:
            print(f"\n{'='*60}")
            print(f"Campaign {campaign_id}")
            print(f"Hypothesis: {self._hypothesis_template_id}")
            print(f"Runs: up to {cap}/{total} ({len(instruments)} instr x {len(periods)} periods)")
            print(f"Alpha gate: pass_rate >= {self._alpha_gate.min_pass_rate:.2f}")
            print(f"{'='*60}\n")

        idx = 0
        successful = 0
        for period in periods:
            for ticker in instruments:
                if max_runs is not None and successful >= max_runs:
                    break
                idx += 1
                dataset_id = p1_dataset_id(ticker, period, timeframe)
                item = self._run_one(dataset_id, ticker, period, timeframe, idx, cap)
                items.append(item)
                if not item.errored:
                    successful += 1

        candidates = [i.candidate for i in items if i.candidate is not None]

        result = CampaignResult(
            campaign_id=campaign_id,
            hypothesis_template_id=self._hypothesis_template_id,
            items=items,
            candidates=candidates,
            generated_at=generated_at,
        )

        if self._verbose:
            self._print_summary(result)

        self._save_campaign_report(result)
        return result

    def _run_one(
        self,
        dataset_id: str,
        ticker: str,
        period: str,
        timeframe: str,
        idx: int,
        total: int,
    ) -> CampaignRunItem:
        item = CampaignRunItem(
            dataset_id=dataset_id,
            instrument=ticker,
            period=period,
            timeframe=timeframe.upper(),
        )
        run_output_dir = self._output_dir / "runs" / dataset_id

        if self._verbose:
            print(f"[{idx:02d}/{total}] {dataset_id} ...", end=" ", flush=True)

        try:
            config = ServiceConfig(
                dataset_id=dataset_id,
                data_dir=self._data_dir,
                output_dir=run_output_dir,
                max_candidates=self._max_candidates,
                pass_threshold=self._pass_threshold,
                max_consecutive_failures=3,
                train_size=self._train_size,
                test_size=self._test_size,
                step_size=self._step_size,
                description=f"Campaign {self._hypothesis_template_id} — {dataset_id}",
                hypothesis_template_id=self._hypothesis_template_id,
            )
            run_result = self._runner.run(config)
            pass_rate, windows_total, outcome = self._extract_finding(run_result)

            item.pass_rate = pass_rate
            item.windows_total = windows_total
            item.outcome = outcome

            gate = self._alpha_gate.check(pass_rate, windows_total)
            item.alpha_gate = gate

            if gate.passed:
                item.candidate = self._make_candidate(item, run_result)

            if self._verbose:
                mark = "ALPHA_PASS" if gate.passed else f"alpha_fail ({gate.reason[:40]})"
                pr = f"{pass_rate:.3f}" if pass_rate is not None else "n/a"
                print(f"pass_rate={pr} windows={windows_total} -> {mark}")

        except FileNotFoundError as exc:
            item.error = f"dataset not found: {exc}"
            if self._verbose:
                print(f"SKIP — {item.error}")
        except Exception as exc:
            item.error = f"{type(exc).__name__}: {exc}"
            if self._verbose:
                print(f"ERROR — {item.error}")
                traceback.print_exc()

        return item

    def _extract_finding(
        self, run_result: RunResult
    ) -> tuple[float | None, int, str]:
        """Extract pass_rate, windows_total, outcome from report.json."""
        with open(run_result.report_path, encoding="utf-8") as f:
            data = json.load(f)
        findings = data.get("findings", [])
        if not findings:
            return None, 0, "NO_FINDINGS"
        # One finding per session (one hypothesis template)
        f = findings[0]
        return f.get("pass_rate"), f.get("windows_total", 0), f.get("outcome", "UNKNOWN")

    def _make_candidate(
        self,
        item: CampaignRunItem,
        run_result: RunResult,
    ) -> StrategyCandidate:
        assert item.pass_rate is not None
        confidence = min(item.pass_rate / self._pass_threshold, 1.0)
        return StrategyCandidate(
            candidate_id=f"cand_{item.instrument.lower()}_{item.period}_{uuid4().hex[:8]}",
            hypothesis_id=self._hypothesis_template_id,
            instrument=item.instrument,
            period=item.period,
            timeframe=item.timeframe,
            pass_rate=item.pass_rate,
            confidence=round(confidence, 4),
            regime_label="RANGING",
            source_ref=item.dataset_id,
            status=StrategyCandidateStatus.CANDIDATE_RESEARCH_PASSED,
            created_at=datetime.now(timezone.utc).isoformat(),
            features={
                "template_id": self._hypothesis_template_id,
                "windows_total": item.windows_total,
                "alpha_gate_reason": item.alpha_gate.reason if item.alpha_gate else "",
                "run_session_id": str(run_result.session_id),
            },
        )

    def _save_campaign_report(self, result: CampaignResult) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self._output_dir / "campaign_report.json"

        def _item_dict(item: CampaignRunItem) -> dict:
            return {
                "dataset_id": item.dataset_id,
                "instrument": item.instrument,
                "period": item.period,
                "timeframe": item.timeframe,
                "pass_rate": item.pass_rate,
                "windows_total": item.windows_total,
                "outcome": item.outcome,
                "alpha_gate_passed": item.alpha_passed,
                "alpha_gate_reason": item.alpha_gate.reason if item.alpha_gate else "",
                "candidate_id": item.candidate.candidate_id if item.candidate else None,
                "error": item.error,
            }

        def _cand_dict(c: StrategyCandidate) -> dict:
            return {
                "candidate_id": c.candidate_id,
                "hypothesis_id": c.hypothesis_id,
                "instrument": c.instrument,
                "period": c.period,
                "timeframe": c.timeframe,
                "pass_rate": c.pass_rate,
                "confidence": c.confidence,
                "regime_label": c.regime_label,
                "source_ref": c.source_ref,
                "status": c.status.value,
                "created_at": c.created_at,
                "features": c.features,
            }

        report = {
            "campaign_id": result.campaign_id,
            "hypothesis_template_id": result.hypothesis_template_id,
            "generated_at": result.generated_at,
            "summary": {
                "total": result.total,
                "alpha_passed": result.alpha_passed_count,
                "alpha_failed": result.alpha_failed_count,
                "errored": result.error_count,
                "candidates_created": len(result.candidates),
            },
            "runs": [_item_dict(i) for i in result.items],
            "candidates": [_cand_dict(c) for c in result.candidates],
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def _print_summary(self, result: CampaignResult) -> None:
        print(f"\n{'='*60}")
        print(f"Campaign {result.campaign_id} complete")
        print(f"  Total runs:       {result.total}")
        print(f"  Alpha PASS:       {result.alpha_passed_count}")
        print(f"  Alpha FAIL:       {result.alpha_failed_count}")
        print(f"  Errors/Skips:     {result.error_count}")
        print(f"  Candidates:       {len(result.candidates)}")
        if result.candidates:
            print(f"\n  StrategyCandidate list (status=CANDIDATE_RESEARCH_PASSED):")
            for c in result.candidates:
                print(
                    f"    {c.candidate_id}  {c.instrument}/{c.period}  "
                    f"pass_rate={c.pass_rate:.3f}  conf={c.confidence:.3f}"
                )
        else:
            print(f"\n  No candidates produced.")
            print(f"  Reason: pass_rate < {self._alpha_gate.min_pass_rate:.2f} "
                  f"across all {result.total} runs.")
        print(f"{'='*60}\n")
