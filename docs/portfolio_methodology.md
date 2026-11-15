# Portfolio methodology

Educational simulation. Fictional profiles. Not personalized financial advice. No real
transactions. Weekly data only — see "Method" below for why, and "Limitations" for what
that trades off.

This document explains, in plain language, how AlphaForge turns a questionnaire into a
reference portfolio, how it checks a proposed change against that profile's limits, and
exactly how every number shown is computed. Every number here states its source and
period; where a number isn't available, that's said explicitly rather than guessed.

## 1. The 15 profiles: 3 bands x 5 styles

Every investor lands in one of 15 reference profiles: a **risk band** (low, medium, high)
crossed with an **investment style** (Broad diversifier, Home country, Growth and
innovation, Income and stability, Responsible ESG). The band sets how much goes into
bonds vs. stocks vs. alternatives; the style decides which stocks fill the stock part.

| Band | Bonds/cash | Stocks | Alternatives |
| --- | --- | --- | --- |
| Low | 70% (XBB.TO 45, ZST.TO 25) | 30% | 0% |
| Medium | 40% (XBB.TO 30, AGG 10) | 55% | 5% (GLD, or GLD+crypto if allowed) |
| High | 10% (XBB.TO 10) | 80% | 10% (GLD+crypto if allowed, else GLD + extra to stocks) |

The style then fills the stock portion — e.g. "Income and stability" splits it across
dividend-paying stocks (RY.TO, TD.TO, FTS.TO, ENB.TO, PG, JNJ, JPM) plus a broad Canadian
ETF; "Growth and innovation" uses QQQ plus individual tech names. Full rules are in
`docs/portfolio_rules.md`; the code that builds them is
`backend/src/alphaforge/domain/reference_portfolios.py`.

After building, each portfolio is backtested and trimmed (crypto to gold, then single
stocks into the style's ETF, then equity ETF into bonds) until it passes its band's
limits. All 15 currently pass. Weights always round to whole percent, with any leftover
going to the largest bond holding — that's why a capped request can sometimes shift a
bond holding by a point or two even though bonds are otherwise protected.

## 2. Questionnaire to profile: how risk gets assessed

The questionnaire doesn't ask the user to type in their band directly. It asks several
narrower questions, and the system scores them the way a bank assesses risk: two
separate tracks, each 1-6, and the **lower of the two wins** — one confident answer can
never override a cautious one.

- **Tolerance** (willingness to take risk) = the lowest of: `risk` (self-reported, 5
  levels), `reaction` (how a 20% drop over 3 months would feel, 4 levels), `knowledge`
  (investing experience, 4 levels).
- **Capacity** (ability to take risk regardless of feelings) = the lower of: `horizon`
  (investment timeframe, 4 levels), `income` (predictability of income, 4 levels).
- **Level** = the lower of capacity and tolerance, 1-6. Band = low (1-2) / medium (3-4) /
  high (5-6).

Style comes from separate signals: `sectors`/`assets` answers (e.g. interest in
"technology" points to Growth and innovation; bonds/cash-heavy interest with no
stocks/crypto points to Income and stability). Two styles — Home country and
Responsible (ESG) — have **no signal at all** in the current 8 relevant questions; they
need an explicit override (see Limitations).

Flags (crypto allowed, exclusions) come from the matched profile's own definition, not
from a separate calculation.

### Worked examples

| Persona | risk / reaction / knowledge | horizon / income | Band | Style | Profile |
| --- | --- | --- | --- | --- | --- |
| Robert | low / hesitant / basic | 5 / regular | low | Income and stability | **4** |
| Mateo | medium / concerned / good | 10 / regular | medium | Responsible (ESG)* | **10** |
| Amira | very_high / calm / advanced | 15+ / regular | high | Growth and innovation | **13** |

\* Mateo's ESG style needs the explicit override — see Limitations.

### Why this matters: comparison against a simpler approach

A simpler matcher exists elsewhere in the codebase (`profile_matching.match_profile()`)
that, left on its own, maps the 5-level `risk` answer straight to a band and
auto-scores style by asset-class overlap. Run side by side on the same answers:

| Case | Simple matcher alone | This assessment feeding it | Why they differ |
| --- | --- | --- | --- |
| Robert | low band, profile 3 (Growth and innovation) | low band, **profile 4** (Income and stability) | Style auto-scoring just maximizes weight in the requested asset class; profile 3 happens to hold slightly more bonds than profile 4 after its own trim, despite being thematically "growth." |
| Mateo | medium band, profile 6 (Broad diversifier) | medium band, **profile 10** (Responsible ESG) | "funds" is too broad a signal to reach ESG at all without the explicit flag. |
| Amira | high band, profile 14 (Income and stability) | high band, **profile 13** (Growth and innovation) | The simple matcher rewards literal "stocks" overlap; profile 14 holds more individual stocks (56% vs. 24%) than profile 13, which is mostly ETF-wrapped, even though profile 13 is the actual tech/growth fit. |
| Edge: risk=high, reaction=worried | high band | **low band** | Self-report alone ignores the worried reaction; this assessment's tolerance score is the *minimum* of the three signals, so one scared answer caps the whole band. |
| Edge: risk=very_high, horizon=1-2 years | high band | **low band** | Same mechanism on the capacity side — a 1-2 year horizon caps the band regardless of stated risk appetite, since there's no time to recover from a drawdown. |

That last two rows are the actual point of the two-track design: a confident or
risk-seeking answer should never unlock a high-risk portfolio if a different answer
(fear, or no time) contradicts it.

## 3. Band limits — what they are and why

The three bands each carry a fixed set of limits. **These are our own team's
assumptions, not a bank's or a regulator's** — documented here so they can be defended
or revised:

| Band | Max volatility | Max drawdown | Max single stock | Max gold | Max crypto (combined) |
| --- | --- | --- | --- | --- | --- |
| Low | 7% | -15% | 5% | 10% | 0% |
| Medium | 13% | -22% | 10% | 15% | 3% |
| High | 25% | -40% | 15% | 15% | 10% |

The reasoning tracks the questionnaire's own `reaction` question directly: it asks how a
**20% drop** over 3 months would feel. A low-band investor's drawdown limit (-15%) is
deliberately *tighter* than that 20% scenario — the idea is that someone who says a 20%
drop would make them want to pull their money out should never actually be exposed to
one. The single-stock/gold/crypto caps follow the same logic in reverse direction for
concentration: the more risk-tolerant the band, the more concentration is allowed, but
never unlimited — "high risk" is explicitly not "anything goes" (one of the project's
named test cases).

## 4. Method — exactly how every number is computed

- **Prices**: `dataset/prices_weekly.csv`, weekly Friday-dated `adj_close` (already
  split-adjusted; never reapplied). Crypto's `adj_close` is a direct copy of `close`
  (confirmed: 0 missing values across all 127 tickers as of this writing).
- **Currency**: every USD-listed holding is converted to CAD *before* any return is
  computed, using the Bank of Canada USD/CAD rate on or before that date
  (`merge_asof(direction="backward")`) from `fx_usdcad_daily.csv`.
- **Window**: Nov 12, 2021 - Nov 13, 2026. This isn't a choice about history length —
  it's set by **FX data availability**. The price history itself goes back further for
  some tickers, but FX coverage starts exactly 2021-11-12, so any USD holding's
  CAD-converted price is unusable before that date. Confirmed directly: SPY has price
  rows before 2021-11-12, but its first usable CAD-converted price is exactly that date.
- **Starting value**: $10,000 CAD, hypothetical, for every backtest.
- **Rebalancing**: monthly, back to target weights. At each month boundary, the
  *existing* units are priced at the new month's first close before rebalancing — this
  preserves any price move that happened right at the boundary, rather than losing it.
- **Volatility**: standard deviation of period-over-period returns, annualized by
  **√52** (weekly data) — the engine detects the actual observation frequency from the
  dates themselves, not from a filename, so it would use √252 automatically if fed
  daily data instead.
- **Max drawdown**: the worst peak-to-trough decline in the value series, with its date.
- **Annual growth**: compound annual growth rate from the first to the last value.
- **Only common trading days** are used — any date where even one holding lacks a price
  is dropped (this is why crypto's weekend-trading doesn't distort the numbers: the
  common-date intersection with weekday-only ETFs/stocks naturally excludes weekends).

## 5. Demo examples, with real numbers

**Robert (profile 4) asks to add 20% TSLA.** Result: `CONFLICT`.

| | Base | As requested (uncapped) | Adjusted (capped) |
| --- | --- | --- | --- |
| Status | PASS | CONFLICT | PASS |
| Volatility | 4.9% | 12.2% (limit 7%) | 5.7% |
| Max drawdown | -8.9% | -19.6% (limit -15%) | -10.3% |
| Single stock | — | 20% (limit 5%) | 5.0% |
| End value ($10,000 start) | $13,368 | $13,631 | $13,204 |

Note: "requested 20%, applied 5%" — the single-stock cap. `max_allowed` for this case
reports 20, not 5: once capped to 5%, the *capped* portfolio already passes every limit,
so the full raw request is fine to submit — the cap itself is what makes it fit.

**Amira (profile 13) asks to add 15% BTC-USD.** Result: `CONFLICT`.

| | Base | As requested (uncapped) | Adjusted (capped) |
| --- | --- | --- | --- |
| Status | PASS | CONFLICT | PASS |
| Volatility | 18.4% | 19.7% (limit 25% — still passes) | 19.0% |
| Max drawdown | -32.0% | -37.3% (limit -40% — still passes) | -34.7% |
| Combined crypto | 4.0% | 19.0% (limit 10%) | 10.0% |
| End value ($10,000 start) | $20,288 | $20,165 | $20,655 |

Notably, Amira's volatility and drawdown both still pass *even uncapped* — only the
combined crypto cap fails. Her high band has enough room that the conflict here is
purely about concentration, not overall portfolio risk.

Both tables: weekly Friday closes, CAD, Nov 2021-Nov 2026, as of 2026-11-15.

## 6. Where the money goes: exposures

`dataset/exposures_profile_tickers.csv` breaks down region, sector and asset-class
exposure per ticker, so a dashboard can show "where the money goes," not just risk
numbers. Every filled cell states its source and date; every unavailable cell says so
explicitly rather than being left blank or guessed.

- **Single-name assets** (individual stocks, crypto, FX pairs, commodity futures): 100%
  in their own category by definition — a single stock's sector/country is a known,
  stable classification fact (matching `backend/scripts/build_dataset.py`'s own
  sector tags), not a measurement. Bond-yield series (e.g. `DGS10`) are marked entirely
  "not applicable" — they're published rates, not holdable assets.
- **SPY, AGG**: real fact-sheet data (State Street, iShares respectively), fetched and
  dated 2026-11-12/11-15.
- **XIU.TO, ESGV, XBB.TO, ZST.TO, QQQ**: geography and asset class filled from the
  fund's stated objective or index rule (same method as SPY's "S&P 500 companies are
  US-domiciled by index rule") — explicitly labelled as objective-based, not fetched
  holdings data. **Sector is marked not available for all five** — that's the one
  dimension objective-based reasoning can't fill in safely.
- **~50 other diversified funds** in the wider universe: not yet covered.

Computed exposure for the three example profiles, as of 2026-11-15 (region / asset
class are now mostly filled, since they come from fund objective for the 5 funds above;
sector remains the main gap, since it still needs real fetched data):

| Profile | Region: known | Sector: known | Asset class: known |
| --- | --- | --- | --- |
| Robert (4) | 100% (Canada 91, US 9) | 21% | 100% (Obligations 70, Actions 30) |
| Mateo (10) | 90% (US 55, Canada 30, no-country 5) | 15% | 100% (Actions 55, Obligations 40, other 5) |
| Amira (13) | 60% (US 28, Canada 23, no-country 9) | 49% | 100% (Actions 80, Obligations 11, other 9) |

Sector's remaining gap is specifically the 5 funds (XIU.TO, XBB.TO, ZST.TO, ESGV, QQQ)
where a real breakdown still needs fetching — not zero, not guessed, just not yet
obtained.

## 7. Limitations and next steps

- **Weekly data smooths over real volatility.** The same scenarios run on daily data
  read slightly higher on both volatility and max drawdown across the board — weekly
  observations miss intra-week swings that daily data captures directly.
- **The backtest window includes 2022**, a real down year — worst-drawdown dates for
  every profile tested fall in 2022, which is informative but also means these numbers
  reflect one specific historical period, not a guarantee of future behavior.
- **Survivorship bias**: the universe is today's list of tickers: companies that
  struggled or were delisted during the window aren't represented.
- **Past performance is not a forecast.** Every backtest number describes what already
  happened to these specific holdings over this specific window — it says nothing
  about what will happen next.
- **Band limits are team assumptions**, not a bank's or regulator's standard — see
  Section 3. They should be defensible in a review, not treated as authoritative.
- **No ESG data exists in the dataset.** The "Responsible (ESG)" style is built from
  ESG-screened fund tickers (ESGV, XESG.TO), not from any controversy/ESG scoring data
  the engine has access to.
- **ESG and home-country preference have no signal in the questionnaire at all** — both
  styles currently require an explicit override rather than being derived from answers.
- **Several fund exposure breakdowns are still missing** (XIU.TO, XBB.TO, ZST.TO, ESGV,
  QQQ sector data; ~50 other funds entirely) — fetch attempts hit JavaScript-rendered
  pages or unresolvable fund IDs; marked "not available," not guessed.
- **`risk.py` (single-asset risk measures) is not yet implemented** — it's a
  deliberate stub, to be written separately.
- **A known edge case**: a request too large to fund from a profile's non-bond holdings
  (e.g. Robert +40% TSLA, where only 30% exists outside bonds) currently returns an
  `INVALID_REQUEST` error instead of a `CONFLICT` with the capped alternative still
  shown — the capped version computes fine internally, but isn't surfaced. Flagged to
  the engine's maintainer; not yet fixed.
- **The wider 116-ticker universe** (including some leveraged ETFs, indices, and FX/
  futures series that aren't appropriate holdings for a buy-and-hold reference
  portfolio) still needs a team decision on final scope before any of it is wired into
  the base profiles.
