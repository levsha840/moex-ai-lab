from __future__ import annotations

from dataclasses import dataclass

from core.common import OrderSide


@dataclass(frozen=True)
class ExecutionCostConfig:
    commission_rate: float = 0.0005
    minimum_commission: float = 0.0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0


@dataclass(frozen=True)
class ExecutionRequest:
    ticker: str
    side: OrderSide
    price: float
    quantity: float


@dataclass(frozen=True)
class ExecutionResult:
    gross_value: float
    commission: float
    spread_cost: float
    slippage_cost: float
    total_cost: float
    effective_price: float
