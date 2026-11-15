# Data inputs and preparation

The canonical data folder is `dataset/` at the Git repository root. CSVs are local inputs and ignored by Git. Copy the supplied files there; do not commit market data. The [dataset README](../dataset/README.md) lists current files and observed coverage.

## Current price file

`prices_daily.csv` is the active file, replacing `historique_actifs_2011.csv`. The supplied header begins `ticker,date`; the loader selects `date`, `ticker`, `adj_close` and `currency` by name, so their order does not matter. No data or header swap is required. `fx_usdcad_daily.csv` supplies CAD per USD in `usdcad`.

`LocalPortfolioRepository` defaults to the repository's `dataset/` and `profiles.json`, independent of the current shell directory. Passing an explicit folder or profile path overrides those defaults; relative overrides follow the caller's working directory.

## Compatibility with reference portfolios

The current local price snapshot has 57,560 rows and 102 tickers, from 2016-01-01 through 2026-11-20. Its median within-ticker date gap is seven days, indicating weekly observations despite the filename. Existing metrics assume 252 observations/year; frequency handling requires a separate review before these observations support annualized metrics. The snapshot also contains dates beyond the current 2026-11-14 client date; simulations must define and enforce an as-of date rather than treating all rows as past history.

FX starts on 2021-11-12 and ends on 2026-11-12. USD observations without a preceding FX rate are unavailable; do not fabricate earlier FX history. Common-date alignment can shorten the usable portfolio window further.

The saved reference portfolios require 13 tickers absent from the current file; see the [dataset inventory](../dataset/README.md) for the list. The calculation API returns `MISSING_INFO` for unavailable holdings. Tests asserting old real-market portfolio verdicts skip explicitly when that reference universe is incomplete; synthetic accounting and policy tests continue to run. Agree on compatible allocation rules before regenerating `profiles.json`.

## Rebuild tools

From the Git root:

```powershell
python backend/scripts/build_dataset.py
```

This is the **original 31-asset starter generator**, with its original 2021-11-12 to 2026-11-12 window. It writes to `dataset/rebuilt_starter/` to preserve the supplied active prices. Its price output uses `prices_daily.csv`; the name does not determine frequency or the generated window. This tool does not reproduce the currently supplied 102-ticker snapshot. `backend/scripts/universe_v2.py` is a proposed universe definition, not automatically applied to the generator or saved profiles. Source metadata and asset-selection rationale are maintained by hand.

Once the team agrees on compatible inputs and rules, rebuild profiles explicitly:

```powershell
python backend/scripts/build_portfolios.py dataset profiles.json
```

That command overwrites its output. It has not been run as part of the file reorganization. Rebuilding requires pandas, yfinance and network access; no download is needed for offline checks.

## Data rules

- Use `adj_close` for returns; prices are already split-adjusted.
- Convert USD prices with the last available Bank of Canada USD/CAD rate on or before each date (`merge_asof`, backward). Never use a future rate.
- Align portfolios on dates where every holding has a usable price. State the resulting window, observation count and CAD currency.
- Monthly macro reference dates are not publication dates. Do not use unpublished values in a strategy backtest.
- Record source and processing assumptions; no ESG scores or fundamentals are supplied.
- The original organizer pack has survivorship and back-adjustment limitations; see the [archived guide](starter-dataset.md). Its row counts and source metadata are not guarantees about the current files.
