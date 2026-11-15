# Reference portfolio rules

These rules build the 15 reference portfolios in profiles.json (implemented in src/alphaforge/domain/reference_portfolios.py; entry point: scripts/build_portfolios.py). All numbers are team assumptions. Educational simulation with fictional profiles; not financial advice.

## Rule 1: the risk band sets the split between asset classes (% of total)

| Band | Risk levels | Bonds and cash | Stocks | Alternatives |
| --- | --- | --- | --- | --- |
| Low | 1-2 | 70: XBB.TO 45, ZST.TO 25 | 30 | 0 |
| Medium | 3-4 | 40: XBB.TO 30, AGG 10 | 55 | 5: GLD 5, or GLD 3 + crypto 2 if allowed |
| High | 5-6 | 10: XBB.TO 10 | 80 | 10: GLD 5 + crypto 5 if allowed; otherwise GLD 5 and +5 to stocks |

## Rule 2: the style fills the stock part (% of the stock part, equal weights inside each group)

| Style | Stock part |
| --- | --- |
| Broad diversifier | XIU.TO 50, SPY 50 |
| Home country | XIU.TO 60; Canadian stocks 40: RY, CNR, FTS, ATD (high band adds SHOP, CSU, CNQ) |
| Growth and innovation | QQQ 50; tech stocks 30: NVDA, MSFT, SHOP, CSU; SPY 20 |
| Income and stability | Dividend payers 70: RY, TD, FTS, ENB, PG, JNJ, JPM; XIU.TO 30 |
| Responsible (ESG) | ESGV 100 (high band: ESGV 80, QQQ 20). No energy stocks. |

## Rule 3: caps
- Single stock: at most 5% of total (low), 10% (medium), 15% (high).
- Crypto only when the profile allows it, split evenly between BTC-USD and ETH-USD.
- Exclusion flags (e.g. fossil fuels) remove ENB, CNQ, XOM and spread their weight over the rest of their group.
- Sector limits apply to single stocks only; ETFs count as diversified (no look-through of ETF holdings: a stated limitation).

## Rule 4: rounding
Whole percentages; any leftover goes to the largest bond holding so the total is exactly 100.

## Rule 5: validation and trimming
1. Backtest over the data window in CAD, rebalanced monthly; compute volatility and maximum drawdown.
2. Band limits: low 7% volatility and -15% drawdown; medium 13% and -22%; high 25% and -40%.
3. If a portfolio breaks its limits, trim in order and log each step:
   - crypto moves to gold;
   - single stocks move into the style's ETF;
   - 5 points move from the largest equity ETF to XBB.TO; repeat until it passes.

## Known results (starter data, Nov 2021 - Nov 2026)

These results were recorded before the month-boundary correction. The monthly backtest now values existing units at the first common observed close before rebalancing, preserving the price change since the previous month's last close. Rebuild and verify the generated profiles using the agreed CSVs before treating the metrics, pass flags or trimming decisions below as current.
- All 15 pass after trimming. Profiles 3 (low growth) and 8 (medium growth) needed trims; the growth rule should be fixed for those bands.
- Rebalancing choice matters: with buy-and-hold instead of monthly rebalancing, some results change (sensitivity test for the documentation).
