import pandas as pd

import backtest_viewer as bv


def test_monthly_rebalance_does_not_drop_the_month_boundary_return():
    # Regression: portfolio_value() used to compute the new month's units from
    # the previous month's closing value, then re-price at the new month's
    # first price — which always nets back to the same value by construction,
    # silently erasing that one day's actual return at every month boundary.
    dates = pd.date_range("2024-01-01", "2024-02-10", freq="B")
    prices = pd.Series(100.0, index=dates)
    feb_start = pd.Timestamp("2024-02-01")
    prices.loc[prices.index >= feb_start] = 200.0
    df = pd.DataFrame({"X": prices})

    value = bv.portfolio_value(df, {"X": 1.0}, rebalance="monthly")

    assert value[value.index < feb_start].iloc[-1] == 10_000.0
    assert value[value.index >= feb_start].iloc[0] == 20_000.0
