"""Protocols for the Research Session Module."""
from __future__ import annotations

from typing import Protocol

from core.hypothesis.service import HypothesisRegistry
from core.research_orchestrator.models import OrchestrationResult, ResearchPlan
from core.research_orchestrator.protocols import ResearchPolicy
from core.research_pipeline.pipeline import ResearchPipeline
from core.research_session.report_models import HypothesisInfo


class HypothesisInfoProvider(Protocol):
    """Provides lightweight hypothesis metadata for ResearchReportBuilder.

    Returns only what the report needs (title + template_id) — not the full
    Hypothesis lifecycle object. HypothesisRegistry satisfies this Protocol
    structurally via duck typing (ADR-0016).

    Absent hypothesis_ids are silently omitted from the returned dict; this is
    not an error. ResearchReportBuilder falls back to "(unknown)" for missing entries.
    """

    def get_info(self, hypothesis_ids: list[str]) -> dict[str, HypothesisInfo]: ...


class PlanExecutor(Protocol):
    """Stateless executor that runs a ResearchPlan and returns an OrchestrationResult.

    **Statelessness contract (ADR-0014):**
    Implementations MUST NOT store mutable state between calls. The same executor
    instance can be called multiple times with different plans, registries, or
    pipelines and must behave identically each time. This constraint enables safe
    replacement with Parallel, Distributed, or Event-Aware implementations without
    any change to the ResearchSession contract.

    ResearchOrchestrator satisfies this Protocol structurally (duck typing) —
    it carries only an injected clock, which is immutable after construction.
    """

    def run(
        self,
        plan: ResearchPlan,
        registry: HypothesisRegistry,
        pipeline: ResearchPipeline,
        *,
        policy: ResearchPolicy | None = None,
    ) -> OrchestrationResult: ...
