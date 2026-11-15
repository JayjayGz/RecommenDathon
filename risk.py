"""Per-ticker risk measures. Kenny writes the body; this documents the contract agents call."""


def risk_measures(ticker, start=None, end=None, data_dir="alphaforge_starter"):
    """Risk and return profile for a single ticker, in CAD.

    Returns a dict with:
      volatility_pct: annualized standard deviation of daily returns, in percent
          (daily return std dev * sqrt(252) * 100).
      max_drawdown_pct: largest peak-to-trough decline in price over the period,
          in percent, as a negative number (e.g. -54.2 means the price fell
          54.2% from its peak before recovering or the window ending).
      annual_growth_pct: annualized compound growth rate (CAGR) over the period,
          in percent, from the first to the last adjusted close in the window.
      years_of_data: number of years of price history actually used
          (trading days in the window / 252).
      first_date: ISO date (YYYY-MM-DD) of the first trading day used.
      last_date: ISO date (YYYY-MM-DD) of the last trading day used.

    Uses adj_close (splits already applied; never reapplied). USD-listed tickers
    are converted to CAD with the Bank of Canada USD/CAD rate on or before each
    date (fx_usdcad_daily.csv, merge_asof direction="backward"). Default period,
    when start/end are not given, is the full range available in data_dir.
    """
    raise NotImplementedError
