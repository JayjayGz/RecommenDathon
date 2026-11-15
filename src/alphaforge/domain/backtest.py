"""Pure historical accounting and metrics; no file or UI access."""
import numpy as np
import pandas as pd

TRADING_DAYS = 252

def portfolio_value(df, weights, rebalance="monthly", start_value=10_000.0):
    """Long-only value path; monthly rebalances at the first observed close.

    Existing units earn the return into that close before rebalancing. This
    preserves the price change from the previous month's last observation.
    """
    if rebalance not in {"monthly", "none"}:
        raise ValueError("rebalance must be 'monthly' or 'none'")
    if (df.empty or not isinstance(df.index, pd.DatetimeIndex)
            or not df.index.is_monotonic_increasing or not df.index.is_unique
            or not df.columns.is_unique):
        raise ValueError("Prices need unique columns and chronological, unique dates")
    if not np.isfinite(df.to_numpy(dtype=float)).all() or (df <= 0).any().any():
        raise ValueError("Prices must be finite and positive")
    if set(weights) != set(df.columns):
        raise ValueError("Weights must match the price columns")
    w = pd.Series(weights, dtype=float)[df.columns]
    if not np.isfinite(w).all() or (w < 0).any():
        raise ValueError("Weights must be finite and nonnegative")
    if abs(w.sum() - 1) > 1e-6:
        raise ValueError(f"Weights sum to {w.sum():.4f}, not 1")
    if not np.isfinite(start_value) or start_value <= 0:
        raise ValueError("start_value must be finite and positive")
    units = start_value * w / df.iloc[0]
    if rebalance == "none":
        return (df * units).sum(axis=1)

    values = []
    for _, month in df.groupby(df.index.to_period("M")):
        current = (units * month.iloc[0]).sum()
        units = current * w / month.iloc[0]
        path = (month * units).sum(axis=1)
        values.append(path)
    return pd.concat(values)


def metrics(value):
    if len(value) < 3 or not np.isfinite(value).all() or (value <= 0).any():
        raise ValueError("At least three finite, positive portfolio observations are required")
    r = value.pct_change().dropna()
    years = len(r) / TRADING_DAYS
    drawdown = value / value.cummax() - 1
    return {
        "annual_growth_pct": round(((value.iloc[-1] / value.iloc[0]) ** (1 / years) - 1) * 100, 1),
        "volatility_pct": round(r.std() * np.sqrt(TRADING_DAYS) * 100, 1),
        "max_drawdown_pct": round(drawdown.min() * 100, 1),
        "worst_drawdown_date": drawdown.idxmin().date().isoformat(),
        "end_value": round(value.iloc[-1], 0),
    }


