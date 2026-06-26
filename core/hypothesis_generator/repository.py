"""In-memory implementation of TemplateRepository."""
from __future__ import annotations

import copy

from core.hypothesis_generator.models import HypothesisTemplate


class MemoryTemplateRepository:
    """Thread-unsafe in-memory store. deepcopy on add() and get() for isolation."""

    def __init__(self, templates: list[HypothesisTemplate] | None = None) -> None:
        self._store: dict[str, HypothesisTemplate] = {}
        for template in templates or []:
            self.add(template)

    def add(self, template: HypothesisTemplate) -> None:
        """Store a deepcopy; overwrites an existing entry with the same template_id."""
        self._store[template.template_id] = copy.deepcopy(template)

    def get(self, template_id: str) -> HypothesisTemplate:
        """Return a deepcopy. Raises KeyError if template_id is not found."""
        try:
            return copy.deepcopy(self._store[template_id])
        except KeyError:
            raise KeyError(f"Template not found: {template_id!r}")

    def list(self) -> list[HypothesisTemplate]:
        """Return deepcopies of all templates in insertion order."""
        return [copy.deepcopy(t) for t in self._store.values()]

    def list_by_category(self, category: str) -> list[HypothesisTemplate]:
        """Return deepcopies of templates matching the given category."""
        return [
            copy.deepcopy(t)
            for t in self._store.values()
            if t.category == category
        ]
