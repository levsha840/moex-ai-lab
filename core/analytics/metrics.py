import numpy as np


def profit_factor(series):
    wins = series[series > 0]
    losses = series[series <= 0]

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    if gross_loss == 0:
        return np.inf

    return gross_profit / gross_loss


def max_drawdown(equity_series):
    peak = equity_series.cummax()
    drawdown = (equity_series - peak) / peak
    return drawdown.min()
