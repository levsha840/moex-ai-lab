"""TemplateStatisticsProvider implementations."""
from __future__ import annotations

from core.hypothesis_generator.models import TemplateStats
from core.knowledge.models import KnowledgeEntry, KnowledgeType
from core.knowledge.service import KnowledgeBase
from core.hypothesis.service import HypothesisRegistry

_CONCLUSIVE = frozenset({"PASS", "FAIL"})


class KBTemplateStatisticsProvider:
    """Builds TemplateStats by querying KnowledgeBase and resolving template_ids
    via HypothesisRegistry.

    Resolution chain:
        KnowledgeEntry.reference_id
            → HypothesisRegistry.get(hypothesis_id)
            → hypothesis.metadata["template_id"]

    Only KnowledgeType.EXPERIMENT entries with validation_status in {PASS, FAIL}
    are counted. Inconclusive entries (status missing or not PASS/FAIL) are skipped.
    Entries whose hypothesis is not found in the registry, or whose hypothesis has
    no template_id in metadata, are silently skipped.
    """

    def __init__(self, knowledge_base: KnowledgeBase, registry: HypothesisRegistry) -> None:
        self._kb = knowledge_base
        self._registry = registry

    def get_stats(self) -> dict[str, TemplateStats]:
        entries = self._kb.find_by_type(KnowledgeType.EXPERIMENT)

        counts: dict[str, dict[str, int]] = {}

        for entry in entries:
            template_id = self._resolve_template_id(entry)
            if template_id is None:
                continue

            status = entry.metadata.get("validation_status", "")
            if status not in _CONCLUSIVE:
                continue

            if template_id not in counts:
                counts[template_id] = {"pass": 0, "fail": 0}

            if status == "PASS":
                counts[template_id]["pass"] += 1
            else:
                counts[template_id]["fail"] += 1

        return {
            tid: TemplateStats(
                template_id=tid,
                pass_count=c["pass"],
                fail_count=c["fail"],
                experiment_count=c["pass"] + c["fail"],
            )
            for tid, c in counts.items()
        }

    def _resolve_template_id(self, entry: KnowledgeEntry) -> str | None:
        try:
            hypothesis = self._registry.get(entry.reference_id)
        except KeyError:
            return None

        template_id = hypothesis.metadata.get("template_id")
        return str(template_id) if template_id is not None else None
