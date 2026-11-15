# Local dataset

All CSV inputs live here and are ignored by Git. File contents were preserved during the reorganization.

| File | Purpose |
| --- | --- |
| `prices_daily.csv` | Active price input; `ticker,date,open,high,low,close,adj_close,volume,currency` |
| `fx_usdcad_daily.csv` | USD/CAD conversion rates |
| `assets_universe_nouveaux.csv` | Supplied asset metadata |
| `asset_selection.csv` | Team asset-selection rationale |
| `corporate_actions.csv` | Corporate actions for reference; do not reapply splits |
| `macro_rates.csv` | Macro context; respect publication dates |
| `sources_metadata.csv` | Supplied source metadata; some records still describe the original starter files |

The active filename is `prices_daily.csv` (replacing `historique_actifs_2011.csv`). Columns are selected by header name: both `ticker,date,...` and `date,ticker,...` are accepted without rewriting the CSV.

The current local snapshot has 57,560 rows, 102 tickers and dates from 2016-01-01 through 2026-11-20. Its median within-ticker observation gap is seven days; the filename alone does not establish daily frequency. Existing metrics annualize using 252 observations/year and therefore need a separate frequency review before use with weekly observations. Dates beyond the simulation's as-of date must not be treated as available historical observations. FX covers 2021-11-12 through 2026-11-12; availability differs by ticker.

`profiles.json` still uses a different reference universe. ATD.TO, CNQ.TO, CNR.TO, CSU.TO, ENB.TO, ESGV, FTS.TO, RY.TO, SHOP.TO, TD.TO, XBB.TO, XIU.TO and ZST.TO are absent from the supplied price file. Reconcile the agreed allocation rules before regenerating profiles. No automatic ticker substitution is applied.

The source metadata and corporate-action files have not been certified against the expanded history. `data_quality_warnings.txt` is currently absent; this is not evidence that the data has no issues.

See [data handling and rebuild instructions](../docs/DATA.md) and the [archived organizer guide](../docs/starter-dataset.md).
