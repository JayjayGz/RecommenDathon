"""Build and validate reference portfolios, then persist through a repository port."""
import pandas as pd
from .repositories import PortfolioRepository
from alphaforge.domain.reference_portfolios import BANDS, PROFILES, build, round_weights, check_caps, validate, trim

def build_profiles(repository: PortfolioRepository, data_dir=None, out=None):
    prices, fx = repository.load_data(data_dir)
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
    repository.write_profiles(config, out)
    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    return config, pd.DataFrame(rows)


