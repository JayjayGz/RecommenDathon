"""Compare configured reference portfolios using pure domain calculations."""
import pandas as pd
from alphaforge.domain import backtest, market_data

def run_all(prices, fx, config, start, end, rebalance):
    limits = config["band_limits"]
    values, rows = {}, []
    for p in config["profiles"]:
        label = f'{p["id"]} · {p["band"].capitalize()} · {p["style"]}' + (f' ({p["persona"]})' if p.get("persona") else "")
        df = market_data.price_table(prices, fx, list(p["weights"]), start, end)
        v = backtest.portfolio_value(df, p["weights"], rebalance)
        m = backtest.metrics(v)
        lim = limits[p["band"]]
        m["within_band_limits"] = (m["volatility_pct"] <= lim["max_volatility_pct"]
                                   and m["max_drawdown_pct"] >= lim["max_drawdown_pct"])
        rows.append({"profile": label, **m, "first_date": df.index[0].date().isoformat(),
                     "last_date": df.index[-1].date().isoformat(), "days": len(df)})
        values[label] = v
    return values, pd.DataFrame(rows).set_index("profile")


