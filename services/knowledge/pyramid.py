"""Knowledge Pyramid — M6.5.

Classifies accumulated IE facts into four epistemological tiers:

  Level 1  Experiment         — any single IE result
  Level 2  Evidence           — 3+ experiments, avg_pr >= 0.20
  Level 3  Knowledge          — 5+ experiments, avg_pr >= 0.28, 2+ periods
  Level 4  Scientific Conclusion — avg_pr >= 0.35, consistency >= 40%, 3+ periods

Chief Scientist only acts on Level 3+ units.
"""
from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from dataclasses import dataclass, field

IE_DIR = pathlib.Path(__file__).parent.parent.parent / "ie_reports"

# Tier thresholds
EVIDENCE_MIN_RUNS    = 3
EVIDENCE_MIN_PR      = 0.20
KNOWLEDGE_MIN_RUNS   = 5
KNOWLEDGE_MIN_PR     = 0.28
KNOWLEDGE_MIN_PERIODS = 2
CONCLUSION_MIN_PR    = 0.35
CONCLUSION_MIN_CONSISTENCY = 0.40
CONCLUSION_MIN_PERIODS     = 3

LEVEL_NAMES = {
    1: "Experiment",
    2: "Evidence",
    3: "Knowledge",
    4: "Scientific Conclusion",
}

LEVEL_NAMES_RU = {
    1: "Эксперимент",
    2: "Свидетельство",
    3: "Знание",
    4: "Научный вывод",
}


@dataclass
class PyramidUnit:
    hypothesis_id: str
    instrument: str
    total_runs: int
    avg_pass_rate: float
    best_pass_rate: float
    periods: set[str]     = field(default_factory=set)
    timeframes: set[str]  = field(default_factory=set)
    consistency: float    = 0.0   # % of periods where avg_pr >= 0.35
    level: int            = 1
    level_name: str       = "Experiment"
    level_name_ru: str    = "Эксперимент"


@dataclass
class PyramidReport:
    units: list[PyramidUnit]
    level_counts: dict[int, int]
    chief_conclusions: list[str]

    @property
    def total_units(self) -> int:
        return len(self.units)

    @property
    def conclusion_units(self) -> list[PyramidUnit]:
        return [u for u in self.units if u.level == 4]

    @property
    def knowledge_units(self) -> list[PyramidUnit]:
        return [u for u in self.units if u.level >= 3]


def build_pyramid(ie_dir: pathlib.Path = IE_DIR) -> PyramidReport:
    """Load all IE facts and build the Knowledge Pyramid."""
    if not ie_dir.exists():
        return PyramidReport(units=[], level_counts={1: 0, 2: 0, 3: 0, 4: 0}, chief_conclusions=[])

    # Group facts by (hypothesis_id, instrument)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for campaign_dir in sorted(ie_dir.iterdir()):
        if not campaign_dir.is_dir():
            continue
        for jf in campaign_dir.glob("*.json"):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                hyp   = d.get("hypothesis_id", "")
                instr = d.get("instrument", "")
                if hyp and instr:
                    groups[(hyp, instr)].append(d)
            except Exception:
                pass

    units: list[PyramidUnit] = []

    for (hyp, instr), facts in groups.items():
        prs       = [float(f.get("pass_rate", 0.0)) for f in facts]
        periods   = {f.get("period", "")    for f in facts if f.get("period")}
        timeframes = {f.get("timeframe", "") for f in facts if f.get("timeframe")}
        n         = len(prs)
        avg_pr    = sum(prs) / n if prs else 0.0
        best_pr   = max(prs)  if prs else 0.0

        # Consistency: % of periods where that period's avg_pr >= 0.35
        per_period_prs: dict[str, list[float]] = defaultdict(list)
        for f in facts:
            p = f.get("period", "")
            if p:
                per_period_prs[p].append(float(f.get("pass_rate", 0.0)))

        if per_period_prs:
            periods_above = sum(
                1 for pprs in per_period_prs.values()
                if sum(pprs) / len(pprs) >= 0.35
            )
            consistency = periods_above / len(per_period_prs)
        else:
            consistency = 0.0

        # Classify into pyramid tier
        level = 1
        if n >= EVIDENCE_MIN_RUNS and avg_pr >= EVIDENCE_MIN_PR:
            level = 2
        if (
            n >= KNOWLEDGE_MIN_RUNS
            and avg_pr >= KNOWLEDGE_MIN_PR
            and len(periods) >= KNOWLEDGE_MIN_PERIODS
        ):
            level = 3
        if (
            avg_pr >= CONCLUSION_MIN_PR
            and consistency >= CONCLUSION_MIN_CONSISTENCY
            and len(periods) >= CONCLUSION_MIN_PERIODS
        ):
            level = 4

        units.append(PyramidUnit(
            hypothesis_id=hyp,
            instrument=instr,
            total_runs=n,
            avg_pass_rate=avg_pr,
            best_pass_rate=best_pr,
            periods=periods,
            timeframes=timeframes,
            consistency=consistency,
            level=level,
            level_name=LEVEL_NAMES[level],
            level_name_ru=LEVEL_NAMES_RU[level],
        ))

    # Sort: highest tier first, then by avg_pr
    units.sort(key=lambda u: (-u.level, -u.avg_pass_rate))

    level_counts: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for u in units:
        level_counts[u.level] = level_counts.get(u.level, 0) + 1

    # Chief Scientist scientific conclusions
    chief_conclusions = [
        f"{u.hypothesis_id} x {u.instrument}: "
        f"avg_pr={u.avg_pass_rate:.4f}, "
        f"consistency={u.consistency:.0%}, "
        f"periods={len(u.periods)}"
        for u in units
        if u.level == 4
    ]

    return PyramidReport(
        units=units,
        level_counts=level_counts,
        chief_conclusions=chief_conclusions,
    )
