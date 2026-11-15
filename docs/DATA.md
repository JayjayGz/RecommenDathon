# Data: what you need and where to put it

The data files are **not in this repo**. The prices come from Yahoo Finance, whose terms limit redistribution, so `.gitignore` excludes the CSVs. Each teammate gets them once and puts them in the right folder.

## Files you need

Put these in `alphaforge_starter/` at the root of your copy of the repo:

| File | Approx. rows | What it holds | Used by |
| --- | --- | --- | --- |
| `prices_daily.csv` | ~40,000 | Daily prices: date, ticker, open, high, low, close, adj_close, volume, currency | Risk module, `build_portfolios.py`, `backtest_viewer.py` |
| `fx_usdcad_daily.csv` | ~1,250 | Bank of Canada USD/CAD rate (CAD per 1 USD) | CAD conversion everywhere |
| `assets_universe.csv` | 31 | Ticker, name, asset class, market, currency, sector | Profile rules, app labels |
| `corporate_actions.csv` | ~660 | Dividends and splits by ex-date (reference only; prices are already adjusted) | Income style, dividend checks |
| `macro_rates.csv` | ~8,300 | Policy rates, 2y and 10y yields, CPI (Canada and U.S.), U.S. unemployment | Risk-free rate, context in explanations |
| `sources_metadata.csv` | 6 | Source, dates, processing, limits and terms for each file | README, technical documentation |

Data window: **2021-11-12 to 2026-11-12** (5 years, includes 2022).

## How to get them

**Option 1: copy them (fastest).**
- On the team Kiro IDE: `cp /workshop/RecommenDathon/alphaforge_starter/*.csv alphaforge_starter/`
- On your laptop: copy them from the organizers' starter kit (event drive or Discord) into `alphaforge_starter\`.

**Option 2: rebuild them.** Needs internet and `pip install pandas yfinance`:
```bash
cd alphaforge_starter
python3 build_dataset.py
cd ..
```
Rebuilt prices can differ slightly from the organizers' copy (Yahoo revises adjusted prices). Use one version for the whole team.

## Check you have everything

```bash
ls alphaforge_starter/*.csv
wc -l alphaforge_starter/*.csv
```
You should see the six files with roughly the row counts above (plus one header line each).

## Our asset list

When the team finalizes its own assets, they are listed in `asset_selection.csv` (ticker, which profiles use it, why it was chosen), and the data is rebuilt with `build_dataset.py` after editing its `UNIVERSE` list. Update this section when that happens.

## Rules when using the data

- Use `adj_close` for returns. Don't reapply splits.
- `.TO` tickers are in CAD; everything else is USD. Convert with `fx_usdcad_daily.csv` (last rate on or before each date).
- Never use data dated after a simulation's as-of date. Monthly macro data is dated by reference month, not release date.
- Cite the source, period and currency of every number shown to users.

Full details: `alphaforge_starter/README.md` and `sources_metadata.csv`.
