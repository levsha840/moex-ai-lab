"""Trading bridge layer: Research Service -> Paper Trading -> T-Invest Sandbox."""

from trading.models import (
    ExecutionReport,
    PaperOrderRecord,
    PaperPortfolio,
    PositionSizingRule,
    RiskLimit,
    SizingMethod,
    StrategyCandidateStatus,
    StrategyCandidate,
    TradeDirection,
    TradeSignal,
    TradeSignalStatus,
)
from trading.engine import ApprovedCandidatePaperEngine
from trading.sandbox_adapter import TInvestSandboxAdapter

# Re-export core paper domain objects for consumers of this package
from core.paper.models import PaperOrder, PaperPosition, PaperPortfolioSnapshot

__all__ = [
    "StrategyCandidate",
    "StrategyCandidateStatus",
    "TradeSignal",
    "TradeDirection",
    "TradeSignalStatus",
    "PositionSizingRule",
    "SizingMethod",
    "RiskLimit",
    "PaperOrderRecord",
    "PaperPortfolio",
    "ExecutionReport",
    "PaperOrder",
    "PaperPosition",
    "PaperPortfolioSnapshot",
    "ApprovedCandidatePaperEngine",
    "TInvestSandboxAdapter",
]
