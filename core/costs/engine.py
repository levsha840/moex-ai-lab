from __future__ import annotations

from core.common import OrderSide
from core.costs.models import ExecutionCostConfig, ExecutionRequest, ExecutionResult


class ExecutionCostEngine:
    def __init__(self, config: ExecutionCostConfig | None = None) -> None:
        self.config = config or ExecutionCostConfig()

    def calculate(self, request: ExecutionRequest) -> ExecutionResult:
        if request.price <= 0:
            raise ValueError(f"price must be positive, got {request.price}")
        if request.quantity <= 0:
            raise ValueError(f"quantity must be positive, got {request.quantity}")
        if isinstance(request.side, OrderSide):
            side = request.side
        else:
            try:
                side = OrderSide(str(request.side).upper())
            except ValueError:
                raise ValueError(f"side must be BUY or SELL, got {request.side!r}")

        gross = request.price * request.quantity

        commission = max(
            gross * self.config.commission_rate,
            self.config.minimum_commission,
        )
        spread_cost = gross * self.config.spread_bps / 10_000
        slippage_cost = gross * self.config.slippage_bps / 10_000
        total_cost = commission + spread_cost + slippage_cost

        if side == OrderSide.BUY:
            effective_price = (gross + total_cost) / request.quantity
        else:
            effective_price = (gross - total_cost) / request.quantity

        return ExecutionResult(
            gross_value=gross,
            commission=commission,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            total_cost=total_cost,
            effective_price=effective_price,
        )
