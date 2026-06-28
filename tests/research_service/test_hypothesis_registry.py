"""Tests for HypothesisTemplateRegistry.

Key assertion: adding a new hypothesis requires only a YAML file +
provider classes — zero Research Service code changes. Tests prove this
through the registry's YAML loading and importlib resolution.
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from services.research.hypothesis_registry import HypothesisTemplateRegistry


# ─── Default directory (real hypotheses/) ────────────────────────────────────

class TestDefaultRegistry:
    """Registry loads from the real hypotheses/ directory."""

    @pytest.fixture(scope="class")
    def registry(self) -> HypothesisTemplateRegistry:
        return HypothesisTemplateRegistry()

    def test_loads_all_hypotheses(self, registry):
        assert len(registry.list()) >= 10

    def test_lists_h_adx_continuation(self, registry):
        ids = [t.template_id for t in registry.list()]
        assert "tmpl_h13_adx_continuation" in ids

    def test_lists_h_rev_vol_reg(self, registry):
        ids = [t.template_id for t in registry.list()]
        assert "tmpl_h_rev_vol_reg" in ids

    def test_get_by_id_returns_template(self, registry):
        t = registry.get("tmpl_h13_adx_continuation")
        assert t.template_id == "tmpl_h13_adx_continuation"
        assert t.name == "ADX Trend Continuation with RSI Pullback"

    def test_get_unknown_id_raises_key_error(self, registry):
        with pytest.raises(KeyError, match="tmpl_does_not_exist"):
            registry.get("tmpl_does_not_exist")

    def test_h_adx_continuation_required_features(self, registry):
        t = registry.get("tmpl_h13_adx_continuation")
        assert "adx_14" in t.required_features
        assert "rsi_14" in t.required_features

    def test_h_rev_vol_reg_required_features(self, registry):
        t = registry.get("tmpl_h_rev_vol_reg")
        assert "bb_zscore_20" in t.required_features
        assert "realized_vol_20" in t.required_features

    def test_h_adx_strategy_name(self, registry):
        assert registry.get_strategy_name("tmpl_h13_adx_continuation") == "adx_continuation"

    def test_h_rev_vol_reg_strategy_name(self, registry):
        assert registry.get_strategy_name("tmpl_h_rev_vol_reg") == "rev_vol_reg"

    def test_alphabetical_order(self, registry):
        ids = [t.template_id for t in registry.list()]
        assert ids.index("tmpl_h13_adx_continuation") < ids.index("tmpl_h_rev_vol_reg")

    def test_priority_loaded(self, registry):
        from core.hypothesis_generator.models import HypothesisPriority
        t = registry.get("tmpl_h13_adx_continuation")
        assert t.priority == HypothesisPriority.A

    def test_default_parameters_loaded(self, registry):
        t = registry.get("tmpl_h13_adx_continuation")
        assert t.default_parameters["ticker"] == "SBER"
        assert t.default_parameters["adx_threshold"] == 25


# ─── Provider factory resolution ─────────────────────────────────────────────

class TestProviderFactoryResolution:
    @pytest.fixture(scope="class")
    def registry(self) -> HypothesisTemplateRegistry:
        return HypothesisTemplateRegistry()

    def test_h_adx_factory_resolves(self, registry):
        factory = registry.get_provider_factory("tmpl_h13_adx_continuation")
        from experiments.h13_adx_continuation.providers import AdxContinuationProviderFactory
        assert isinstance(factory, AdxContinuationProviderFactory)

    def test_h_rev_vol_reg_factory_resolves(self, registry):
        factory = registry.get_provider_factory("tmpl_h_rev_vol_reg")
        from experiments.h_rev_vol_reg.providers import RevVolRegProviderFactory
        assert isinstance(factory, RevVolRegProviderFactory)

    def test_factory_has_create_providers_method(self, registry):
        factory = registry.get_provider_factory("tmpl_h_rev_vol_reg")
        assert callable(getattr(factory, "create_providers", None))

    def test_missing_provider_factory_raises_key_error(self, tmp_path):
        yaml_text = dedent("""\
            template_id: tmpl_no_factory
            name: "No Factory"
            category: "Test"
            priority: A
            title_template: "T on {ticker}"
            statement_template: "S for {ticker}"
            required_features: [adx_14]
            default_parameters:
              ticker: SBER
        """)
        (tmp_path / "no_factory.yaml").write_text(yaml_text, encoding="utf-8")
        registry = HypothesisTemplateRegistry(tmp_path)
        with pytest.raises(KeyError, match="No provider_factory registered"):
            registry.get_provider_factory("tmpl_no_factory")

    def test_bad_module_path_raises_import_error(self, tmp_path):
        yaml_text = dedent("""\
            template_id: tmpl_bad_module
            name: "Bad Module"
            category: "Test"
            priority: A
            title_template: "T on {ticker}"
            statement_template: "S for {ticker}"
            required_features: [adx_14]
            default_parameters:
              ticker: SBER
            provider_factory: experiments.nonexistent_module.providers.SomeFactory
        """)
        (tmp_path / "bad_module.yaml").write_text(yaml_text, encoding="utf-8")
        registry = HypothesisTemplateRegistry(tmp_path)
        with pytest.raises(ImportError):
            registry.get_provider_factory("tmpl_bad_module")

    def test_bad_class_name_raises_attribute_error(self, tmp_path):
        yaml_text = dedent("""\
            template_id: tmpl_bad_class
            name: "Bad Class"
            category: "Test"
            priority: A
            title_template: "T on {ticker}"
            statement_template: "S for {ticker}"
            required_features: [adx_14]
            default_parameters:
              ticker: SBER
            provider_factory: experiments.h_rev_vol_reg.providers.NonExistentFactory
        """)
        (tmp_path / "bad_class.yaml").write_text(yaml_text, encoding="utf-8")
        registry = HypothesisTemplateRegistry(tmp_path)
        with pytest.raises(AttributeError):
            registry.get_provider_factory("tmpl_bad_class")


# ─── Custom directory (empty) ─────────────────────────────────────────────────

class TestEmptyDirectory:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        registry = HypothesisTemplateRegistry(tmp_path)
        assert registry.list() == []

    def test_nonexistent_dir_returns_empty_list(self, tmp_path):
        registry = HypothesisTemplateRegistry(tmp_path / "does_not_exist")
        assert registry.list() == []


# ─── KEY PROOF: new hypothesis without core change ───────────────────────────

class TestNewHypothesisWithoutCoreChange:
    """
    PROVES requirement: "Добавление новой гипотезы не требует изменения Research Service."

    A completely new hypothesis (not H-ADX-CONTINUATION, not H-REV-VOL-REG) is
    loaded purely by placing a YAML file in a directory. No Research Service code
    is changed — this test is written BEFORE the hypothesis exists in hypotheses/.
    """

    def _write_custom_yaml(self, directory: Path, template_id: str, factory_path: str) -> None:
        yaml_text = dedent(f"""\
            template_id: {template_id}
            name: "Custom Momentum Filter"
            category: "Momentum"
            priority: B
            title_template: "Custom on {{ticker}}"
            statement_template: "Custom hypothesis statement for {{ticker}} in {{regime}}"
            required_features:
              - adx_14
              - rsi_14
              - atr_14
            default_parameters:
              ticker: GAZP
              regime: TREND_UP
            strategy_name: custom_momentum
            provider_factory: {factory_path}
        """)
        (directory / "custom_hyp.yaml").write_text(yaml_text, encoding="utf-8")

    def test_custom_yaml_loads_without_changing_any_rs_code(self, tmp_path):
        """New hypothesis loaded from YAML — Research Service code unchanged."""
        self._write_custom_yaml(
            tmp_path,
            template_id="tmpl_custom_momentum",
            factory_path="experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory",
        )
        registry = HypothesisTemplateRegistry(tmp_path)
        templates = registry.list()
        assert len(templates) == 1
        assert templates[0].template_id == "tmpl_custom_momentum"
        assert templates[0].category == "Momentum"
        assert "adx_14" in templates[0].required_features

    def test_custom_hypothesis_factory_resolves_via_importlib(self, tmp_path):
        """Provider factory resolved via importlib — no static import in Research Service."""
        self._write_custom_yaml(
            tmp_path,
            template_id="tmpl_custom_importlib",
            factory_path="experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory",
        )
        registry = HypothesisTemplateRegistry(tmp_path)
        factory = registry.get_provider_factory("tmpl_custom_importlib")
        assert hasattr(factory, "create_providers")

    def test_adding_second_hypothesis_alongside_existing(self, tmp_path):
        """Two hypotheses in one directory — both load without interfering."""
        self._write_custom_yaml(
            tmp_path,
            template_id="tmpl_custom_a",
            factory_path="experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory",
        )
        yaml_b = dedent("""\
            template_id: tmpl_custom_b
            name: "Custom B"
            category: "Volatility"
            priority: A
            title_template: "B on {ticker}"
            statement_template: "B statement {ticker}"
            required_features: [rsi_14]
            default_parameters:
              ticker: SBER
            strategy_name: custom_b
            provider_factory: experiments.h13_adx_continuation.providers.AdxContinuationProviderFactory
        """)
        (tmp_path / "custom_b.yaml").write_text(yaml_b, encoding="utf-8")

        registry = HypothesisTemplateRegistry(tmp_path)
        assert len(registry.list()) == 2
        ids = {t.template_id for t in registry.list()}
        assert ids == {"tmpl_custom_a", "tmpl_custom_b"}

    def test_json_format_also_supported(self, tmp_path):
        """JSON format works alongside YAML — registry is format-agnostic."""
        json_text = """{
            "template_id": "tmpl_json_format",
            "name": "JSON Format Test",
            "category": "Test",
            "priority": "A",
            "title_template": "JSON on {ticker}",
            "statement_template": "JSON statement for {ticker}",
            "required_features": ["adx_14"],
            "default_parameters": {"ticker": "SBER"},
            "strategy_name": "json_strategy",
            "provider_factory": "experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory"
        }"""
        (tmp_path / "json_hyp.json").write_text(json_text, encoding="utf-8")
        registry = HypothesisTemplateRegistry(tmp_path)
        assert len(registry.list()) == 1
        assert registry.list()[0].template_id == "tmpl_json_format"

    def test_strategy_name_from_custom_yaml(self, tmp_path):
        """strategy_name from YAML flows through correctly."""
        self._write_custom_yaml(
            tmp_path,
            template_id="tmpl_strategy_name_test",
            factory_path="experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory",
        )
        registry = HypothesisTemplateRegistry(tmp_path)
        assert registry.get_strategy_name("tmpl_strategy_name_test") == "custom_momentum"

    def test_title_template_renders_with_default_parameters(self, tmp_path):
        """HypothesisTemplate.instantiate() works on registry-loaded templates."""
        self._write_custom_yaml(
            tmp_path,
            template_id="tmpl_render_test",
            factory_path="experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory",
        )
        registry = HypothesisTemplateRegistry(tmp_path)
        tmpl = registry.get("tmpl_render_test")
        title, _ = tmpl.instantiate()
        assert "GAZP" in title
