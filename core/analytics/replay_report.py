import numpy as np
from core.analytics.metrics import profit_factor, max_drawdown

class ReplayReport:
    def build(self, positions, portfolio, initial_cash=1_000_000):
        if positions.empty or portfolio.empty:
            return {}
        dr = portfolio["equity"].pct_change().dropna()
        sharpe = np.sqrt(252) * dr.mean() / dr.std() if dr.std() != 0 else 0
        downside = dr[dr < 0]
        sortino = np.sqrt(252) * dr.mean() / downside.std() if downside.std() != 0 else 0
        return {
            "total_trades": int(len(positions)),
            "wins": int((positions["pnl"] > 0).sum()),
            "losses": int((positions["pnl"] <= 0).sum()),
            "win_rate": float((positions["pnl"] > 0).mean()),
            "profit_factor": float(profit_factor(positions["pnl"])),
            "expectancy": float(positions["pnl"].mean()),
            "total_return": float((portfolio["equity"].iloc[-1] - initial_cash) / initial_cash),
            "max_drawdown": float(max_drawdown(portfolio["equity"])),
            "sharpe": float(sharpe),
            "sortino": float(sortino),
        }
