"""Agent Protocol interfaces for Intelligence Era.

All agents — Data, Analysis, Research, Knowledge, Chief Scientist —
satisfy AgentProtocol. CandleSource is the data-source abstraction
that enables fixture injection in MarketAgent.
"""
from __future__ import annotations

from typing import Any, Protocol


class AgentProtocol(Protocol):
    """Minimum structural contract for every Intelligence Era agent."""

    agent_id: str
    agent_type: str
    version: str

    def run(self, **kwargs: Any) -> "AgentResult":  # noqa: F821
        ...


class CandleSource(Protocol):
    """OHLCV data source abstraction — separates HTTP from agent logic."""

    def fetch(
        self,
        ticker: str,
        timeframe: str,
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        ...


class MacroSource(Protocol):
    """Macro time-series source abstraction — enables fixture injection in MacroAgent.

    Each call returns a list of daily rows for one symbol.
    Row format: {date: str, open: float, high: float, low: float, close: float, volume: int}
    """

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        ...


class RegimeSource(Protocol):
    """Data-loading abstraction for RegimeDetectionAgent.

    Same interface as CorrelationSource — any class with these two methods
    satisfies both protocols structurally (duck typing).
    """

    def load_instrument(self, instrument: str, period: str) -> list[dict]:
        ...

    def load_macro_symbol(self, symbol: str, period: str) -> list[dict]:
        ...


class KnowledgeSource(Protocol):
    """Data-loading abstraction for KnowledgeAgent.

    Reports: dicts with keys hypothesis_id, instrument, period, pass_rate,
             passed, confidence, regime_label (opt), source_ref, features (opt).
    KB entries: dicts with keys entry_id, hypothesis_id, finding, confidence,
                source_ref.
    Both methods return empty lists when no data is available.
    """

    def load_reports(self, campaign_id: str) -> list[dict]:
        ...

    def load_kb_entries(self, campaign_id: str) -> list[dict]:
        ...


class CorrelationSource(Protocol):
    """Data-loading abstraction for CorrelationAgent — enables fixture injection.

    Both methods return daily {date: str, close: float} dicts, already at daily
    granularity. FileCorrelationSource aggregates intraday OHLCV internally;
    FixtureCorrelationSource returns pre-baked data.
    """

    def load_instrument(self, instrument: str, period: str) -> list[dict]:
        ...

    def load_macro_symbol(self, symbol: str, period: str) -> list[dict]:
        ...
