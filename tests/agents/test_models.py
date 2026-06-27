"""Tests for Intelligence Era domain models — Phase 1 + Phase 2 + Phase 3 + Phase 4.

Validates structure, immutability, and invariants of all models
in agents/models.py. No I/O, no network.
"""
from __future__ import annotations

import math

import pytest

from agents.models import (
    AgentResult,
    ConfidenceScore,
    CorrelationPair,
    CorrelationSnapshot,
    DatasetManifest,
    EvidenceRef,
    MacroSeries,
    MacroSnapshot,
    MarketSnapshot,
    RegimeLabel,
    RegimeSegment,
    RegimeSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evidence() -> EvidenceRef:
    return EvidenceRef(
        source="test",
        reference="fixture://candles",
        timestamp="2023-01-10T10:00:00",
    )


def _confidence(value: float = 1.0) -> ConfidenceScore:
    return ConfidenceScore(value=value, reason="test")


def _manifest() -> DatasetManifest:
    return DatasetManifest(
        dataset_id="sber_1h_2023_main",
        dataset_path="/data/datasets/sber_1h_2023_main",
        ohlcv_path="/data/datasets/sber_1h_2023_main/ohlcv.csv",
        metadata_path="/data/datasets/sber_1h_2023_main/metadata.json",
        ticker="SBER",
        timeframe="1h",
        bar_count=2540,
        date_from="2023-01-10",
        date_to="2023-12-29",
        session_filter="main",
        source="MOEX ISS API",
    )


# ---------------------------------------------------------------------------
# EvidenceRef
# ---------------------------------------------------------------------------

class TestEvidenceRef:
    def test_construction(self) -> None:
        ref = _evidence()
        assert ref.source == "test"
        assert ref.reference == "fixture://candles"
        assert ref.timestamp == "2023-01-10T10:00:00"

    def test_is_frozen(self) -> None:
        ref = _evidence()
        with pytest.raises((AttributeError, TypeError)):
            ref.source = "mutated"  # type: ignore[misc]

    def test_hashable(self) -> None:
        ref = _evidence()
        assert hash(ref) is not None
        assert {ref, ref} == {ref}

    def test_equality(self) -> None:
        a = _evidence()
        b = _evidence()
        assert a == b

    def test_inequality_on_different_source(self) -> None:
        a = EvidenceRef(source="a", reference="x", timestamp="t")
        b = EvidenceRef(source="b", reference="x", timestamp="t")
        assert a != b


# ---------------------------------------------------------------------------
# ConfidenceScore
# ---------------------------------------------------------------------------

class TestConfidenceScore:
    def test_valid_score(self) -> None:
        cs = _confidence(0.75)
        assert cs.value == 0.75
        assert cs.reason == "test"

    def test_boundary_zero(self) -> None:
        cs = ConfidenceScore(value=0.0, reason="no data")
        assert cs.value == 0.0

    def test_boundary_one(self) -> None:
        cs = ConfidenceScore(value=1.0, reason="complete")
        assert cs.value == 1.0

    def test_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="0.0, 1.0"):
            ConfidenceScore(value=-0.1, reason="bad")

    def test_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="0.0, 1.0"):
            ConfidenceScore(value=1.001, reason="bad")

    def test_is_frozen(self) -> None:
        cs = _confidence()
        with pytest.raises((AttributeError, TypeError)):
            cs.value = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AgentResult
# ---------------------------------------------------------------------------

class TestAgentResult:
    def _make(self, output: object = None) -> AgentResult:
        return AgentResult(
            agent_id="market-agent",
            agent_type="DATA",
            version="1.0",
            input_summary="SBER 1h 2023",
            output=output or _manifest(),
            evidence=(_evidence(),),
            confidence=_confidence(),
            created_at="2023-01-10T10:00:00",
        )

    def test_construction(self) -> None:
        result = self._make()
        assert result.agent_id == "market-agent"
        assert result.agent_type == "DATA"
        assert result.version == "1.0"

    def test_is_frozen(self) -> None:
        result = self._make()
        with pytest.raises((AttributeError, TypeError)):
            result.agent_id = "mutated"  # type: ignore[misc]

    def test_evidence_is_tuple(self) -> None:
        result = self._make()
        assert isinstance(result.evidence, tuple)
        assert len(result.evidence) == 1
        assert isinstance(result.evidence[0], EvidenceRef)

    def test_confidence_is_confidence_score(self) -> None:
        result = self._make()
        assert isinstance(result.confidence, ConfidenceScore)

    def test_output_carries_manifest(self) -> None:
        manifest = _manifest()
        result = self._make(output=manifest)
        assert isinstance(result.output, DatasetManifest)
        assert result.output.dataset_id == "sber_1h_2023_main"

    def test_agent_types(self) -> None:
        valid_types = {"DATA", "ANALYSIS", "RESEARCH", "KNOWLEDGE", "CHIEF_SCIENTIST"}
        for t in valid_types:
            r = AgentResult(
                agent_id="x",
                agent_type=t,
                version="1.0",
                input_summary="",
                output=None,
                evidence=(),
                confidence=_confidence(),
                created_at="2023-01-10T10:00:00",
            )
            assert r.agent_type == t

    def test_empty_evidence_tuple(self) -> None:
        result = AgentResult(
            agent_id="x",
            agent_type="DATA",
            version="1.0",
            input_summary="",
            output=None,
            evidence=(),
            confidence=_confidence(),
            created_at="2023-01-10T10:00:00",
        )
        assert result.evidence == ()


# ---------------------------------------------------------------------------
# MarketSnapshot
# ---------------------------------------------------------------------------

class TestMarketSnapshot:
    def test_construction(self) -> None:
        snap = MarketSnapshot(
            ticker="GAZP",
            timeframe="4h",
            bar_count=635,
            date_from="2023-01-10",
            date_to="2023-12-29",
            session_filter="main",
        )
        assert snap.ticker == "GAZP"
        assert snap.bar_count == 635

    def test_is_frozen(self) -> None:
        snap = MarketSnapshot(
            ticker="GAZP", timeframe="4h", bar_count=635,
            date_from="2023-01-10", date_to="2023-12-29", session_filter="main",
        )
        with pytest.raises((AttributeError, TypeError)):
            snap.ticker = "SBER"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DatasetManifest
# ---------------------------------------------------------------------------

class TestDatasetManifest:
    def test_construction(self) -> None:
        m = _manifest()
        assert m.dataset_id == "sber_1h_2023_main"
        assert m.ticker == "SBER"
        assert m.timeframe == "1h"
        assert m.bar_count == 2540
        assert m.session_filter == "main"
        assert m.source == "MOEX ISS API"

    def test_is_frozen(self) -> None:
        m = _manifest()
        with pytest.raises((AttributeError, TypeError)):
            m.ticker = "GAZP"  # type: ignore[misc]

    def test_all_required_fields_present(self) -> None:
        m = _manifest()
        required = {
            "dataset_id", "dataset_path", "ohlcv_path", "metadata_path",
            "ticker", "timeframe", "bar_count", "date_from", "date_to",
            "session_filter", "source",
        }
        actual = set(m.__dataclass_fields__.keys())
        assert required == actual

    def test_paths_are_strings(self) -> None:
        m = _manifest()
        assert isinstance(m.dataset_path, str)
        assert isinstance(m.ohlcv_path, str)
        assert isinstance(m.metadata_path, str)


# ---------------------------------------------------------------------------
# MacroSeries
# ---------------------------------------------------------------------------

def _macro_series(symbol: str = "IMOEX") -> MacroSeries:
    return MacroSeries(
        symbol=symbol,
        timeframe="1d",
        date_from="2023-01-03",
        date_to="2023-12-29",
        value_count=247,
        path="/data/context/macro/2023/IMOEX_1d.csv",
    )


class TestMacroSeries:
    def test_construction(self) -> None:
        s = _macro_series()
        assert s.symbol == "IMOEX"
        assert s.timeframe == "1d"
        assert s.value_count == 247
        assert s.path.endswith("IMOEX_1d.csv")

    def test_is_frozen(self) -> None:
        s = _macro_series()
        with pytest.raises((AttributeError, TypeError)):
            s.symbol = "RGBI"  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        s = _macro_series()
        assert hash(s) is not None
        assert {s, s} == {s}

    def test_equality(self) -> None:
        a = _macro_series("IMOEX")
        b = _macro_series("IMOEX")
        assert a == b

    def test_inequality_on_different_symbol(self) -> None:
        a = _macro_series("IMOEX")
        b = _macro_series("RGBI")
        assert a != b

    def test_all_required_fields(self) -> None:
        s = _macro_series()
        required = {"symbol", "timeframe", "date_from", "date_to", "value_count", "path"}
        assert required == set(s.__dataclass_fields__.keys())


# ---------------------------------------------------------------------------
# MacroSnapshot
# ---------------------------------------------------------------------------

def _macro_snapshot() -> MacroSnapshot:
    return MacroSnapshot(
        snapshot_id="macro_2023_1d",
        period="2023",
        observations=(
            _macro_series("IMOEX"),
            _macro_series("USDRUB"),
            _macro_series("RGBI"),
        ),
        source_refs=(_evidence(),),
        missing_values=(),
        confidence=_confidence(1.0),
    )


class TestMacroSnapshot:
    def test_construction(self) -> None:
        snap = _macro_snapshot()
        assert snap.snapshot_id == "macro_2023_1d"
        assert snap.period == "2023"
        assert len(snap.observations) == 3

    def test_is_frozen(self) -> None:
        snap = _macro_snapshot()
        with pytest.raises((AttributeError, TypeError)):
            snap.period = "2024"  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        snap = _macro_snapshot()
        assert hash(snap) is not None

    def test_observations_are_tuple(self) -> None:
        snap = _macro_snapshot()
        assert isinstance(snap.observations, tuple)
        for obs in snap.observations:
            assert isinstance(obs, MacroSeries)

    def test_source_refs_are_tuple(self) -> None:
        snap = _macro_snapshot()
        assert isinstance(snap.source_refs, tuple)

    def test_missing_values_is_tuple(self) -> None:
        snap = _macro_snapshot()
        assert isinstance(snap.missing_values, tuple)

    def test_missing_values_as_dict(self) -> None:
        snap = MacroSnapshot(
            snapshot_id="macro_2023_1d",
            period="2023",
            observations=(_macro_series("IMOEX"),),
            source_refs=(),
            missing_values=(("RGBI", 0), ("USDRUB", 0)),
            confidence=_confidence(0.33),
        )
        as_dict = dict(snap.missing_values)
        assert as_dict == {"RGBI": 0, "USDRUB": 0}

    def test_empty_observations(self) -> None:
        snap = MacroSnapshot(
            snapshot_id="macro_2023_1d",
            period="2023",
            observations=(),
            source_refs=(),
            missing_values=(("IMOEX", 0), ("USDRUB", 0), ("RGBI", 0)),
            confidence=_confidence(0.0),
        )
        assert snap.observations == ()
        assert len(snap.missing_values) == 3

    def test_confidence_reflects_completeness(self) -> None:
        full = _macro_snapshot()
        partial = MacroSnapshot(
            snapshot_id="macro_2023_1d",
            period="2023",
            observations=(_macro_series("IMOEX"),),
            source_refs=(),
            missing_values=(("RGBI", 0),),
            confidence=_confidence(0.5),
        )
        assert full.confidence.value > partial.confidence.value


# ---------------------------------------------------------------------------
# CorrelationPair
# ---------------------------------------------------------------------------

def _pair(
    symbol: str = "IMOEX",
    lag: int = 0,
    correlation: float = 0.75,
    n: int = 240,
) -> CorrelationPair:
    return CorrelationPair(
        instrument="SBER",
        macro_symbol=symbol,
        lag=lag,
        correlation=correlation,
        observation_count=n,
    )


class TestCorrelationPair:
    def test_construction(self) -> None:
        p = _pair()
        assert p.instrument == "SBER"
        assert p.macro_symbol == "IMOEX"
        assert p.lag == 0
        assert p.correlation == 0.75
        assert p.observation_count == 240

    def test_is_frozen(self) -> None:
        p = _pair()
        with pytest.raises((AttributeError, TypeError)):
            p.correlation = 0.5  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        p = _pair()
        assert hash(p) is not None
        assert {p, p} == {p}

    def test_equality(self) -> None:
        assert _pair() == _pair()

    def test_inequality_on_lag(self) -> None:
        assert _pair(lag=0) != _pair(lag=1)

    def test_nan_correlation_accepted(self) -> None:
        p = CorrelationPair(
            instrument="SBER",
            macro_symbol="IMOEX",
            lag=5,
            correlation=math.nan,
            observation_count=1,
        )
        assert math.isnan(p.correlation)

    def test_lag_positive(self) -> None:
        p = _pair(lag=5)
        assert p.lag == 5

    def test_lag_negative(self) -> None:
        p = _pair(lag=-5)
        assert p.lag == -5

    def test_all_required_fields(self) -> None:
        required = {"instrument", "macro_symbol", "lag", "correlation", "observation_count"}
        assert required == set(_pair().__dataclass_fields__.keys())


# ---------------------------------------------------------------------------
# CorrelationSnapshot
# ---------------------------------------------------------------------------

def _corr_snapshot() -> CorrelationSnapshot:
    return CorrelationSnapshot(
        snapshot_id="corr_SBER_2023",
        instrument="SBER",
        period="2023",
        pairs=(
            _pair("IMOEX", 0, 0.90, 240),
            _pair("IMOEX", 1, 0.88, 239),
            _pair("USDRUB", 0, -0.40, 240),
            _pair("RGBI", 0, 0.15, 238),
        ),
        total_instrument_bars=247,
        aligned_dates=240,
        missing_alignment=7,
        source_refs=(_evidence(),),
        confidence=_confidence(0.97),
    )


class TestCorrelationSnapshot:
    def test_construction(self) -> None:
        snap = _corr_snapshot()
        assert snap.snapshot_id == "corr_SBER_2023"
        assert snap.instrument == "SBER"
        assert snap.period == "2023"
        assert len(snap.pairs) == 4

    def test_is_frozen(self) -> None:
        snap = _corr_snapshot()
        with pytest.raises((AttributeError, TypeError)):
            snap.period = "2024"  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        snap = _corr_snapshot()
        assert hash(snap) is not None

    def test_pairs_is_tuple_of_correlation_pairs(self) -> None:
        snap = _corr_snapshot()
        assert isinstance(snap.pairs, tuple)
        for p in snap.pairs:
            assert isinstance(p, CorrelationPair)

    def test_alignment_invariant(self) -> None:
        snap = _corr_snapshot()
        assert snap.aligned_dates + snap.missing_alignment == snap.total_instrument_bars

    def test_source_refs_is_tuple(self) -> None:
        snap = _corr_snapshot()
        assert isinstance(snap.source_refs, tuple)

    def test_empty_pairs(self) -> None:
        snap = CorrelationSnapshot(
            snapshot_id="corr_SBER_2023",
            instrument="SBER",
            period="2023",
            pairs=(),
            total_instrument_bars=0,
            aligned_dates=0,
            missing_alignment=0,
            source_refs=(),
            confidence=_confidence(0.0),
        )
        assert snap.pairs == ()

    def test_required_fields(self) -> None:
        required = {
            "snapshot_id", "instrument", "period", "pairs",
            "total_instrument_bars", "aligned_dates", "missing_alignment",
            "source_refs", "confidence",
        }
        assert required == set(_corr_snapshot().__dataclass_fields__.keys())


# ---------------------------------------------------------------------------
# RegimeLabel
# ---------------------------------------------------------------------------

class TestRegimeLabel:
    def test_trend_up(self) -> None:
        assert RegimeLabel.TREND_UP == "TREND_UP"

    def test_trend_down(self) -> None:
        assert RegimeLabel.TREND_DOWN == "TREND_DOWN"

    def test_range(self) -> None:
        assert RegimeLabel.RANGE == "RANGE"

    def test_low_vol(self) -> None:
        assert RegimeLabel.LOW_VOL == "LOW_VOL"

    def test_normal_vol(self) -> None:
        assert RegimeLabel.NORMAL_VOL == "NORMAL_VOL"

    def test_high_vol(self) -> None:
        assert RegimeLabel.HIGH_VOL == "HIGH_VOL"

    def test_risk_on(self) -> None:
        assert RegimeLabel.RISK_ON == "RISK_ON"

    def test_risk_off(self) -> None:
        assert RegimeLabel.RISK_OFF == "RISK_OFF"

    def test_neutral(self) -> None:
        assert RegimeLabel.NEUTRAL == "NEUTRAL"

    def test_trend_set_contains_all(self) -> None:
        assert RegimeLabel._TREND == {"TREND_UP", "TREND_DOWN", "RANGE"}

    def test_volatility_set_contains_all(self) -> None:
        assert RegimeLabel._VOLATILITY == {"LOW_VOL", "NORMAL_VOL", "HIGH_VOL"}

    def test_risk_set_contains_all(self) -> None:
        assert RegimeLabel._RISK == {"RISK_ON", "RISK_OFF", "NEUTRAL"}


# ---------------------------------------------------------------------------
# RegimeSegment
# ---------------------------------------------------------------------------

def _regime_segment(
    regime_type: str = "trend",
    label: str = "TREND_UP",
) -> RegimeSegment:
    return RegimeSegment(
        regime_type=regime_type,
        label=label,
        date_from="2023-01-03",
        date_to="2023-01-31",
        confidence=0.75,
        metrics=(("slope_normalized", 0.002), ("sma_position", 0.015)),
        evidence=("slope > threshold and price above SMA",),
    )


class TestRegimeSegment:
    def test_construction(self) -> None:
        s = _regime_segment()
        assert s.regime_type == "trend"
        assert s.label == "TREND_UP"
        assert s.date_from == "2023-01-03"
        assert s.confidence == 0.75

    def test_is_frozen(self) -> None:
        s = _regime_segment()
        with pytest.raises((AttributeError, TypeError)):
            s.label = "RANGE"  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        s = _regime_segment()
        assert hash(s) is not None
        assert {s, s} == {s}

    def test_metrics_is_tuple_of_pairs(self) -> None:
        s = _regime_segment()
        assert isinstance(s.metrics, tuple)
        for pair in s.metrics:
            assert isinstance(pair, tuple)
            assert isinstance(pair[0], str)
            assert isinstance(pair[1], float)

    def test_evidence_is_tuple_of_strings(self) -> None:
        s = _regime_segment()
        assert isinstance(s.evidence, tuple)
        assert all(isinstance(e, str) for e in s.evidence)

    def test_equality(self) -> None:
        assert _regime_segment() == _regime_segment()

    def test_all_regime_types_valid(self) -> None:
        for rt in ("trend", "volatility", "risk"):
            s = RegimeSegment(
                regime_type=rt, label="RANGE", date_from="d1", date_to="d2",
                confidence=0.5, metrics=(), evidence=(),
            )
            assert s.regime_type == rt


# ---------------------------------------------------------------------------
# RegimeSnapshot
# ---------------------------------------------------------------------------

def _regime_snapshot() -> RegimeSnapshot:
    return RegimeSnapshot(
        snapshot_id="regime_SBER_2023",
        instrument="SBER",
        period="2023",
        segments=(
            _regime_segment("trend", "TREND_UP"),
            _regime_segment("volatility", "NORMAL_VOL"),
            _regime_segment("risk", "RISK_ON"),
        ),
        source_refs=(_evidence(),),
        confidence=_confidence(0.72),
    )


class TestRegimeSnapshot:
    def test_construction(self) -> None:
        snap = _regime_snapshot()
        assert snap.snapshot_id == "regime_SBER_2023"
        assert snap.instrument == "SBER"
        assert len(snap.segments) == 3

    def test_is_frozen(self) -> None:
        snap = _regime_snapshot()
        with pytest.raises((AttributeError, TypeError)):
            snap.period = "2024"  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        snap = _regime_snapshot()
        assert hash(snap) is not None

    def test_segments_is_tuple_of_regime_segments(self) -> None:
        snap = _regime_snapshot()
        assert isinstance(snap.segments, tuple)
        for s in snap.segments:
            assert isinstance(s, RegimeSegment)

    def test_source_refs_is_tuple(self) -> None:
        snap = _regime_snapshot()
        assert isinstance(snap.source_refs, tuple)

    def test_empty_segments(self) -> None:
        snap = RegimeSnapshot(
            snapshot_id="regime_SBER_2023",
            instrument="SBER",
            period="2023",
            segments=(),
            source_refs=(),
            confidence=_confidence(0.0),
        )
        assert snap.segments == ()

    def test_required_fields(self) -> None:
        required = {
            "snapshot_id", "instrument", "period", "segments",
            "source_refs", "confidence",
        }
        assert required == set(_regime_snapshot().__dataclass_fields__.keys())
