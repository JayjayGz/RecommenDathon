"""Build the 15 AlphaForge reference portfolios from written rules, then validate them.

Rules (team assumptions, see docs/portfolio_rules.md):
  1. The band sets the split between bonds, stocks and alternatives.
  2. The style decides which assets fill the stock part.
  3. Equal weights inside each group.
  4. Caps: single stock per band; crypto only if allowed.
  5. Validate against band limits; if a portfolio fails, trim (crypto, then single stocks, then stocks to bonds).

Educational simulation with fictional profiles. Not financial advice.
"""

import json
import sys

import pandas as pd

import backtest_viewer as bv

BANDS = {
    "low":    {"bonds": {"XBB.TO": 45, "ZST.TO": 25}, "stocks": 30, "alt": 0,  "max_stock": 5,
               "max_vol": 7, "max_dd": -15},
    "medium": {"bonds": {"XBB.TO": 30, "AGG": 10},    "stocks": 55, "alt": 5,  "max_stock": 10,
               "max_vol": 13, "max_dd": -22},
    "high":   {"bonds": {"XBB.TO": 10},               "stocks": 80, "alt": 10, "max_stock": 15,
               "max_vol": 25, "max_dd": -40},
}

# Each style: list of (share of the stock part, holdings that split it equally). ETFs in their own group.
STYLES = {
    "Broad diversifier":     {"any":  [(50, ["XIU.TO"]), (50, ["SPY"])]},
    "Home country":          {"low":  [(60, ["XIU.TO"]), (40, ["RY.TO", "CNR.TO", "FTS.TO", "ATD.TO"])],
                              "high": [(60, ["XIU.TO"]), (40, ["RY.TO", "CNR.TO", "FTS.TO", "ATD.TO",
                                                               "SHOP.TO", "CSU.TO", "CNQ.TO"])]},
    "Growth and innovation": {"any":  [(50, ["QQQ"]), (30, ["NVDA", "MSFT", "SHOP.TO", "CSU.TO"]), (20, ["SPY"])]},
    "Income and stability":  {"any":  [(70, ["RY.TO", "TD.TO", "FTS.TO", "ENB.TO", "PG", "JNJ", "JPM"]),
                                       (30, ["XIU.TO"])]},
    "Responsible (ESG)":     {"low":  [(100, ["ESGV"])],
                              "high": [(80, ["ESGV"]), (20, ["QQQ"])]},
}
ETFS = {"XIU.TO", "SPY", "QQQ", "ESGV", "XBB.TO", "ZST.TO", "AGG", "TLT", "GLD"}
CRYPTO = ["BTC-USD", "ETH-USD"]

PROFILES = [  # id, band, style, crypto_allowed, persona
    (1, "low", "Broad diversifier", False, None), (2, "low", "Home country", False, None),
    (3, "low", "Growth and innovation", False, None), (4, "low", "Income and stability", False, "Robert"),
    (5, "low", "Responsible (ESG)", False, None),
    (6, "medium", "Broad diversifier", False, None), (7, "medium", "Home country", False, None),
    (8, "medium", "Growth and innovation", True, None), (9, "medium", "Income and stability", False, None),
    (10, "medium", "Responsible (ESG)", False, "Mateo"),
    (11, "high", "Broad diversifier", False, None), (12, "high", "Home country", False, None),
    (13, "high", "Growth and innovation", True, "Amira"), (14, "high", "Income and stability", False, None),
    (15, "high", "Responsible (ESG)", False, None),
]


def style_groups(style, band):
    s = STYLES[style]
    return s.get(band) or s.get("any") or s["low"]


def build(band, style, crypto_allowed):
    b = BANDS[band]
    w = dict(b["bonds"])
    stocks = b["stocks"]
    if b["alt"]:
        if crypto_allowed:
            crypto = 2 if band == "medium" else 5
            w["GLD"] = b["alt"] - crypto
            for c in CRYPTO:
                w[c] = crypto / len(CRYPTO)
        elif band == "high":          # no crypto: gold 5, the other 5 goes to stocks
            w["GLD"] = 5
            stocks += b["alt"] - 5
        else:
            w["GLD"] = b["alt"]
    for share, names in style_groups(style, band):
        for t in names:
            w[t] = w.get(t, 0) + stocks * share / 100 / len(names)
    return w


def round_weights(w):
    """Whole percentages; leftover goes to the largest bond holding so the total is exactly 100."""
    r = {t: round(v) for t, v in w.items() if round(v) > 0}
    bond = max((t for t in r if t in {"XBB.TO", "ZST.TO", "AGG"}), key=lambda t: r[t])
    r[bond] += 100 - sum(r.values())
    return r


def check_caps(w, band):
    cap = BANDS[band]["max_stock"]
    return [f"{t} {v}% > {cap}% single-stock cap" for t, v in w.items()
            if t not in ETFS and t not in CRYPTO and v > cap]


def validate(prices, fx, w, band, start, end):
    df = bv.price_table(prices, fx, list(w), start, end)
    m = bv.metrics(bv.portfolio_value(df, {t: v / 100 for t, v in w.items()}, "monthly"))
    m = {k: (v.item() if hasattr(v, "item") else v) for k, v in m.items()}   # numpy -> plain Python for JSON
    b = BANDS[band]
    m["passes"] = bool(m["volatility_pct"] <= b["max_vol"] and m["max_drawdown_pct"] >= b["max_dd"])
    return m


def trim(w, band, style):
    """One trimming step. Returns the new weights and a log line, or None if nothing is left to trim."""
    w = dict(w)
    crypto = [t for t in CRYPTO if t in w]
    if crypto:
        moved = sum(w.pop(t) for t in crypto)
        w["GLD"] = w.get("GLD", 0) + moved
        return w, f"moved {moved}% crypto to gold"
    singles = [t for t in w if t not in ETFS]
    if singles:
        etf = next(n[0] for _, n in style_groups(style, band) if n[0] in ETFS)
        moved = sum(w.pop(t) for t in singles)
        w[etf] += moved
        return w, f"moved {moved}% single stocks into {etf}"
    equity = [t for t in w if t in {"XIU.TO", "SPY", "QQQ", "ESGV"}]
    if equity:
        top = max(equity, key=lambda t: w[t])
        step = min(5, w[top])
        w[top] -= step
        w["XBB.TO"] = w.get("XBB.TO", 0) + step
        return {t: v for t, v in w.items() if v > 0}, f"moved {step}% from {top} to XBB.TO"
    return None


def main(data_dir="data", out="profiles.json"):
    prices, fx = bv.load_data(data_dir)
    start, end = prices.date.min(), prices.date.max()
    profiles, rows = [], []
    for pid, band, style, crypto_ok, persona in PROFILES:
        w = round_weights(build(band, style, crypto_ok))
        assert sum(w.values()) == 100, (pid, w)
        log = check_caps(w, band)
        m = validate(prices, fx, w, band, start, end)
        while not m["passes"]:
            step = trim(w, band, style)
            if step is None:
                log.append("still outside limits after all trims")
                break
            w, line = step
            log.append(line)
            m = validate(prices, fx, w, band, start, end)
        profiles.append({"id": pid, "band": band, "style": style, "persona": persona,
                         "crypto_allowed": crypto_ok,
                         "weights": {t: v / 100 for t, v in sorted(w.items(), key=lambda kv: -kv[1])},
                         "validation": {**m, "adjustments": log}})
        rows.append({"id": pid, "band": band, "style": style, "persona": persona or "",
                     "weights": ", ".join(f"{t} {v:g}" for t, v in sorted(w.items(), key=lambda kv: -kv[1])),
                     "vol": m["volatility_pct"], "max_dd": m["max_drawdown_pct"],
                     "passes": m["passes"], "adjustments": "; ".join(log)})

    config = {"_note": "Reference portfolios built from rules in build_portfolios.py. Educational simulation "
                       "with fictional profiles; not financial advice.",
              "band_limits": {k: {"max_volatility_pct": v["max_vol"], "max_drawdown_pct": v["max_dd"],
                                  "max_single_stock_pct": v["max_stock"]} for k, v in BANDS.items()},
              "profiles": profiles}
    with open(out, "w") as f:
        json.dump(config, f, indent=2)
    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
