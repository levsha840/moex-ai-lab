from core.portfolio.portfolio import Portfolio
from core.portfolio.position import Position
from core.risk.risk_manager import RiskManager
from core.execution.replay_execution_engine import ReplayExecutionEngine

def main():
    p = Portfolio(1_000_000); r = RiskManager(max_open_positions=1); e = ReplayExecutionEngine()
    tv = e.estimate_trade_value(p.cash)
    allowed, reason = r.can_open_position(p, "S1", "AAA", tv)
    assert allowed, reason
    p.add_position(Position("S1","AAA",None,100,10,1))
    allowed, reason = r.can_open_position(p, "S2", "BBB", tv)
    assert not allowed and reason == "MAX_OPEN_POSITIONS_REACHED"
    print("Core portfolio/risk OK")

if __name__ == "__main__":
    main()
