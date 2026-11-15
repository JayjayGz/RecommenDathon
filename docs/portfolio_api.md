# PortfolioEngine: calculation API for agents

The engine computes weights, historical metrics and profile-rule decisions in Python. Agents explain its outputs; they do not calculate returns, invent reasons or override the verdict. `backend/src/alphaforge/application/risk.py` remains a separate, unimplemented per-ticker module owned by the teammate.

Weights are fractions summing to one. Changes use whole percentage points: `add_pct: 5` adds five points to the existing holding; it does not set the holding to 5%. Fractional changes, NaN, infinity and booleans are rejected explicitly. The engine uses the team's whole-percent rounding rule. `profiles.json` is read-only.

## Wiring and imports

```python
from alphaforge.bootstrap import create_engine
engine = create_engine()
```

The operations below are methods of `engine`, implemented in `backend/src/alphaforge/application/portfolio_engine.py`. For custom storage, construct `PortfolioEngine(repository)` using the `PortfolioRepository` port. Root-level Python modules have been removed; update existing imports. `data_dir=None` resolves to the repository's `dataset/`, and `profiles_path=None` to its `profiles.json`. The active price filename is `prices_daily.csv`. Explicit paths override these defaults. See [data compatibility](DATA.md): the current file lacks 13 legacy profile tickers, so affected assessments return `MISSING_INFO`.

## get_profile(profile_id, profiles_path=None)

Returns a copy of one reference profile's `id`, `band`, `style`, `crypto_allowed` and `weights`. The ID must be an integer matching a configured profile. Evaluating a proposal does not change the stored profile.

## apply_changes(profile, changes, ...)

Returns `{"weights": ..., "notes": ...}` after applying caps. This transforms weights; it does not establish historical risk fit. Call `evaluate` for the complete agent-facing assessment.

Supported changes:

```python
[{"ticker": "TSLA", "add_pct": 20}]
[{"exclude": "ENB.TO"}]
```

Caps remain existing team assumptions: single-stock limits come from `profiles.json`; combined crypto and GLD limits come from `EXTRA_CAPS`. Crypto also requires the profile's permission flag. Redistribution can cause another holding to exceed a limit, so a capped candidate must still pass `validate`.

Funding comes proportionally from other non-bond holdings. Direct changes to protected bonds are unsupported, including liquidating bonds to buy stocks. Exclusions redistribute within the same bond/non-bond group; excluding its final holding is rejected. The rounding residual still goes to the largest bond, with a note when this changes bond weights.

Unknown tickers, malformed changes, insufficient funding and unsupported operations raise `ProposalError` with a stable `code`. They are not silently skipped. No negative weights, shorting or leverage is introduced to satisfy a request. A list with an invalid member is rejected as a whole; no partial proposal is returned.

## validate(weights, band, ..., crypto_allowed=None)

```python
validate(weights, band, start=None, end=None, rebalance="monthly",
         data_dir=None, profiles_path=None,
         crypto_allowed=None)
```

Checks long-only, finite weights summing to one before backtesting. All required policy checks contribute to the verdict:

- Historical volatility and maximum drawdown limits.
- Largest single-stock weight.
- Combined BTC/ETH weight and crypto permission.
- GLD weight.

If crypto is held but the caller omits `crypto_allowed`, the verdict is `MISSING_INFO`. With no crypto held, an omitted flag does not block assessment. `evaluate` always supplies the selected profile's flag.

Returns metrics plus:

| Field | Meaning |
| --- | --- |
| `status` | `PASS`, `CONFLICT`, `INVALID_REQUEST`, or `MISSING_INFO` |
| `passes` | True only after all required checks pass |
| `checks` | Each rule's value, limit and pass result; missing information may use null |
| `reasons` | Failed/unknown rule records for successfully calculated assessments |
| `errors` | Error codes/messages for invalid or unavailable assessments |
| `period` | Actual first/last observation dates and observation count |
| `currency` | CAD |
| `rebalance`, `method` | Historical calculation method |

Invalid weights are not backtested. Missing files, unavailable asset history or fewer than three usable observations return `MISSING_INFO`, without fabricated risk numbers. The default window remains the last five years available in the dataset; mixed holdings use common observation dates. These historical measures are not future-loss guarantees.

### Corrected monthly method

`monthly_first_observed_close_v2` values existing units at the first common observed close of the new month, then rebalances to target weights. It preserves the return since the previous month's last close. Buy-and-hold uses `buy_and_hold_v1`.

The old implementation discarded that boundary return. Stored validation metrics, trimming decisions and pass flags in `profiles.json` are therefore stale until regenerated using the agreed private CSVs. Synthetic tests establish accounting correctness, not corrected real-market results. The previous API's numerical examples must not be cited as current measurements.

## evaluate(profile_id, changes, ...)

```python
result = engine.evaluate(4, [{"ticker": "TSLA", "add_pct": 20}])
```

This is the main function agents should call:

| Field | Meaning |
| --- | --- |
| `base` | Original profile weights with freshly computed validation |
| `as_requested` | Requested changes without applying policy caps |
| `adjusted` | Separate capped candidate with its own validation; passing is not guaranteed |
| `status` | Verdict for `as_requested`, never replaced with the adjusted verdict |
| `outside_profile` | True for `CONFLICT`, false for `PASS`, null when invalid or unevaluable |
| `notes` | Adjustments, unsupported operations and rounding explanations |
| `max_allowed` | Feasible additional whole points, searched without capping trials |

Each evaluable scenario has `weights` and `validation`. If a raw request cannot be funded, its weights are null with a structured error; a separately feasible capped alternative may still be returned. Malformed/unknown requests fail before scenario calculation: `base` and `adjusted` are null. Data unavailability returns `MISSING_INFO`.

`max_allowed` is searched only for a `CONFLICT` and only up to the requested amount. With several changes, it varies one addition while keeping every other requested change fixed. These conditional maxima must not be combined into a supposedly approved portfolio. Repeated additions to one ticker omit that ambiguous maximum. Null means no passing trial was found, including zero; zero means the zero-addition trial actually passed.

Example using **fabricated flat prices**: Robert's low-band profile plus a 20-point TSLA addition returns `CONFLICT`; raw TSLA weight is 20%, the capped candidate is 5%, and `max_allowed.TSLA` is 5 additional points if the rest of the scenario passes. Real prices can lower that feasible maximum. The earlier value of 20 referred to a request already clamped to the cap; that interpretation is no longer used.

A `CONFLICT` is a valid result for the UI to explain. The release gate must check that the explanation accurately describes the failed proposal and the alternative's separate verdict. It must not hide the conflict or request prose retries to change computed facts.

## Verification and regeneration

Run the offline suite with the project interpreter:

```powershell
..\.venv\Scripts\python.exe -m pytest tests -q
```

Synthetic regressions cover month-boundary gains/losses, hand-computable rebalancing, policy conflicts, invalid requests and valid controls. Dataset integration tests explicitly skip when the local reference universe is absent or incomplete. Once the team has the agreed data, regenerate reference portfolios with `python backend/scripts/build_portfolios.py dataset profiles.json`, review changed metrics/allocations, and rerun the dataset tests. This overwrites the generated output; regeneration was not performed during this correction.
