import numpy as np

def profit_factor(series):
    wins = series[series > 0]
    losses = series[series <= 0]
    gp = wins.sum()
    gl = abs(losses.sum())
    return np.inf if gl == 0 else gp / gl

def max_drawdown(equity_series):
    peak = equity_series.cummax()
    return ((equity_series - peak) / peak).min()

def win_rate(series):
    return 0 if len(series) == 0 else (series > 0).mean()

def expectancy(series):
    return 0 if len(series) == 0 else series.mean()
