"""Pure currency conversion and common-calendar preparation."""
import pandas as pd


def observation_convention(dates):
    """Infer supported cadence from dates, never from the input filename.

    This is a gap sanity check, not certification of an exchange calendar.
    Small holiday date shifts are allowed; missing weeks and mixed cadences fail.
    """
    dates = pd.DatetimeIndex(dates).sort_values()
    if len(dates) < 3 or dates.hasnans or not dates.is_unique:
        raise ValueError("At least three unique observation dates are required")
    gaps = dates.to_series().diff().dropna().dt.total_seconds() / 86400
    median = gaps.median()
    if 0 < median <= 3 and gaps.between(1, 7).all():
        return "daily", 252
    if 5 <= median <= 9 and gaps.between(5, 9).all():
        return "weekly", 52
    raise ValueError("Unsupported or mixed observation frequency")


def cad_prices(prices, fx, ticker):
    """Adjusted close in CAD. USD prices use the last Bank of Canada rate on or before each date."""
    s = prices[prices.ticker == ticker].sort_values("date")[["date", "adj_close", "currency"]]
    if s.empty:
        raise ValueError(f"Ticker {ticker} not found in prices_weekly.csv")
    if not s.currency.isin(["CAD", "USD"]).all() or s.currency.nunique() != 1:
        raise ValueError(f"Ticker {ticker} has unsupported or inconsistent currency")
    if s.currency.iloc[0] == "USD":
        s = pd.merge_asof(s, fx[["date", "usdcad"]], on="date", direction="backward")
        s["price_cad"] = s.adj_close * s.usdcad
    else:
        s["price_cad"] = s.adj_close
    return s.set_index("date")["price_cad"].rename(ticker)


def price_table(prices, fx, tickers, start, end):
    """One column per ticker, only dates where every holding has a price (common trading days)."""
    series = [cad_prices(prices, fx, t) for t in tickers]
    series = [s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))] for s in series]
    conventions = {observation_convention(s.index) for s in series}
    if len(conventions) != 1:
        raise ValueError("Mixed holding observation frequencies")
    df = pd.concat(series, axis=1, sort=True).dropna()
    if observation_convention(df.index) not in conventions:
        raise ValueError("Common calendar changes observation frequency")
    return df


