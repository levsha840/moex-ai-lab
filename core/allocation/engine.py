from __future__ import annotations

from core.allocation.models import (
    AllocationConfig,
    AllocationDecision,
    AllocationDecisionType,
    AllocationReason,
    AllocationRequest,
)

_TOL = 1e-9


class PortfolioAllocationEngine:
    def __init__(self, config: AllocationConfig | None = None) -> None:
        self.config = config or AllocationConfig()

    def allocate(self, request: AllocationRequest) -> AllocationDecision:
        if request.price <= 0 or request.requested_quantity <= 0 or request.portfolio_value <= 0:
            return AllocationDecision(
                decision=AllocationDecisionType.REJECT,
                approved_quantity=0.0,
                reasons=(AllocationReason.INVALID_REQUEST,),
            )

        requested_value = request.price * request.requested_quantity
        available_cash = request.cash - request.portfolio_value * self.config.cash_buffer

        if available_cash <= 0:
            return AllocationDecision(
                decision=AllocationDecisionType.REJECT,
                approved_quantity=0.0,
                reasons=(AllocationReason.CASH_BUFFER_REQUIRED,),
            )

        max_by_cash = available_cash
        max_by_position = (
            request.portfolio_value * self.config.max_position_pct
            - request.current_position_value
        )
        max_by_strategy = (
            request.portfolio_value * self.config.max_strategy_pct
            - request.strategy_exposure
        )
        max_by_correlated = (
            request.portfolio_value * self.config.max_correlated_pct
            - request.correlated_exposure
        )

        approved_value = min(
            requested_value,
            max_by_cash,
            max_by_position,
            max_by_strategy,
            max_by_correlated,
        )

        if approved_value <= 0:
            reasons: list[AllocationReason] = []
            if max_by_cash <= 0:
                reasons.append(AllocationReason.INSUFFICIENT_CASH)
            if max_by_position <= 0:
                reasons.append(AllocationReason.MAX_POSITION_PCT_EXCEEDED)
            if max_by_strategy <= 0:
                reasons.append(AllocationReason.MAX_STRATEGY_PCT_EXCEEDED)
            if max_by_correlated <= 0:
                reasons.append(AllocationReason.MAX_CORRELATED_PCT_EXCEEDED)
            if not reasons:
                reasons.append(AllocationReason.INSUFFICIENT_CASH)
            return AllocationDecision(
                decision=AllocationDecisionType.REJECT,
                approved_quantity=0.0,
                reasons=tuple(reasons),
            )

        if approved_value >= requested_value * (1 - self.config.rebalance_threshold):
            return AllocationDecision(
                decision=AllocationDecisionType.ALLOCATE,
                approved_quantity=request.requested_quantity,
                reasons=(AllocationReason.APPROVED,),
            )

        # REDUCE — collect all binding limits
        binding: list[AllocationReason] = []
        if max_by_cash - approved_value <= _TOL:
            binding.append(AllocationReason.INSUFFICIENT_CASH)
        if max_by_position - approved_value <= _TOL:
            binding.append(AllocationReason.MAX_POSITION_PCT_EXCEEDED)
        if max_by_strategy - approved_value <= _TOL:
            binding.append(AllocationReason.MAX_STRATEGY_PCT_EXCEEDED)
        if max_by_correlated - approved_value <= _TOL:
            binding.append(AllocationReason.MAX_CORRELATED_PCT_EXCEEDED)
        if not binding:
            binding.append(AllocationReason.INSUFFICIENT_CASH)

        return AllocationDecision(
            decision=AllocationDecisionType.REDUCE,
            approved_quantity=approved_value / request.price,
            reasons=tuple(binding),
        )
