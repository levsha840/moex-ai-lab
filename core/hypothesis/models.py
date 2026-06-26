from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class HypothesisStatus(str, Enum):
    IDEA = "IDEA"
    DRAFT = "DRAFT"
    RESEARCH = "RESEARCH"
    BACKTEST = "BACKTEST"
    WALKFORWARD = "WALKFORWARD"
    PAPER_TRADING = "PAPER_TRADING"
    PRODUCTION = "PRODUCTION"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


@dataclass
class Hypothesis:
    id: str
    title: str
    statement: str
    status: HypothesisStatus
    created_at: datetime
    updated_at: datetime
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
