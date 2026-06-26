import pytest

from core.costs import ExecutionCostConfig, ExecutionCostEngine, ExecutionRequest


def _req(side="BUY", price=100.0, quantity=10.0, ticker="SBER") -> ExecutionRequest:
    return ExecutionRequest(ticker=ticker, side=side, price=price, quantity=quantity)


@pytest.fixture
def zero_config() -> ExecutionCostConfig:
    return ExecutionCostConfig(
        commission_rate=0.0,
        minimum_commission=0.0,
        spread_bps=0.0,
        slippage_bps=0.0,
    )


def test_zero_costs(zero_config):
    engine = ExecutionCostEngine(zero_config)
    result = engine.calculate(_req())
    assert result.gross_value == pytest.approx(1000.0)
    assert result.commission == pytest.approx(0.0)
    assert result.spread_cost == pytest.approx(0.0)
    assert result.slippage_cost == pytest.approx(0.0)
    assert result.total_cost == pytest.approx(0.0)
    assert result.effective_price == pytest.approx(100.0)


def test_default_commission():
    # commission_rate=0.0005, all others zero
    engine = ExecutionCostEngine(ExecutionCostConfig())
    result = engine.calculate(_req(quantity=100.0))
    # gross=10_000, commission=10_000*0.0005=5.0
    assert result.gross_value == pytest.approx(10_000.0)
    assert result.commission == pytest.approx(5.0)
    assert result.total_cost == pytest.approx(5.0)
    assert result.effective_price == pytest.approx(100.05)


def test_minimum_commission_applies():
    config = ExecutionCostConfig(commission_rate=0.0005, minimum_commission=10.0)
    engine = ExecutionCostEngine(config)
    # gross=10*1=10, commission=max(0.005, 10.0)=10.0
    result = engine.calculate(_req(price=10.0, quantity=1.0))
    assert result.commission == pytest.approx(10.0)
    assert result.total_cost == pytest.approx(10.0)


def test_spread_only():
    config = ExecutionCostConfig(commission_rate=0.0, spread_bps=10.0)
    engine = ExecutionCostEngine(config)
    # gross=1000, spread=1000*10/10_000=1.0
    result = engine.calculate(_req())
    assert result.spread_cost == pytest.approx(1.0)
    assert result.commission == pytest.approx(0.0)
    assert result.slippage_cost == pytest.approx(0.0)
    assert result.total_cost == pytest.approx(1.0)
    assert result.effective_price == pytest.approx(100.1)


def test_slippage_only():
    config = ExecutionCostConfig(commission_rate=0.0, slippage_bps=5.0)
    engine = ExecutionCostEngine(config)
    # gross=1000, slippage=1000*5/10_000=0.5
    result = engine.calculate(_req())
    assert result.slippage_cost == pytest.approx(0.5)
    assert result.commission == pytest.approx(0.0)
    assert result.spread_cost == pytest.approx(0.0)
    assert result.total_cost == pytest.approx(0.5)
    assert result.effective_price == pytest.approx(100.05)


def test_combined_costs_buy():
    config = ExecutionCostConfig(commission_rate=0.0005, spread_bps=10.0, slippage_bps=5.0)
    engine = ExecutionCostEngine(config)
    # gross=10_000, commission=5.0, spread=10.0, slippage=5.0, total=20.0
    result = engine.calculate(_req(quantity=100.0))
    assert result.commission == pytest.approx(5.0)
    assert result.spread_cost == pytest.approx(10.0)
    assert result.slippage_cost == pytest.approx(5.0)
    assert result.total_cost == pytest.approx(20.0)
    assert result.effective_price == pytest.approx(100.2)  # (10000+20)/100


def test_combined_costs_sell():
    config = ExecutionCostConfig(commission_rate=0.0005, spread_bps=10.0, slippage_bps=5.0)
    engine = ExecutionCostEngine(config)
    # same costs, but effective_price = (gross - total_cost)/qty
    result = engine.calculate(_req(side="SELL", quantity=100.0))
    assert result.total_cost == pytest.approx(20.0)
    assert result.effective_price == pytest.approx(99.8)  # (10000-20)/100


def test_buy_effective_price_higher_than_market():
    engine = ExecutionCostEngine()
    result = engine.calculate(_req(side="BUY"))
    assert result.effective_price > 100.0


def test_sell_effective_price_lower_than_market():
    engine = ExecutionCostEngine()
    result = engine.calculate(_req(side="SELL"))
    assert result.effective_price < 100.0


def test_invalid_price_rejected():
    engine = ExecutionCostEngine()
    with pytest.raises(ValueError, match="price"):
        engine.calculate(_req(price=0.0))


def test_negative_price_rejected():
    engine = ExecutionCostEngine()
    with pytest.raises(ValueError):
        engine.calculate(_req(price=-50.0))


def test_invalid_quantity_rejected():
    engine = ExecutionCostEngine()
    with pytest.raises(ValueError, match="quantity"):
        engine.calculate(_req(quantity=0.0))


def test_invalid_side_rejected():
    engine = ExecutionCostEngine()
    with pytest.raises(ValueError, match="side"):
        engine.calculate(_req(side="HOLD"))


def test_deterministic_same_input_same_output():
    engine = ExecutionCostEngine(ExecutionCostConfig(commission_rate=0.0005, spread_bps=10.0))
    req = _req(quantity=50.0)
    result_a = engine.calculate(req)
    result_b = engine.calculate(req)
    assert result_a == result_b


def test_large_order_calculation():
    config = ExecutionCostConfig(commission_rate=0.0005, spread_bps=5.0, slippage_bps=3.0)
    engine = ExecutionCostEngine(config)
    # gross=250*1000=250_000
    result = engine.calculate(_req(price=250.0, quantity=1000.0))
    assert result.gross_value == pytest.approx(250_000.0)
    assert result.commission == pytest.approx(125.0)    # 250_000*0.0005
    assert result.spread_cost == pytest.approx(125.0)   # 250_000*5/10_000
    assert result.slippage_cost == pytest.approx(75.0)  # 250_000*3/10_000
    assert result.total_cost == pytest.approx(325.0)
    assert result.effective_price == pytest.approx(250.325)  # (250_000+325)/1000
