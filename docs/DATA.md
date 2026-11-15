# Data inputs and preparation

The canonical data folder is `dataset/` at the Git repository root. CSVs are local inputs and ignored by Git. Copy the supplied files there; do not commit market data. The [dataset README](../dataset/README.md) lists current files and observed coverage.

## Current price file

`prices_weekly.csv` is the active file, renamed from `prices_daily.csv` without changing its bytes. Local and S3 adapters expect the weekly filename; the older daily filename is not used as a fallback. The supplied header begins `ticker,date`; the loader selects `date`, `ticker`, `adj_close` and `currency` by name, so their order does not matter. No data or header swap is required. `fx_usdcad_daily.csv` supplies CAD per USD in `usdcad`.

`LocalPortfolioRepository` defaults to the repository's `dataset/` and `profiles.json`, independent of the current shell directory. Passing an explicit folder or profile path overrides those defaults; relative overrides follow the caller's working directory.

## Compatibility with reference portfolios

The current local price snapshot has 55,859 rows and 99 tickers, from 2016-01-01 through 2026-11-20. Its median within-ticker date gap is seven days. Metrics now infer cadence from actual dates: weekly returns use 52 observations/year and daily returns use 252. Volatility uses sample standard deviation times the square root of that factor; growth uses the number of return intervals divided by that factor. The workflow excludes dates after the requested as-of date. Saved profile validation metrics predate this methodology and must not be reused as current results.

FX starts on 2021-11-12 and ends on 2026-11-12. USD observations without a preceding FX rate are unavailable; do not fabricate earlier FX history. Common-date alignment can shorten the usable portfolio window further.

The saved reference portfolios require 13 tickers absent from the current file; see the [dataset inventory](../dataset/README.md) for the list. The calculation API returns `MISSING_INFO` for unavailable holdings. Tests asserting old real-market portfolio verdicts skip explicitly when that reference universe is incomplete; synthetic accounting and policy tests continue to run. Agree on compatible allocation rules before regenerating `profiles.json`.

## Rebuild tools

From the Git root:

```powershell
python backend/scripts/build_dataset.py
```

This is the **original 31-asset starter generator**, with its original 2021-11-12 to 2026-11-12 window. It writes to `dataset/rebuilt_starter/` to preserve the supplied active prices. Its price output remains `prices_daily.csv` in the separate rebuilt folder. To intentionally use that daily output with the active adapter, place it under the active `prices_weekly.csv` filename; actual daily dates still select daily annualization. The filename never determines cadence. This tool does not reproduce the currently supplied 99-ticker snapshot. `backend/scripts/universe_v2.py` is a proposed universe definition, not automatically applied to the generator or saved profiles. Source metadata and asset-selection rationale are maintained by hand.

Once the team agrees on compatible inputs and rules, rebuild profiles explicitly:

```powershell
python backend/scripts/build_portfolios.py dataset profiles.json
```

That command overwrites its output. It has not been run as part of the file reorganization. Rebuilding requires pandas, yfinance and network access; no download is needed for offline checks.

## Data rules

The workflow parses and hashes the complete input files, then checks supported currencies
for the selected profile's reference holdings and requested changes. Unrelated JPY assets
may remain in the CSV. A required asset outside CAD/USD returns
`MISSING_INFO` / `UNSUPPORTED_HOLDING_CURRENCY` before calculations or explanation.
Direct currency-conversion callers also reject unsupported or inconsistent currencies.
Weekly observations are supported; absent reference holdings still require genuine history or agreed reference-allocation changes. Do not relabel currencies or forward-fill weekly prices to manufacture daily history.

Cadence checks run per required holding and again on the aligned portfolio calendar. Daily history requires a median gap of at most three days and no gap over seven days; weekly history requires a median gap of five to nine days with every gap between five and nine days. These checks allow small holiday date shifts but reject missing weeks and clearly sparse or mixed cadence. They do not certify completeness against an exchange calendar. Monthly rebalancing uses the first observed close in the new month after marking existing holdings to that close. Weekly drawdown and volatility omit intraweek moves. FX continues to use the preceding daily USD/CAD rate without looking ahead.

- Use `adj_close` for returns; prices are already split-adjusted.
- Convert USD prices with the last available Bank of Canada USD/CAD rate on or before each date (`merge_asof`, backward). Never use a future rate.
- Align portfolios on dates where every holding has a usable price. State the resulting window, observation count and CAD currency.
- Monthly macro reference dates are not publication dates. Do not use unpublished values in a strategy backtest.
- Record source and processing assumptions; no ESG scores or fundamentals are supplied.
- The original organizer pack has survivorship and back-adjustment limitations; see the [archived guide](starter-dataset.md). Its row counts and source metadata are not guarantees about the current files.
