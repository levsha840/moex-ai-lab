from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class KnowledgeType(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT = "EXPERIMENT"
    FEATURE = "FEATURE"
    REGIME = "REGIME"
    VALIDATION = "VALIDATION"
    OBSERVATION = "OBSERVATION"


@dataclass
class KnowledgeEntry:
    id: str
    knowledge_type: KnowledgeType
    reference_id: str
    summary: str
    tags: list[str]
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
