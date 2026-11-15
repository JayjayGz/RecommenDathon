# portfolio_engine.py — API for agents

`portfolio_engine.py` is the deterministic calculation layer. Plain Python, no LLM
calls, no network. Agents call these functions as tools and explain the results;
they never compute numbers themselves. `risk.py` (stub, not yet implemented) is a
companion module for per-ticker risk measures.

All weights are fractions (sum to 1), rounded to whole percent internally. All
prices are in CAD. `profiles.json` is read-only — nothing here writes to it.

## get_profile(profile_id, profiles_path="profiles.json")

Loads one of the 15 base profiles.

**Input:** `get_profile(4)`

**Output:**
```json
{
  "id": 4,
  "band": "low",
  "style": "Income and stability",
  "crypto_allowed": false,
  "weights": {
    "XBB.TO": 0.45, "ZST.TO": 0.25, "XIU.TO": 0.09,
    "RY.TO": 0.03, "TD.TO": 0.03, "FTS.TO": 0.03,
    "ENB.TO": 0.03, "PG": 0.03, "JNJ": 0.03, "JPM": 0.03
  }
}
```

## apply_changes(profile, changes, data_dir="alphaforge_starter", profiles_path="profiles.json")

Applies a list of proposed changes **with band caps enforced**. Caps: single-stock
(from `profiles.json`'s `band_limits`), gold (GLD), and crypto (BTC-USD+ETH-USD
combined, requires `crypto_allowed`): low 5/10/0, medium 10/15/3, high 15/15/10
(percentage points). Bonds (XBB.TO, ZST.TO, AGG) are protected — a change is
funded from, or given back to, the other holdings proportionally, never bonds.
`{"exclude": ticker}` removes a holding and redistributes its weight within its
own group (bonds or non-bonds). An unknown ticker is not applied, with a note,
and its ticker is listed in `unsupported` — treat any non-empty `unsupported`
list as "this request could not be fully evaluated," not as a pass. A requested
change can never exceed what the non-bond holdings can actually fund (or go
below 0%) — if it would, it's clamped to what's feasible, with a note.

**Input:**
```json
{"profile": "<Robert, profile 4>", "changes": [{"ticker": "TSLA", "add_pct": 20}]}
```

**Output:**
```json
{
  "weights": {
    "XBB.TO": 0.48, "ZST.TO": 0.25, "XIU.TO": 0.08,
    "RY.TO": 0.02, "TD.TO": 0.02, "FTS.TO": 0.02, "ENB.TO": 0.02,
    "PG": 0.02, "JNJ": 0.02, "JPM": 0.02, "TSLA": 0.05
  },
  "notes": ["TSLA: requested 20%, applied 5% (low band single-stock cap)"],
  "unsupported": []
}
```
(XBB.TO moved from 45% to 48% here — that's `build_portfolios.round_weights()`'s
"leftover to the largest bond" rounding fix-up, not a change caused by TSLA.)

## validate(weights, band, crypto_allowed=True, start=None, end=None, rebalance="monthly", data_dir="alphaforge_starter", profiles_path="profiles.json")

Backtests a weight set and checks it against five things: the band's three
limits from `profiles.json` (volatility, drawdown, single-stock), plus gold and
combined-crypto caps (team assumptions, not in `profiles.json`). Pass the
profile's `crypto_allowed` flag explicitly — it defaults to `True` (permissive)
only for callers that don't have a profile to check against; `evaluate()` always
passes the real flag, so a crypto position on a profile that doesn't allow
crypto fails here even if volatility/drawdown alone would have passed.
Default period: last 5 years of data in `data_dir`. Default rebalance: monthly,
back to target weights.

**Input:** `validate(<Robert's base weights>, "low", crypto_allowed=False)`

**Output:**
```json
{
  "annual_growth_pct": 5.6,
  "volatility_pct": 4.7,
  "max_drawdown_pct": -9.4,
  "worst_drawdown_date": "2022-10-12",
  "end_value": 13031.0,
  "checks": {
    "max_volatility_pct": {"limit": 7, "value": 4.7, "passes": true},
    "max_drawdown_pct": {"limit": -15, "value": -9.4, "passes": true},
    "max_single_stock_pct": {"limit": 5, "value": 3.0, "passes": true},
    "max_gold_pct": {"limit": 10, "value": 0, "passes": true},
    "max_crypto_pct": {"limit": 0, "value": 0, "passes": true}
  },
  "passes": true
}
```

## evaluate(profile_id, changes, data_dir="alphaforge_starter", profiles_path="profiles.json")

**The one function agents should call.** Runs the proposal three ways — base
(untouched), as-requested (no caps, to see if the raw request fits), adjusted
(caps applied) — validates each, and reports whether the raw request was outside
the profile, plus the largest whole-percent add that would still pass.

**Input:** `evaluate(4, [{"ticker": "TSLA", "add_pct": 20}])` (Robert + TSLA 20%)

**Output:**
```json
{
  "base": {
    "weights": {"XBB.TO": 0.45, "ZST.TO": 0.25, "XIU.TO": 0.09, "RY.TO": 0.03,
                "TD.TO": 0.03, "FTS.TO": 0.03, "ENB.TO": 0.03, "PG": 0.03,
                "JNJ": 0.03, "JPM": 0.03},
    "validation": {"annual_growth_pct": 5.6, "volatility_pct": 4.7,
                   "max_drawdown_pct": -9.4, "worst_drawdown_date": "2022-10-12",
                   "end_value": 13031.0, "passes": true, "checks": "..."}
  },
  "as_requested": {
    "weights": {"...": "...", "TSLA": 0.2},
    "validation": {"volatility_pct": 12.4, "max_drawdown_pct": -22.3,
                   "passes": false, "checks": "..."}
  },
  "adjusted": {
    "weights": {"...": "...", "TSLA": 0.05},
    "validation": {"volatility_pct": 5.7, "max_drawdown_pct": -10.9,
                   "passes": true, "checks": "..."}
  },
  "notes": ["TSLA: requested 20%, applied 5% (low band single-stock cap)"],
  "unsupported": [],
  "outside_profile": true,
  "max_allowed": {"TSLA": {"requested_pct": 20, "realized_pct": 5.0}}
}
```

`max_allowed.TSLA.requested_pct` is 20 (the original request), not 5:
once the single-stock cap clamps TSLA to 5% (`realized_pct`), the *capped*
portfolio already passes every band limit, so the full requested amount is
fine to send through `apply_changes` — the cap is what makes it fit.
`outside_profile` is true because the *raw, uncapped* request would not have
fit on its own; that's the signal that the user's request needed adjustment,
not a verdict on the adjusted portfolio. Read `requested_pct` as "the largest
number the user could have typed," and `realized_pct` as "what they'd actually
end up holding" — they are deliberately different numbers.

If `unsupported` is non-empty (an unknown ticker), treat the whole result as
unevaluated for that ticker, not as a pass — `outside_profile` can still be
`False` in that case because nothing changed, which is not the same as "fits."

## risk.py — risk_measures(ticker, start=None, end=None, data_dir="alphaforge_starter")

Stub only (not yet implemented; calls currently raise `NotImplementedError`).
Will return `volatility_pct`, `max_drawdown_pct`, `annual_growth_pct`,
`years_of_data`, `first_date`, `last_date` for a single ticker, in CAD. See the
docstring in `risk.py` for exact definitions.
