"""YAML-based Hypothesis Template Registry for Research Service.

Design: hypothesis metadata lives in YAML files under hypotheses/.
The `provider_factory` field is a dotted Python import path resolved via
importlib at runtime. Adding a new hypothesis requires:
  1. A YAML file in hypotheses/
  2. Provider classes in experiments/<name>/
  Zero Research Service code changes.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import yaml

from core.hypothesis_generator.models import HypothesisPriority, HypothesisTemplate

# Default hypotheses directory: project root / hypotheses/
_DEFAULT_DIR = Path(__file__).parent.parent.parent / "hypotheses"


class HypothesisTemplateRegistry:
    """Loads and serves HypothesisTemplate objects from YAML/JSON files.

    Usage:
        registry = HypothesisTemplateRegistry()          # loads hypotheses/
        registry = HypothesisTemplateRegistry(my_dir)   # loads custom dir (tests)

        templates = registry.list()
        tmpl      = registry.get("tmpl_h13_adx_continuation")
        factory   = registry.get_provider_factory("tmpl_h13_adx_continuation")
        name      = registry.get_strategy_name("tmpl_h13_adx_continuation")
    """

    def __init__(self, hypotheses_dir: Path | None = None) -> None:
        self._dir = hypotheses_dir or _DEFAULT_DIR
        self._templates: dict[str, HypothesisTemplate] = {}
        self._provider_paths: dict[str, str] = {}
        self._strategy_names: dict[str, str] = {}
        self._load_all()

    # ── Public API ────────────────────────────────────────────────────────────

    def list(self) -> list[HypothesisTemplate]:
        """All loaded templates in load order (alphabetical by filename)."""
        return list(self._templates.values())

    def get(self, template_id: str) -> HypothesisTemplate:
        try:
            return self._templates[template_id]
        except KeyError:
            raise KeyError(
                f"Hypothesis template not found: {template_id!r}. "
                f"Available: {list(self._templates)}"
            )

    def get_provider_factory(self, template_id: str) -> Any:
        """Resolve and instantiate the provider factory registered for *template_id*.

        The `provider_factory` field in the YAML is a dotted import path:
          experiments.h13_adx_continuation.providers.AdxContinuationProviderFactory
        importlib resolves it at call time — no static import in Research Service.
        """
        path = self._provider_paths.get(template_id)
        if not path:
            raise KeyError(
                f"No provider_factory registered for template_id: {template_id!r}"
            )
        module_path, class_name = path.rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(
                f"Cannot import provider module {module_path!r} "
                f"(registered in template {template_id!r}): {exc}"
            ) from exc
        try:
            factory_class = getattr(module, class_name)
        except AttributeError as exc:
            raise AttributeError(
                f"Module {module_path!r} has no class {class_name!r} "
                f"(registered in template {template_id!r}): {exc}"
            ) from exc
        return factory_class()

    def get_strategy_name(self, template_id: str) -> str:
        """Return the strategy_name for this template (used in ExperimentConfig)."""
        return self._strategy_names.get(template_id, template_id)

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        if not self._dir.is_dir():
            return
        paths = sorted(
            p for p in self._dir.iterdir()
            if p.suffix in (".yaml", ".yml", ".json")
        )
        for path in paths:
            try:
                self._load_one(path)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load hypothesis template from {path}: {exc}"
                ) from exc

    def _load_one(self, path: Path) -> None:
        with open(path, encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                data: dict[str, Any] = yaml.safe_load(f)
            else:
                data = json.load(f)

        template = HypothesisTemplate(
            template_id=data["template_id"],
            name=data["name"],
            category=data["category"],
            priority=HypothesisPriority[str(data["priority"])],
            title_template=data["title_template"],
            statement_template=data["statement_template"],
            required_features=list(data["required_features"]),
            default_parameters=dict(data["default_parameters"]),
        )
        self._templates[template.template_id] = template
        if "provider_factory" in data:
            self._provider_paths[template.template_id] = str(data["provider_factory"])
        if "strategy_name" in data:
            self._strategy_names[template.template_id] = str(data["strategy_name"])
