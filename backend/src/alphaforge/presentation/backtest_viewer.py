"""Streamlit reference portfolio viewer; run backend/scripts/backtest_viewer.py."""
import json
import pandas as pd
from alphaforge.application.backtests import run_all

def main(repository, default_data_dir):
    import streamlit as st

    st.set_page_config(page_title="AlphaForge profile backtests", layout="wide")
    st.title("AlphaForge profile backtests")
    st.caption("Educational simulation with fictional profiles. Not financial advice. "
               "Past results do not predict future results.")

    with st.sidebar:
        data_dir = st.text_input("Dataset folder", str(default_data_dir))
        uploaded = st.file_uploader("profiles.json", type="json")
        rebalance = st.radio("Rebalancing", ["monthly", "none"],
                             help="monthly: back to target weights at each month start. none: buy and hold.")

    try:
        prices, fx = repository.load_data(data_dir)
    except FileNotFoundError:
        st.error(f"Put prices_daily.csv and fx_usdcad_daily.csv in the '{data_dir}' folder.")
        st.stop()

    config = json.load(uploaded) if uploaded else repository.load_profiles()

    first, last = prices.date.min().date(), prices.date.max().date()
    with st.sidebar:
        start, end = st.slider("Period", min_value=first, max_value=last, value=(first, last))

    try:
        values, table = run_all(prices, fx, config, start, end, rebalance)
    except (ValueError, KeyError) as error:
        st.error(f"Reference portfolios cannot be evaluated with this dataset: {error}")
        st.info("See docs/DATA.md for missing legacy tickers and available FX history.")
        st.stop()

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

