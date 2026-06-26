import pytest

from core.allocation import (
    AllocationConfig,
    AllocationDecisionType,
    AllocationReason,
    AllocationRequest,
    PortfolioAllocationEngine,
)


def _request(**kwargs) -> AllocationRequest:
    defaults = dict(
        ticker="SBER",
        strategy_name="test_strategy",
        price=100.0,
        requested_quantity=10.0,
        cash=50_000.0,
        portfolio_value=100_000.0,
        current_position_value=0.0,
        strategy_exposure=0.0,
        correlated_exposure=0.0,
    )
    defaults.update(kwargs)
    return AllocationRequest(**defaults)


@pytest.fixture
def engine() -> PortfolioAllocationEngine:
    return PortfolioAllocationEngine()


def test_full_allocation_approved(engine):
    # requested_value=1000, available_cash=45000, max_position=10000 — all clear
    result = engine.allocate(_request())
    assert result.decision == AllocationDecisionType.ALLOCATE
    assert result.approved_quantity == 10.0
    assert AllocationReason.APPROVED in result.reasons


def test_invalid_price_rejected(engine):
    result = engine.allocate(_request(price=0.0))
    assert result.decision == AllocationDecisionType.REJECT
    assert AllocationReason.INVALID_REQUEST in result.reasons
    assert result.approved_quantity == 0.0


def test_invalid_quantity_rejected(engine):
    result = engine.allocate(_request(requested_quantity=0.0))
    assert result.decision == AllocationDecisionType.REJECT
    assert AllocationReason.INVALID_REQUEST in result.reasons


def test_invalid_portfolio_value_rejected(engine):
    result = engine.allocate(_request(portfolio_value=0.0))
    assert result.decision == AllocationDecisionType.REJECT
    assert AllocationReason.INVALID_REQUEST in result.reasons


def test_cash_buffer_reject(engine):
    # cash=4000 < buffer=5000 (5% of 100_000)
    result = engine.allocate(_request(cash=4_000.0))
    assert result.decision == AllocationDecisionType.REJECT
    assert AllocationReason.CASH_BUFFER_REQUIRED in result.reasons
    assert result.approved_quantity == 0.0


def test_insufficient_cash_reduce(engine):
    # available_cash=7000-5000=2000; requested=50*100=5000
    result = engine.allocate(_request(cash=7_000.0, requested_quantity=50.0))
    assert result.decision == AllocationDecisionType.REDUCE
    assert AllocationReason.INSUFFICIENT_CASH in result.reasons
    assert pytest.approx(result.approved_quantity) == 20.0  # 2000/100


def test_max_position_pct_reduce(engine):
    # max_position=10% of 100_000=10_000, current=5_000, remaining=5_000
    # requested=200*100=20_000 > 5_000
    result = engine.allocate(
        _request(requested_quantity=200.0, current_position_value=5_000.0)
    )
    assert result.decision == AllocationDecisionType.REDUCE
    assert AllocationReason.MAX_POSITION_PCT_EXCEEDED in result.reasons
    assert pytest.approx(result.approved_quantity) == 50.0  # 5000/100


def test_max_strategy_pct_reduce(engine):
    # max_strategy=30% of 100_000=30_000, exposure=25_000, remaining=5_000
    # requested=200*100=20_000 — limited by strategy to 5_000
    result = engine.allocate(
        _request(requested_quantity=200.0, strategy_exposure=25_000.0)
    )
    assert result.decision == AllocationDecisionType.REDUCE
    assert AllocationReason.MAX_STRATEGY_PCT_EXCEEDED in result.reasons
    assert pytest.approx(result.approved_quantity) == 50.0  # 5000/100


def test_max_correlated_pct_reduce(engine):
    # max_correlated=30% of 100_000=30_000, exposure=25_000, remaining=5_000
    result = engine.allocate(
        _request(requested_quantity=200.0, correlated_exposure=25_000.0)
    )
    assert result.decision == AllocationDecisionType.REDUCE
    assert AllocationReason.MAX_CORRELATED_PCT_EXCEEDED in result.reasons
    assert pytest.approx(result.approved_quantity) == 50.0


def test_zero_remaining_position_capacity_reject(engine):
    # current_position_value already at 100% of max_position_pct cap
    result = engine.allocate(
        _request(requested_quantity=10.0, current_position_value=10_000.0)
    )
    assert result.decision == AllocationDecisionType.REJECT
    assert AllocationReason.MAX_POSITION_PCT_EXCEEDED in result.reasons
    assert result.approved_quantity == 0.0


def test_reduction_respects_rebalance_threshold(engine):
    # available_cash = 5990 - 5000 = 990; requested = 10*100 = 1000
    # approved_value = 990; threshold = 2%: 990 >= 1000*(1-0.02)=980 → ALLOCATE
    result = engine.allocate(_request(cash=5_990.0, requested_quantity=10.0))
    assert result.decision == AllocationDecisionType.ALLOCATE
    assert result.approved_quantity == 10.0
    assert AllocationReason.APPROVED in result.reasons


def test_deterministic_same_input_same_output(engine):
    req = _request(requested_quantity=50.0, cash=7_000.0)
    result_a = engine.allocate(req)
    result_b = engine.allocate(req)
    assert result_a.decision == result_b.decision
    assert result_a.approved_quantity == result_b.approved_quantity
    assert result_a.reasons == result_b.reasons


def test_custom_config_applied():
    config = AllocationConfig(max_position_pct=0.05, cash_buffer=0.0)
    engine = PortfolioAllocationEngine(config=config)
    # max_position=5% of 100_000=5_000; requested=100*100=10_000
    result = engine.allocate(_request(requested_quantity=100.0))
    assert result.decision == AllocationDecisionType.REDUCE
    assert AllocationReason.MAX_POSITION_PCT_EXCEEDED in result.reasons
    assert pytest.approx(result.approved_quantity) == 50.0  # 5000/100


def test_negative_price_rejected(engine):
    result = engine.allocate(_request(price=-10.0))
    assert result.decision == AllocationDecisionType.REJECT
    assert AllocationReason.INVALID_REQUEST in result.reasons
