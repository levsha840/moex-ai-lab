from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.knowledge.models import KnowledgeEntry, KnowledgeType
from core.research_session.models import ResearchSessionResult
from core.research_session.report_models import ResearchReport

from services.research.dataset import OhlcvDataset


# ─────────────────────────────────────────────────────────────────────────────
# JsonKnowledgeStorage
# ─────────────────────────────────────────────────────────────────────────────

class JsonKnowledgeStorage:
    """KnowledgeRepository Protocol implementation backed by a local JSON file.

    Named 'Storage' to distinguish from Core's KnowledgeRepository Protocol.
    Satisfies KnowledgeRepository via structural typing (duck typing) — SA-ADR-002.
    Loads existing entries on init. Each add() syncs to disk immediately.
    """

    _VERSION = "1.0"

    def __init__(self, path: Path) -> None:
        self._path = path
        self._store: dict[str, KnowledgeEntry] = {}
        if path.exists():
            self._load()

    # ── KnowledgeRepository Protocol ─────────────────────────────────────────

    def add(self, entry: KnowledgeEntry) -> None:
        if entry.id in self._store:
            raise KeyError(f"KnowledgeEntry already exists: {entry.id!r}")
        self._store[entry.id] = copy.deepcopy(entry)
        self._save()

    def get(self, id: str) -> KnowledgeEntry | None:
        stored = self._store.get(id)
        return copy.deepcopy(stored) if stored is not None else None

    def list(self) -> list[KnowledgeEntry]:
        return [copy.deepcopy(e) for e in self._store.values()]

    def delete(self, id: str) -> None:
        if id not in self._store:
            raise KeyError(f"KnowledgeEntry not found: {id!r}")
        del self._store[id]
        self._save()

    def find_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        return [copy.deepcopy(e) for e in self._store.values() if tag in e.tags]

    def find_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeEntry]:
        return [
            copy.deepcopy(e)
            for e in self._store.values()
            if e.knowledge_type == knowledge_type
        ]

    # ── Persistence helpers ───────────────────────────────────────────────────

    def _load(self) -> None:
        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)
        for entry_dict in data.get("entries", []):
            entry = _deserialize_entry(entry_dict)
            self._store[entry.id] = entry

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self._VERSION,
            "entries": [_serialize_entry(e) for e in self._store.values()],
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)


def _serialize_entry(entry: KnowledgeEntry) -> dict:
    return {
        "id": entry.id,
        "knowledge_type": entry.knowledge_type.value,
        "reference_id": entry.reference_id,
        "summary": entry.summary,
        "tags": list(entry.tags),
        "created_at": entry.created_at.isoformat(),
        "metadata": dict(entry.metadata),
    }


def _deserialize_entry(d: dict) -> KnowledgeEntry:
    return KnowledgeEntry(
        id=d["id"],
        knowledge_type=KnowledgeType(d["knowledge_type"]),
        reference_id=d["reference_id"],
        summary=d["summary"],
        tags=list(d["tags"]),
        created_at=datetime.fromisoformat(d["created_at"]),
        metadata=dict(d.get("metadata", {})),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ArtifactWriter
# ─────────────────────────────────────────────────────────────────────────────

class ArtifactWriter:
    """Writes run artifacts to local filesystem. No Core dependencies."""

    def write_report(self, report: ResearchReport, report_dir: Path) -> Path:
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / "report.json"
        payload = _report_to_dict(report)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path

    def write_session_meta(
        self,
        result: ResearchSessionResult,
        session_dir: Path,
    ) -> Path:
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / "session_meta.json"
        stats = result.statistics
        payload = {
            "session_id": result.session_id,
            "status": result.status.value,
            "started_at": result.started_at.isoformat(),
            "finished_at": result.finished_at.isoformat(),
            "duration_seconds": stats.duration_seconds,
            "dataset_id": result.config.experiment_config.dataset_id,
            "pass_threshold": result.config.pass_threshold,
            "candidates_generated": stats.candidates_generated,
            "hypotheses_accepted": stats.hypotheses_accepted,
            "tasks_completed": stats.tasks_completed,
            "tasks_failed": stats.tasks_failed,
            "tasks_skipped": stats.tasks_skipped,
            "validation_pass": stats.validation_pass,
            "validation_fail": stats.validation_fail,
            "validation_inconclusive": stats.validation_inconclusive,
            "avg_pass_rate": stats.avg_pass_rate,
            "kb_entries_created": stats.kb_entries_created,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path

    def write_summary_txt(
        self,
        report: ResearchReport,
        dataset: OhlcvDataset,
        report_dir: Path,
    ) -> Path:
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / "summary.txt"
        text = _format_summary(report, dataset)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def write_run_meta(
        self,
        config: "ServiceConfig",  # noqa: F821  (avoid circular import in type hint)
        session_id: str,
        exit_code: int,
        started_at: datetime,
        finished_at: datetime,
        runs_dir: Path,
    ) -> Path:
        date_str = started_at.strftime("%Y-%m-%d")
        run_dir = runs_dir / date_str / session_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "run_meta.json"

        payload: dict[str, Any] = {
            "session_id": session_id,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "exit_code": exit_code,
            "config": {
                "dataset_id": config.dataset_id,
                "data_dir": str(config.data_dir),
                "max_candidates": config.max_candidates,
                "pass_threshold": config.pass_threshold,
                "max_consecutive_failures": config.max_consecutive_failures,
                "output_dir": str(config.output_dir),
                "description": config.description,
                "train_size": config.train_size,
                "test_size": config.test_size,
                "step_size": config.step_size,
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _report_to_dict(report: ResearchReport) -> dict:
    s = report.summary
    return {
        "report_id": report.report_id,
        "generated_at": report.generated_at.isoformat(),
        "session_id": report.session_id,
        "summary": {
            "session_id": s.session_id,
            "description": s.description,
            "status": s.status.value,
            "total_hypotheses": s.total_hypotheses,
            "pass_count": s.pass_count,
            "fail_count": s.fail_count,
            "inconclusive_count": s.inconclusive_count,
            "error_count": s.error_count,
            "skipped_count": s.skipped_count,
            "validation_pass_rate": s.validation_pass_rate,
            "avg_pass_rate": s.avg_pass_rate,
            "median_pass_rate": s.median_pass_rate,
            "kb_entries_created": s.kb_entries_created,
            "duration_seconds": s.duration_seconds,
            "pass_threshold": s.pass_threshold,
        },
        "findings": [
            {
                "hypothesis_id": f.hypothesis_id,
                "hypothesis_title": f.hypothesis_title,
                "template_id": f.template_id,
                "outcome": f.outcome.value,
                "pass_rate": f.pass_rate,
                "windows_total": f.windows_total,
                "knowledge_entry_id": f.knowledge_entry_id,
                "strategy_name": f.strategy_name,
                "rationale": f.rationale,
            }
            for f in report.findings
        ],
        "recommendations": [
            {
                "kind": r.kind.value,
                "scope": r.scope.value,
                "hypothesis_id": r.hypothesis_id,
                "rationale": r.rationale,
                "priority": r.priority.value,
            }
            for r in report.recommendations
        ],
    }


def _format_summary(report: ResearchReport, dataset: OhlcvDataset) -> str:
    s = report.summary
    conclusive = s.pass_count + s.fail_count
    pass_pct = (s.pass_count / conclusive * 100) if conclusive > 0 else 0.0
    avg_str = f"{s.avg_pass_rate:.3f}" if s.avg_pass_rate is not None else "n/a"
    med_str = f"{s.median_pass_rate:.3f}" if s.median_pass_rate is not None else "n/a"
    vpr_str = (
        f"{s.validation_pass_rate:.1%}" if s.validation_pass_rate is not None else "n/a"
    )
    med_count = s.pass_count + s.fail_count  # non-None pass_rates

    lines = [
        "Research Service — Session Summary",
        "═" * 55,
        f"Session:   {report.session_id}",
        f"Dataset:   {dataset.dataset_id} ({dataset.ticker} {dataset.timeframe}, {dataset.bar_count} bars)",
        f"Duration:  {s.duration_seconds:.1f}s",
        "",
        "Results:",
        f"  PASS:          {s.pass_count} / {conclusive} conclusive ({pass_pct:.1f}%)",
        f"  FAIL:          {s.fail_count} / {conclusive} conclusive",
        f"  INCONCLUSIVE:  {s.inconclusive_count}",
        f"  SKIPPED:       {s.skipped_count}",
        f"  ERROR:         {s.error_count}",
        "",
        "Metrics:",
        f"  validation_pass_rate: {vpr_str}",
        f"  avg_pass_rate:        {avg_str}  (n={med_count})",
        f"  median_pass_rate:     {med_str}  (n={med_count})",
        f"  KB entries:           {s.kb_entries_created}",
        "",
    ]

    if report.recommendations:
        high = sum(1 for r in report.recommendations if r.priority.value == "HIGH")
        med = sum(1 for r in report.recommendations if r.priority.value == "MEDIUM")
        low = sum(1 for r in report.recommendations if r.priority.value == "LOW")
        parts = []
        if high:
            parts.append(f"{high} HIGH")
        if med:
            parts.append(f"{med} MEDIUM")
        if low:
            parts.append(f"{low} LOW")
        lines.append(f"Recommendations: {len(report.recommendations)} ({', '.join(parts)})")
    else:
        lines.append("Recommendations: none")

    lines.append("═" * 55)
    return "\n".join(lines) + "\n"
