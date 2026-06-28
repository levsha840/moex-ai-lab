"""Hypothesis template access for Research Service.

Templates are declared in YAML files under hypotheses/ and loaded via
HypothesisTemplateRegistry. No hardcoded template references here.
"""
from services.research.hypothesis_registry import HypothesisTemplateRegistry

__all__ = ["HypothesisTemplateRegistry"]
