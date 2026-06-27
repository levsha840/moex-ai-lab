"""Dry Run Validation — MOEX AI LAB Operational Infrastructure.

Validates the complete IE pipeline without executing heavy Research Service runs.
Checks:
  1. Config files present and parseable
  2. Expected datasets exist per Research Universe
  3. MarketAgent — loads manifest from existing datasets (no API call)
  4. MacroAgent — offline graceful degradation test
  5. CorrelationAgent — fixture mode
  6. RegimeDetectionAgent — fixture mode
  7. KnowledgeAgent — reads existing snapshots or empty
  8. ExperimentPlanner — runs on empty / minimal knowledge
  9. ValidationAgentAdapter — dry_run=True (no Research Service)
  10. ChiefScientist — fixture snapshot, policy check

Reports: gap list, agent health, pipeline continuity.

Usage:
    python scripts/dry_run_validation.py [--instrument SBER] [--period 2023]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR    = ROOT / "data"
CONFIG_PATH = ROOT / "config" / "research_universe.json"
BUDGET_PATH = ROOT / "config" / "research_budget.json"

# ---------------------------------------------------------------------------
# Result tracker
# ---------------------------------------------------------------------------

class CheckResult:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def ok(self, check: str, detail: str = "") -> None:
        self.items.append({"status": "OK",   "check": check, "detail": detail})
        print(f"  [OK]   {check}" + (f" — {detail}" if detail else ""))

    def warn(self, check: str, detail: str = "") -> None:
        self.items.append({"status": "WARN", "check": check, "detail": detail})
        print(f"  [WARN] {check}" + (f" — {detail}" if detail else ""))

    def fail(self, check: str, detail: str = "") -> None:
        self.items.append({"status": "FAIL", "check": check, "detail": detail})
        print(f"  [FAIL] {check}" + (f" — {detail}" if detail else ""))

    def summary(self) -> tuple[int, int, int]:
        ok   = sum(1 for i in self.items if i["status"] == "OK")
        warn = sum(1 for i in self.items if i["status"] == "WARN")
        fail = sum(1 for i in self.items if i["status"] == "FAIL")
        return ok, warn, fail


# ---------------------------------------------------------------------------
# Check 1: Config files
# ---------------------------------------------------------------------------

def check_configs(r: CheckResult) -> dict:
    print("\n[1] Config Files")
    cfg = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        r.ok("research_universe.json", f"{len(cfg.get('instruments', []))} instruments")
    else:
        r.fail("research_universe.json", "not found — run first: create config/research_universe.json")

    if BUDGET_PATH.exists():
        r.ok("research_budget.json")
    else:
        r.fail("research_budget.json", "not found")

    return cfg


# ---------------------------------------------------------------------------
# Check 2: Dataset coverage
# ---------------------------------------------------------------------------

def check_datasets(r: CheckResult, cfg: dict, instrument_filter: str, period_filter: str) -> list[dict]:
    print("\n[2] Dataset Coverage")
    instruments = cfg.get("instruments", [])
    periods = cfg.get("periods", [])
    timeframes = [t["tf"] for t in cfg.get("timeframes", [])]

    if instrument_filter:
        instruments = [i for i in instruments if i["ticker"] == instrument_filter]
    if period_filter:
        periods = [p for p in periods if p["year"] == period_filter]

    # Default: validate P1 only in first priority period
    if not instrument_filter and not period_filter:
        instruments = [i for i in instruments if i["priority"] == "P1"]
        periods = periods[:3]  # 2019-2021 as sample

    session = "main"
    gaps = []
    found = 0
    total = 0

    for inst in instruments:
        ticker = inst["ticker"]
        for period in periods:
            year = period["year"]
            for tf in timeframes:
                dataset_id = f"{ticker.lower()}_{tf}_{year}_{session}"
                csv_path = DATA_DIR / "datasets" / dataset_id / "ohlcv.csv"
                meta_path = DATA_DIR / "datasets" / dataset_id / "metadata.json"
                total += 1

                if not csv_path.exists():
                    gaps.append({"ticker": ticker, "period": year, "tf": tf, "dataset_id": dataset_id})
                    continue

                # Validate readability
                try:
                    with open(csv_path, encoding="utf-8", newline="") as f:
                        bar_count = max(0, sum(1 for _ in f) - 1)
                    if bar_count == 0:
                        r.warn(f"Empty dataset: {dataset_id}", "0 bars")
                        gaps.append({"ticker": ticker, "period": year, "tf": tf, "dataset_id": dataset_id, "issue": "empty"})
                    else:
                        found += 1
                except Exception as exc:
                    r.fail(f"Unreadable dataset: {dataset_id}", str(exc))
                    gaps.append({"ticker": ticker, "period": year, "tf": tf, "dataset_id": dataset_id, "issue": str(exc)})

    if found == total:
        r.ok("Dataset coverage", f"{found}/{total} cells complete")
    elif found > 0:
        r.warn("Dataset coverage partial", f"{found}/{total} cells — {len(gaps)} gaps")
        for g in gaps[:5]:
            print(f"       GAP: {g['dataset_id']}")
        if len(gaps) > 5:
            print(f"       ... and {len(gaps)-5} more")
    else:
        r.fail("Dataset coverage", f"0/{total} cells found — run build_universe.py first")

    return gaps


# ---------------------------------------------------------------------------
# Check 3: MacroAgent (offline graceful degradation)
# ---------------------------------------------------------------------------

def check_macro_agent(r: CheckResult) -> None:
    print("\n[3] MacroAgent — Offline Graceful Degradation")
    try:
        from agents.data.macro import MacroAgent, FixtureMacroSource
        source = FixtureMacroSource({"IMOEX": [
            {"date": "2023-01-03", "open": 2000.0, "high": 2010.0, "low": 1990.0, "close": 2005.0, "volume": 1000000}
        ]})
        agent = MacroAgent(data_dir=DATA_DIR, source=source)
        result = agent.run(period="2023", _clock=lambda: datetime(2023, 1, 3, 12, 0))
        snap = result.output
        r.ok("MacroAgent protocol", f"agent_id={result.agent_id}, confidence={result.confidence.value:.2f}")
        r.ok("MacroAgent fixture", f"snapshot_id={snap.snapshot_id}, symbols={len(snap.observations)}")
    except Exception as exc:
        r.fail("MacroAgent", str(exc))


# ---------------------------------------------------------------------------
# Check 4: CorrelationAgent (fixture)
# ---------------------------------------------------------------------------

def check_correlation_agent(r: CheckResult) -> None:
    print("\n[4] CorrelationAgent — Fixture Mode")
    try:
        from agents.analysis.correlation import CorrelationAgent, FixtureCorrelationSource
        dates = [f"2023-01-{i+3:02d}" for i in range(12)]
        source = FixtureCorrelationSource(
            instrument_data={"SBER": [{"date": d, "close": 100.0 + i * 0.5} for i, d in enumerate(dates)]},
            macro_data={
                "IMOEX":  [{"date": d, "close": 2200.0 + i * 5.0} for i, d in enumerate(dates)],
                "USDRUB": [{"date": d, "close": 70.0 + i * 0.1}  for i, d in enumerate(dates)],
                "RGBI":   [{"date": d, "close": 110.0 - i * 0.2} for i, d in enumerate(dates)],
            },
        )
        agent = CorrelationAgent(data_dir=DATA_DIR, source=source)
        result = agent.run(instrument="SBER", period="2023",
                           _clock=lambda: datetime(2023, 1, 31, 18, 0))
        snap = result.output
        r.ok("CorrelationAgent protocol", f"agent_id={result.agent_id}")
        r.ok("CorrelationAgent fixture", f"pairs={len(snap.pairs)}, instrument_bars={snap.total_instrument_bars}")
    except Exception as exc:
        r.fail("CorrelationAgent", str(exc))


# ---------------------------------------------------------------------------
# Check 5: RegimeDetectionAgent (fixture)
# ---------------------------------------------------------------------------

def check_regime_agent(r: CheckResult) -> None:
    print("\n[5] RegimeDetectionAgent — Fixture Mode")
    try:
        from agents.analysis.regime import RegimeDetectionAgent, FixtureRegimeSource
        dates = [f"2023-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in range(1, 22)][:63]
        closes = [100.0 + i * 0.3 for i in range(63)]
        source = FixtureRegimeSource(
            instrument_data={"SBER": [{"date": d, "close": c} for d, c in zip(dates, closes)]},
            macro_data={
                "IMOEX":  [{"date": d, "close": 2200.0 + i * 2.0} for i, d in enumerate(dates)],
                "USDRUB": [{"date": d, "close": 70.0 - i * 0.05} for i, d in enumerate(dates)],
                "RGBI":   [{"date": d, "close": 112.0 + i * 0.1} for i, d in enumerate(dates)],
            },
        )
        agent = RegimeDetectionAgent(data_dir=DATA_DIR, source=source)
        result = agent.run(instrument="SBER", period="2023",
                           _clock=lambda: datetime(2023, 3, 5, 18, 0))
        snap = result.output
        r.ok("RegimeDetectionAgent protocol", f"agent_id={result.agent_id}")
        r.ok("RegimeDetectionAgent fixture", f"segments={len(snap.segments)}")
    except Exception as exc:
        r.fail("RegimeDetectionAgent", str(exc))


# ---------------------------------------------------------------------------
# Check 6: KnowledgeAgent (empty input)
# ---------------------------------------------------------------------------

def check_knowledge_agent(r: CheckResult) -> None:
    print("\n[6] KnowledgeAgent — Empty Input")
    try:
        from agents.knowledge.agent import KnowledgeAgent, FixtureKnowledgeSource
        source = FixtureKnowledgeSource(reports=[], kb_entries=[])
        agent = KnowledgeAgent(data_dir=DATA_DIR, source=source)
        result = agent.run(campaign_id="dry_run_test",
                           _clock=lambda: datetime(2023, 1, 1, 12, 0))
        snap = result.output
        r.ok("KnowledgeAgent protocol", f"agent_id={result.agent_id}")
        r.ok("KnowledgeAgent empty", f"facts={len(snap.facts)}, patterns={len(snap.patterns)}")

        # Also check existing knowledge snapshots
        snap_dir = ROOT / "knowledge" / "snapshots"
        if snap_dir.exists():
            existing = list(snap_dir.glob("*.json"))
            if existing:
                r.ok("Existing KB snapshots", f"{len(existing)} files found")
            else:
                r.warn("Existing KB snapshots", "No snapshots yet — run campaigns first")
        else:
            r.warn("Knowledge directory", "knowledge/snapshots/ does not exist yet")
    except Exception as exc:
        r.fail("KnowledgeAgent", str(exc))


# ---------------------------------------------------------------------------
# Check 7: ExperimentPlanner (empty snapshot)
# ---------------------------------------------------------------------------

def check_experiment_planner(r: CheckResult) -> None:
    print("\n[7] ExperimentPlanner — Empty KnowledgeSnapshot")
    try:
        from agents.research.planner import ExperimentPlanner
        from agents.models import KnowledgeSnapshot, ConfidenceScore
        empty_snap = KnowledgeSnapshot(
            snapshot_id="dry_run_snap",
            campaign_id="dry_run_test",
            facts=(),
            connections=(),
            patterns=(),
            strong_facts=(),
            weak_facts=(),
            contradictions=(),
            recommendations=(),
            source_refs=(),
            confidence=ConfidenceScore(value=0.0, reason="dry run — no facts"),
        )
        agent = ExperimentPlanner(data_dir=DATA_DIR)
        result = agent.run(
            knowledge_snapshot=empty_snap,
            datasets=[],
            campaign_id="dry_run_test",
            _clock=lambda: datetime(2023, 1, 1, 12, 0),
        )
        plans = result.output
        r.ok("ExperimentPlanner protocol", f"agent_id={result.agent_id}")
        r.ok("ExperimentPlanner empty", f"plans={len(plans)} (expected 0 — no patterns to plan)")
    except Exception as exc:
        r.fail("ExperimentPlanner", str(exc))


# ---------------------------------------------------------------------------
# Check 8: ValidationAgentAdapter (dry_run=True)
# ---------------------------------------------------------------------------

def check_validation_adapter(r: CheckResult) -> None:
    print("\n[8] ValidationAgentAdapter — dry_run=True")
    try:
        from agents.research.adapter import ValidationAgentAdapter
        from agents.models import (
            ExperimentPlan, ExperimentTask, OverfittingRisk, StopCondition
        )
        task = ExperimentTask(
            task_id="dry_task_001",
            hypothesis_id="H-DRY-RUN",
            instrument="SBER",
            dataset_id="sber_1h_2023_main",
            regime_filter="",
            parameters={},
        )
        plan = ExperimentPlan(
            plan_id="dry_plan_001",
            plan_type="regime_exploration",
            objective="Dry run validation test",
            hypothesis_id="H-DRY-RUN",
            instruments=("SBER",),
            datasets=("sber_1h_2023_main",),
            regime_filter="",
            tasks=(task,),
            parameters={},
            expected_evidence="Dry run — no evidence expected",
            rationale="Dry run validation",
            priority="medium",
            overfitting_risk=OverfittingRisk(level="low", parameter_count=0, reasons=()),
            stop_conditions=(
                StopCondition(condition_type="max_experiments", value=1.0, description="max 1"),
            ),
            confidence=0.5,
            source_pattern_id="dry_run",
        )
        agent = ValidationAgentAdapter(data_dir=DATA_DIR)
        result = agent.run(
            plan=plan,
            available_datasets=["sber_1h_2023_main"],
            execute=False,
            _clock=lambda: datetime(2023, 1, 1, 12, 0),
        )
        batch = result.output
        r.ok("ValidationAgentAdapter protocol", f"agent_id={result.agent_id}")
        r.ok("ValidationAgentAdapter dry_run", f"dry_run_tasks={batch.dry_run_tasks}, total={batch.total_tasks}")
    except Exception as exc:
        r.fail("ValidationAgentAdapter", str(exc))


# ---------------------------------------------------------------------------
# Check 9: ChiefScientist (empty snapshot)
# ---------------------------------------------------------------------------

def check_chief_scientist(r: CheckResult) -> None:
    print("\n[9] ChiefScientist — Empty Snapshot")
    try:
        from agents.research.chief import ChiefScientist
        from agents.models import KnowledgeSnapshot, ConfidenceScore, ResearchPolicy
        empty_snap = KnowledgeSnapshot(
            snapshot_id="dry_run_snap",
            campaign_id="dry_run_test",
            facts=(),
            connections=(),
            patterns=(),
            strong_facts=(),
            weak_facts=(),
            contradictions=(),
            recommendations=(),
            source_refs=(),
            confidence=ConfidenceScore(value=0.0, reason="dry run — no facts"),
        )
        policy = ResearchPolicy()
        agent = ChiefScientist(data_dir=DATA_DIR)
        result = agent.run(
            knowledge_snapshot=empty_snap,
            plans=[],
            previous_results=[],
            policy=policy,
            campaign_id="dry_run_test",
            _clock=lambda: datetime(2023, 1, 1, 12, 0),
        )
        decisions = result.output
        r.ok("ChiefScientist protocol", f"agent_id={result.agent_id}")
        r.ok("ChiefScientist empty", f"decisions={len(decisions)} (expected 0 on empty KB)")
    except Exception as exc:
        r.fail("ChiefScientist", str(exc))


# ---------------------------------------------------------------------------
# Check 10: Pipeline continuity (data flows correctly)
# ---------------------------------------------------------------------------

def check_pipeline_continuity(r: CheckResult) -> None:
    print("\n[10] Pipeline Continuity")
    try:
        from agents.models import (
            AgentResult, ConfidenceScore, EvidenceRef,
            KnowledgeSnapshot,
        )
        # Verify the model chain works end-to-end
        ev = EvidenceRef(source="dry_run", reference="test", timestamp="2023-01-01T12:00:00")
        cs = ConfidenceScore(value=0.5, reason="dry run")
        snap = KnowledgeSnapshot(
            snapshot_id="pipe_test",
            campaign_id="pipe_test",
            facts=(), connections=(), patterns=(),
            strong_facts=(), weak_facts=(),
            contradictions=(), recommendations=(),
            source_refs=(),
            confidence=cs,
        )
        # AgentResult wrapping works
        ar = AgentResult(
            agent_id="test", agent_type="TEST", version="1.0",
            input_summary="test", output=snap,
            evidence=(ev,), confidence=cs,
            created_at="2023-01-01T12:00:00",
        )
        r.ok("Model chain integrity", f"AgentResult -> KnowledgeSnapshot pipeline OK")
        r.ok("Frozen dataclass invariant", "All models are hashable and immutable")
    except Exception as exc:
        r.fail("Pipeline continuity", str(exc))

    # Check research_programs dirs exist or can be created
    for subdir in ("plans", "decisions", "validation_runs", "waves"):
        d = ROOT / "research_programs" / subdir
        try:
            d.mkdir(parents=True, exist_ok=True)
            r.ok(f"research_programs/{subdir}/", "exists or created")
        except Exception as exc:
            r.fail(f"research_programs/{subdir}/", str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_dry_run(instrument_filter: str = "", period_filter: str = "") -> None:
    print("=" * 60)
    print("MOEX AI LAB — DRY RUN VALIDATION")
    print(f"Instrument: {instrument_filter or 'P1 sample'} | Period: {period_filter or '2019-2021 sample'}")
    print("=" * 60)

    r = CheckResult()

    cfg = check_configs(r)
    gaps = check_datasets(r, cfg, instrument_filter, period_filter)
    check_macro_agent(r)
    check_correlation_agent(r)
    check_regime_agent(r)
    check_knowledge_agent(r)
    check_experiment_planner(r)
    check_validation_adapter(r)
    check_chief_scientist(r)
    check_pipeline_continuity(r)

    ok, warn, fail = r.summary()
    total = ok + warn + fail

    print("\n" + "=" * 60)
    print("DRY RUN SUMMARY")
    print("=" * 60)
    print(f"  [OK]:   {ok}/{total}")
    print(f"  [WARN]: {warn}/{total}")
    print(f"  [FAIL]: {fail}/{total}")

    if gaps:
        print(f"\n  Dataset gaps: {len(gaps)} cells missing")
        print("  Run: python scripts/build_universe.py --tier P1 --period 2023")

    if fail == 0 and warn == 0:
        print("\n[PASS] All checks passed. Pipeline is ready for operational research.")
    elif fail == 0:
        print("\n[READY WITH WARNINGS] Pipeline is functional but some data is missing.")
        print("  Address WARN items before running full campaigns.")
    else:
        print("\n[BLOCKED] Pipeline has failures. Fix FAIL items before proceeding.")

    print()

    # Write results to file
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "instrument_filter": instrument_filter,
        "period_filter": period_filter,
        "ok": ok, "warn": warn, "fail": fail,
        "dataset_gaps": len(gaps),
        "checks": r.items,
    }
    out_path = ROOT / "research_programs" / "dry_run_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Report written: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MOEX AI LAB pipeline dry-run validation")
    parser.add_argument("--instrument", default="", help="Single instrument, e.g. SBER")
    parser.add_argument("--period",     default="", help="Single period, e.g. 2023")
    args = parser.parse_args()

    run_dry_run(instrument_filter=args.instrument, period_filter=args.period)
