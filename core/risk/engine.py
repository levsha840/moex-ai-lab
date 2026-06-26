"""Risk Engine — pre-trade risk evaluation against configurable limits."""

from __future__ import annotations

from core.common import OrderSide
from core.risk.models import (
    RiskCheckRequest,
    RiskDecision,
    RiskLimits,
    RiskReason,
)


class RiskEngine:
    """Evaluates a trade request against risk limits and returns ALLOW or REJECT.

    The engine is stateless and deterministic: the same request with the same
    limits always produces the same decision. It does not access the database
    or any external state.
    """

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def check(self, request: RiskCheckRequest) -> RiskDecision:
        """Run all configured risk checks and return a single decision."""

        reasons: list[RiskReason] = []
        trade_value = request.quantity * request.price

        if not self.limits.allow_short and request.side == OrderSide.SELL:
            if request.current_position_value == 0:
                reasons.append(RiskReason.SHORT_NOT_ALLOWED)

        if trade_value > self.limits.max_trade_value:
            reasons.append(RiskReason.MAX_TRADE_VALUE_EXCEEDED)

        if request.side == OrderSide.BUY:
            new_position_value = request.current_position_value + trade_value

            if new_position_value > self.limits.max_position_value:
                reasons.append(RiskReason.MAX_POSITION_VALUE_EXCEEDED)

            if request.portfolio_equity > 0:
                if new_position_value / request.portfolio_equity > self.limits.max_position_pct:
                    reasons.append(RiskReason.MAX_POSITION_PCT_EXCEEDED)

            if request.current_position_value == 0:
                if request.open_positions_count >= self.limits.max_open_positions:
                    reasons.append(RiskReason.MAX_OPEN_POSITIONS_EXCEEDED)

        if reasons:
            return RiskDecision.reject(*reasons)
        return RiskDecision.allow()
