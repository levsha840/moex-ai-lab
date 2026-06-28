from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.experiment.engine import ExperimentRunner
from core.experiment.models import ExperimentConfig
from core.hypothesis.service import HypothesisRegistry
from core.hypothesis_generator.engine import HypothesisGenerator
from core.hypothesis_generator.models import GenerationConfig
from core.hypothesis_generator.ranker import KnowledgeRanker
from core.hypothesis_generator.repository import MemoryTemplateRepository
from core.hypothesis_generator.statistics import KBTemplateStatisticsProvider
from core.knowledge.service import KnowledgeBase
from core.research_orchestrator.orchestrator import ResearchOrchestrator
from core.research_orchestrator.policy import DefaultResearchPolicy
from core.research_pipeline.pipeline import ResearchPipeline
from core.research_session.models import ResearchSessionConfig
from core.research_session.report import ResearchReportBuilder
from core.research_session.session import ResearchSession
from core.walkforward.models import WalkForwardConfig
from core.walkforward.window_generator import WalkForwardWindowGenerator

from services.research.config import ServiceConfig
from services.research.dataset import DatasetLoader, OhlcvDataset
from services.research.hypothesis_registry import HypothesisTemplateRegistry
from services.research.persistence import ArtifactWriter, JsonKnowledgeStorage
from services.research.providers import RegistryInfoProviderAdapter


@dataclass(frozen=True)
class RunResult:
    session_id: str
    report_path: Path
    session_meta_path: Path
    summary_txt_path: Path
    run_meta_path: Path
    kb_path: Path
    duration_seconds: float
    exit_code: int


class ResearchRunner:
    """Assembles Core components and executes a full research cycle.

    Makes no decisions — delegates to Core. Prints progress to stdout.
    Hypothesis selection is driven by HypothesisTemplateRegistry (YAML files).
    """

    def run(self, config: ServiceConfig) -> RunResult:
        started_at = datetime.now(timezone.utc)

        # ── 1. Load dataset ───────────────────────────────────────────────────
        print("[1/8] Loading dataset ...")
        dataset = DatasetLoader().load(config.dataset_id, config.data_dir)
        print(
            f"      {dataset.dataset_id}: {dataset.ticker} {dataset.timeframe}, "
            f"{dataset.bar_count} bars"
        )

        # ── 2. Load KnowledgeBase ─────────────────────────────────────────────
        print("\n[2/8] Loading KnowledgeBase ...")
        storage = JsonKnowledgeStorage(config.knowledge_db_path)
        prior_count = len(storage.list())
        kb = KnowledgeBase(repository=storage)
        print(f"      {config.knowledge_db_path}: {prior_count} existing entries")

        # ── 3. Initialise infrastructure ──────────────────────────────────────
        print("\n[3/8] Initialising infrastructure ...")
        registry = HypothesisRegistry()

        # Load templates from YAML registry — no H-ID specific code here
        tmpl_registry = HypothesisTemplateRegistry(config.hypotheses_dir)
        all_templates = tmpl_registry.list()

        if not all_templates:
            raise RuntimeError(
                "No hypothesis templates available. "
                "Add YAML files to the hypotheses/ directory."
            )

        # Select template: use configured id or fall back to first available
        if config.hypothesis_template_id:
            active_template = tmpl_registry.get(config.hypothesis_template_id)
        else:
            active_template = all_templates[0]

        provider_factory = tmpl_registry.get_provider_factory(active_template.template_id)
        strategy_name = tmpl_registry.get_strategy_name(active_template.template_id)

        template_repo = MemoryTemplateRepository([active_template])
        stats_provider = KBTemplateStatisticsProvider(kb, registry)
        ranker = KnowledgeRanker(stats_provider)
        generator = HypothesisGenerator(template_repo, ranker)

        wf_config = WalkForwardConfig(
            train_size=config.train_size,
            test_size=config.test_size,
            step_size=config.step_size,
        )
        feature_p, regime_p, strategy_p, validation_p = provider_factory.create_providers(
            dataset, wf_config
        )
        experiment_runner = ExperimentRunner(feature_p, regime_p, strategy_p, validation_p)
        pipeline = ResearchPipeline(experiment_runner, kb)

        orchestrator = ResearchOrchestrator()
        session = ResearchSession(generator, orchestrator)
        policy = DefaultResearchPolicy(
            max_consecutive_failures=config.max_consecutive_failures
        )

        session_config = ResearchSessionConfig(
            generation_config=GenerationConfig(max_candidates=config.max_candidates),
            experiment_config=ExperimentConfig(
                experiment_id=f"exp_{uuid4().hex[:8]}",
                hypothesis_id="",
                dataset_id=config.dataset_id,
                strategy_name=strategy_name,
                feature_set=list(active_template.required_features),
            ),
            description=config.description or f"Research session on {config.dataset_id}",
            pass_threshold=config.pass_threshold,
        )

        template_ids = ", ".join(t.template_id for t in all_templates)
        print(f"      Templates: {len(all_templates)} ({template_ids})")
        print(f"      Active: {active_template.template_id}")
        print(
            f"      WalkForward: train={config.train_size} test={config.test_size} "
            f"step={config.step_size}"
        )

        # ── 4. Run ResearchSession ────────────────────────────────────────────
        print("\n[4/8] Running ResearchSession ...")
        result = session.run(session_config, registry, pipeline, policy=policy)
        _print_task_results(result, config.pass_threshold)

        # ── 5. Build ResearchReport ───────────────────────────────────────────
        print("\n[5/8] Building ResearchReport ...")
        info_provider = RegistryInfoProviderAdapter(registry)
        report = ResearchReportBuilder(info_provider=info_provider).build(result)
        s = report.summary
        print(
            f"      {s.pass_count} PASS, {s.fail_count} FAIL, "
            f"{s.inconclusive_count} INCONCLUSIVE, {s.error_count} ERROR, "
            f"{s.skipped_count} SKIPPED"
        )

        # ── 6. KB persisted (JsonKnowledgeStorage syncs on each add) ─────────
        current_count = len(storage.list())
        new_entries = current_count - prior_count
        print(
            f"\n[6/8] KnowledgeBase: {config.knowledge_db_path} "
            f"({current_count} entries, +{new_entries} this run)"
        )

        # ── 7. Write artifacts ────────────────────────────────────────────────
        print("\n[7/8] Writing artifacts ...")
        writer = ArtifactWriter()
        session_report_dir = config.reports_dir / result.session_id
        session_sessions_dir = config.sessions_dir / result.session_id

        report_path = writer.write_report(report, session_report_dir)
        session_meta_path = writer.write_session_meta(result, session_sessions_dir)
        summary_txt_path = writer.write_summary_txt(report, dataset, session_report_dir)
        print(f"      {report_path}")
        print(f"      {session_meta_path}")
        print(f"      {summary_txt_path}")

        # ── 8. Finalise ───────────────────────────────────────────────────────
        finished_at = datetime.now(timezone.utc)
        duration = (finished_at - started_at).total_seconds()
        exit_code = _determine_exit_code(report)

        run_meta_path = writer.write_run_meta(
            config,
            result.session_id,
            exit_code,
            started_at,
            finished_at,
            config.runs_dir,
        )

        print(f"\n[8/8] Done in {duration:.1f}s\n")
        _print_final_summary(report, dataset)

        return RunResult(
            session_id=result.session_id,
            report_path=report_path,
            session_meta_path=session_meta_path,
            summary_txt_path=summary_txt_path,
            run_meta_path=run_meta_path,
            kb_path=config.knowledge_db_path,
            duration_seconds=duration,
            exit_code=exit_code,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _determine_exit_code(report: "ResearchReport") -> int:  # noqa: F821
    s = report.summary
    completed = s.pass_count + s.fail_count + s.inconclusive_count
    if completed > 0:
        return 0  # at least one task ran to completion
    if s.total_hypotheses > 0:
        return 2  # tasks generated but all skipped/error
    return 2      # nothing generated at all


def _print_task_results(result: "ResearchSessionResult", pass_threshold: float) -> None:  # noqa: F821
    for task in result.orchestration_result.plan.tasks:
        status = task.status.value
        if task.summary and task.summary.pass_rate is not None:
            pr_str = f"pass_rate={task.summary.pass_rate:.2f}"
            outcome = "PASS" if task.summary.pass_rate >= pass_threshold else "FAIL"
        else:
            pr_str = "pass_rate=n/a"
            outcome = status
        print(f"      {task.hypothesis_id[:8]}:  {status:<12}  {pr_str:<20}  [{outcome}]")


def _print_final_summary(report: "ResearchReport", dataset: OhlcvDataset) -> None:  # noqa: F821
    s = report.summary
    conclusive = s.pass_count + s.fail_count
    pass_pct = (s.pass_count / conclusive * 100) if conclusive > 0 else 0.0
    avg_str = f"{s.avg_pass_rate:.3f}" if s.avg_pass_rate is not None else "n/a"
    med_str = f"{s.median_pass_rate:.3f}" if s.median_pass_rate is not None else "n/a"
    vpr_str = (
        f"{s.validation_pass_rate:.1%}" if s.validation_pass_rate is not None else "n/a"
    )
    rec_count = len(report.recommendations)

    print("Summary:")
    print(f"  PASS: {s.pass_count}/{conclusive} conclusive ({pass_pct:.1f}%)")
    print(f"  validation_pass_rate: {vpr_str} | avg_pass_rate: {avg_str} | median: {med_str}")
    print(f"  {rec_count} recommendation(s)")
    print(f"  Session ID: {report.session_id}")
