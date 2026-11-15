"""Pure currency conversion and common-calendar preparation."""
import pandas as pd

def cad_prices(prices, fx, ticker):
    """Adjusted close in CAD. USD prices use the last Bank of Canada rate on or before each date."""
    s = prices[prices.ticker == ticker].sort_values("date")[["date", "adj_close", "currency"]]
    if s.empty:
        raise ValueError(f"Ticker {ticker} not found in prices_daily.csv")
    if s.currency.iloc[0] == "USD":
        s = pd.merge_asof(s, fx[["date", "usdcad"]], on="date", direction="backward")
        s["price_cad"] = s.adj_close * s.usdcad
    else:
        s["price_cad"] = s.adj_close
    return s.set_index("date")["price_cad"].rename(ticker)


def price_table(prices, fx, tickers, start, end):
    """One column per ticker, only dates where every holding has a price (common trading days)."""
    df = pd.concat([cad_prices(prices, fx, t) for t in tickers], axis=1, sort=True).dropna()
    return df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]


