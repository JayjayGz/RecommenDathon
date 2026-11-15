"""AlphaForge profile backtest viewer.

Reads profiles.json and the starter dataset, then shows how each reference
portfolio would have behaved in CAD: growth of $10,000, drawdowns, and a
metrics table checked against the band limits.

Run:  streamlit run backtest_viewer.py
Educational simulation only. Past results do not predict future results.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# ---------- data ----------

def load_data(data_dir):
    data_dir = Path(data_dir)
    prices = pd.read_csv(data_dir / "prices_daily.csv", parse_dates=["date"])
    fx = pd.read_csv(data_dir / "fx_usdcad_daily.csv", parse_dates=["date"]).sort_values("date")
    return prices, fx


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


# ---------- backtest ----------

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


def run_all(prices, fx, config, start, end, rebalance):
    limits = config["band_limits"]
    values, rows = {}, []
    for p in config["profiles"]:
        label = f'{p["id"]} · {p["band"].capitalize()} · {p["style"]}' + (f' ({p["persona"]})' if p.get("persona") else "")
        df = price_table(prices, fx, list(p["weights"]), start, end)
        v = portfolio_value(df, p["weights"], rebalance)
        m = metrics(v)
        lim = limits[p["band"]]
        m["within_band_limits"] = (m["volatility_pct"] <= lim["max_volatility_pct"]
                                   and m["max_drawdown_pct"] >= lim["max_drawdown_pct"])
        rows.append({"profile": label, **m, "first_date": df.index[0].date().isoformat(),
                     "last_date": df.index[-1].date().isoformat(), "days": len(df)})
        values[label] = v
    return values, pd.DataFrame(rows).set_index("profile")


# ---------- app ----------

def main():
    import streamlit as st

    st.set_page_config(page_title="AlphaForge profile backtests", layout="wide")
    st.title("AlphaForge profile backtests")
    st.caption("Educational simulation with fictional profiles. Not financial advice. "
               "Past results do not predict future results.")

    with st.sidebar:
        data_dir = st.text_input("Starter data folder", "data")
        uploaded = st.file_uploader("profiles.json", type="json")
        rebalance = st.radio("Rebalancing", ["monthly", "none"],
                             help="monthly: back to target weights at each month start. none: buy and hold.")

    try:
        prices, fx = load_data(data_dir)
    except FileNotFoundError:
        st.error(f"Put prices_daily.csv and fx_usdcad_daily.csv in the '{data_dir}' folder.")
        st.stop()

    config = json.load(uploaded) if uploaded else json.loads(Path("profiles.json").read_text())

    first, last = prices.date.min().date(), prices.date.max().date()
    with st.sidebar:
        start, end = st.slider("Period", min_value=first, max_value=last, value=(first, last))

    values, table = run_all(prices, fx, config, start, end, rebalance)

    labels = list(values)
    chosen = st.multiselect("Profiles to compare", labels,
                            default=[l for l in labels if "(" in l] or labels[:3])
    if not chosen:
        st.info("Pick at least one profile.")
        st.stop()

    growth = pd.DataFrame({k: values[k] for k in chosen})
    st.subheader("Growth of $10,000 (CAD)")
    st.line_chart(growth)

    st.subheader("Drawdown from previous peak (%)")
    st.line_chart((growth / growth.cummax() - 1) * 100)

    st.subheader("Metrics and band check")
    st.dataframe(table.loc[chosen], width="stretch")

    st.subheader("Weights")
    pick = st.selectbox("Profile", chosen)
    profile = next(p for p in config["profiles"] if pick.startswith(f'{p["id"]} ·'))
    st.bar_chart(pd.Series(profile["weights"], name="weight") * 100)

    st.caption("Method: Yahoo Finance adjusted close from the AlphaForge starter dataset; USD assets converted "
               "with the last Bank of Canada USD/CAD rate on or before each date; only days when every holding "
               "traded (crypto weekends dropped); no fees, taxes or slippage.")


if __name__ == "__main__":
    main()
