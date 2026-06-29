"""
M11 Continuous Learning — Planner Bridge

Bridges AlphaDiscovery queue → AdaptivePlanner.
Translates discovery queue entries into planner-compatible tasks.
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Planner task representation
# ---------------------------------------------------------------------------

@dataclass
class PlannerTask:
    task_id: str
    strategy_or_instrument: str
    priority: str        # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    priority_score: float
    estimated_cost: str  # "LOW", "MEDIUM", "HIGH"
    target_timeframe: str
    target_regime: str
    source: str          # "DISCOVERY_QUEUE", "UNIVERSE_EXPANSION"


# ---------------------------------------------------------------------------
# Planner bridge
# ---------------------------------------------------------------------------

class PlannerBridge:
    """
    Bridges AlphaDiscovery → DiscoveryQueue → AdaptivePlanner.

    Converts queue entries (from M10 DiscoveryQueue or M11 DiscoveryScheduler)
    into AdaptivePlanner-compatible task format.
    """

    def __init__(self) -> None:
        self._synced_tasks: list[PlannerTask] = []
        self._sync_count = 0

    def sync_queue_to_planner(self, queue_entries: list) -> dict:
        """
        Sync a list of queue entries to the planner.

        Accepts either QueueEntry (from M10) or ScheduleEntry (from M11).
        Returns sync result summary.
        """
        added = 0
        updated = 0
        existing_ids = {t.task_id for t in self._synced_tasks}

        for entry in queue_entries:
            # Support both QueueEntry (M10) and ScheduleEntry (M11)
            if hasattr(entry, "draft_id"):
                # M10 QueueEntry
                task_id = entry.draft_id
                name = entry.name
                priority_score = entry.priority_score
                cost = entry.estimated_research_cost
                regime = (entry.target_regimes[0] if entry.target_regimes else "TREND")
                tf = (entry.target_timeframes[0] if entry.target_timeframes else "1D")
                source = "DISCOVERY_QUEUE"
            else:
                # M11 ScheduleEntry
                task_id = entry.entry_id
                name = entry.strategy_or_instrument
                priority_score = entry.priority_score
                cost = entry.estimated_cost
                regime = "TREND"  # M11 default
                tf = "1D"
                source = "UNIVERSE_EXPANSION"

            # Determine priority label from score
            if priority_score >= 0.75:
                priority = "CRITICAL"
            elif priority_score >= 0.55:
                priority = "HIGH"
            elif priority_score >= 0.35:
                priority = "MEDIUM"
            else:
                priority = "LOW"

            task = PlannerTask(
                task_id=task_id,
                strategy_or_instrument=name,
                priority=priority,
                priority_score=round(priority_score, 4),
                estimated_cost=cost,
                target_timeframe=tf,
                target_regime=regime,
                source=source,
            )

            if task_id in existing_ids:
                self._synced_tasks = [t for t in self._synced_tasks if t.task_id != task_id]
                self._synced_tasks.append(task)
                updated += 1
            else:
                self._synced_tasks.append(task)
                existing_ids.add(task_id)
                added += 1

        self._sync_count += 1
        self._synced_tasks.sort(key=lambda t: t.priority_score, reverse=True)

        return {
            "sync_number": self._sync_count,
            "entries_received": len(queue_entries),
            "added": added,
            "updated": updated,
            "total_in_planner": len(self._synced_tasks),
        }

    def get_next_research_candidate(self) -> dict | None:
        """Return the highest-priority task ready for research."""
        if not self._synced_tasks:
            return None

        task = self._synced_tasks[0]
        return {
            "task_id": task.task_id,
            "name": task.strategy_or_instrument,
            "priority": task.priority,
            "priority_score": task.priority_score,
            "estimated_cost": task.estimated_cost,
            "target_timeframe": task.target_timeframe,
            "target_regime": task.target_regime,
            "source": task.source,
        }

    def get_all_tasks(self) -> list[PlannerTask]:
        return list(self._synced_tasks)

    def task_count(self) -> int:
        return len(self._synced_tasks)
