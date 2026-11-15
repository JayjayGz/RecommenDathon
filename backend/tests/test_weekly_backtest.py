"""Hand-computable weekly metrics and timing; no real-market claims."""
import numpy as np
import pandas as pd
import pytest

from alphaforge.domain.backtest import metrics, portfolio_value
from alphaforge.domain.market_data import observation_convention, price_table


def test_weekly_annualization_matches_known_returns():
    returns = np.array([.01, -.02, .03, -.01])
    value = pd.Series(100 * np.r_[1., np.cumprod(1 + returns)],
                      index=pd.date_range("2025-01-03", periods=5, freq="W-FRI"))
    result = metrics(value)
    assert result["volatility_pct"] == round(np.std(returns, ddof=1) * np.sqrt(52) * 100, 1)
    assert result["annual_growth_pct"] == round(((value.iloc[-1] / 100) ** (52 / 4) - 1) * 100, 1)
    assert result["annualization_observations"] == 52
    assert result["observation_frequency"] == "weekly"


@pytest.mark.parametrize("freq,annualization", [("B", 252), ("W-FRI", 52)])
def test_flat_control_and_daily_compatibility(freq, annualization):
    dates = pd.date_range("2025-01-03", periods=10, freq=freq)
    result = metrics(pd.Series(100., index=dates))
    assert result["volatility_pct"] == result["annual_growth_pct"] == result["max_drawdown_pct"] == 0
    assert result["annualization_observations"] == annualization


def test_weekly_month_boundary_preserves_gain_before_rebalance():
    prices = pd.DataFrame({"A": [100., 200., 400., 400.], "B": [100., 100., 100., 200.]},
                          index=pd.to_datetime(["2025-01-24", "2025-01-31", "2025-02-07", "2025-02-14"]))
    assert portfolio_value(prices, {"A": .5, "B": .5}).tolist() == pytest.approx(
        [10000, 15000, 25000, 37500])


@pytest.mark.parametrize("dates", [
    pd.date_range("2025-01-03", periods=4, freq="28D"),
    pd.to_datetime(["2025-01-03", "2025-01-04", "2025-01-10", "2025-01-17"]),
])
def test_sparse_and_mixed_cadence_fail(dates):
    with pytest.raises(ValueError, match="frequency"):
        observation_convention(dates)


def test_common_dates_cannot_silently_turn_weekly_into_biweekly():
    dates = pd.date_range("2025-01-03", periods=7, freq="W-FRI")
    shifted = [d + pd.Timedelta(days=i % 2) for i, d in enumerate(dates)]
    rows = [("A", d) for d in dates] + [("B", d) for d in shifted]
    prices = pd.DataFrame(rows, columns=["ticker", "date"]).assign(adj_close=100., currency="CAD")
    # Both assets are weekly, but only alternating weeks have matching dates.
    with pytest.raises(ValueError, match="frequency"):
        price_table(prices, pd.DataFrame(), ["A", "B"], dates[0], dates[-1])
