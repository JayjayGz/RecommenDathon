# Deterministic portfolio review and optional alternatives

Questionnaire and follow-up evaluations now run `REVIEW_PORTFOLIO` and
`CHECK_SUGGESTIONS` after the engine evaluation and before evidence/explanation.
The review uses the selected passing branch, or the requested allocation when
neither branch passes. It does not change the selected weights.

## Structured findings

`portfolio_analysis.review` includes:

- Reference profile, approved risk-band mapping, template asset-class split and
  starting-weight origin. Individual weights come from `profiles.json` or the
  submitted portfolio and existing proposal rules; they are not optimized.
- Evaluated asset-class percentages and listing-currency percentages. Listing
  currencies do not establish the underlying economic currency exposure.
- Direct-stock sector weights, covered percentage and unclassified percentage.
  ETF constituents and overlap are absent from the dataset; ETF category labels
  are not used as a sector look-through. Unclassified is not a sector.
- Holding count, largest position, holding HHI (`sum(weight_fraction ** 2)`)
  and effective holding count (`1 / HHI`). These describe listed positions,
  not the number of underlying securities or independent risk exposures.
- Historical growth, volatility and maximum drawdown, with the actual common
  dates, observation count, cadence, annualization, rebalancing and CAD convention.
- Every existing policy check and its observed value, limit and pass/fail result.
  Unequal weights are observations; the review invents no concentration threshold
  or investor suitability score.

The domain functions in `domain/portfolio_review.py` perform no I/O or model calls.
The Application module of the same name drives the existing `PortfolioEngine`
against its captured snapshot.

## Bounded alternatives

The current supported objective is reducing **holding-level concentration**.
For each asset class with unequal held weights, the search proposes independent
1, 3 and 5 percentage-point edits from the largest position to the smallest,
without passing their equal-weight point. Classes are searched by descending
weight gap, then class name; ticker order breaks position ties. The search
evaluates at most six candidates and returns at most two, one per issue/class.
It uses held assets only and does not search the whole universe.

`PortfolioEngine.evaluate_candidate()` applies the existing funding and rounding
rules without cap rewriting or another nested search. The *resulting* weights,
including any proportional funding or rounding effects, must:

1. Pass all existing band, crypto, gold, single-stock, exclusion and explicit
   user constraints, using the same limits.
2. Preserve the exact asset-class totals and introduce no new holding.
3. Reduce both overall holding HHI and the largest weight within the issue's
   asset class.
4. Use the same captured input manifest, backtest dates, cadence, annualization,
   CAD conversion and rebalancing convention.
5. Have no worse historical volatility or maximum drawdown **at the engine's
   reported precision**. Historical growth may fall; that trade-off is reported.

Every attempted candidate and rejection code is saved in private
`decisions.json`. Public responses contain only qualifying alternatives plus
search status and counts. No qualifying candidate is a valid result; it is not
evidence that no improvement exists elsewhere. Below 45 seconds of remaining
workflow budget, optional search stops as `budget_limited`; the final audit
reserve remains in place. A run without a passing portfolio does not search.

Alternatives are independent and have `applied: false`. They are not automatically
combined or applied. Same-class transfers can change duration, geography or other
underlying exposures which this dataset does not quantify. Lower holding HHI
does not prove better economic diversification, suitability or future returns.
This is a bounded historical comparison, not an optimal allocation claim.

## Evidence, explanation and release

Evidence method `proposal_evidence_v3_portfolio_review` adds `review.*`,
`suggestion.search` and `suggestion.C*` claims before any explanation call.
Every claim carries the input-manifest hash. Before release, deterministic checks
rebuild the review, search plans, rejection reasons and qualifying selection.
Changed review facts, provenance or suggestions fail the release gate.

The optional Bedrock call can order all verified claim IDs. Python renders their
vetted sentences and mandatory limitations. It cannot supply new calculations,
pass/fail decisions or investment claims. The existing shared two-repair budget,
checked fallback and audit-before-release requirement remain enforced.

Workflow version is `proposal_workflow_v3_review`. The frontend recommendation
exposes `analysis.review`, `analysis.search`, `analysis.suggestions` and evidence
IDs through its proxy and normalizer. Existing explanation/source displays carry
the review narrative. There is no automatic apply action; a chosen alternative
must be submitted for a fresh evaluation and explanation.

## Reproducible local example

Run `python scripts/check_pipeline_e2e.py --as-of 2026-11-15` to use the supplied
French example and actual CSVs through the local Node proxy and Lambda handler.
The response is saved in `.local-runs/e2e-verification/initial-response.json`;
the report records the audit directory. No AWS or live model call is made.

The low-band Broad diversifier example starts with XBB.TO 45%, ZST.TO 25%,
XIU.TO 15%, SPY 15%. The search evaluated three candidates and returned the
five-point XBB.TO-to-ZST.TO alternative:

| Metric | Selected portfolio | Optional alternative |
| --- | ---: | ---: |
| XBB.TO | 45% | 40% |
| ZST.TO | 25% | 30% |
| XIU.TO / SPY | 15% / 15% | 15% / 15% |
| Bond ETFs / equity ETFs | 70% / 30% | 70% / 30% |
| Holding HHI | 0.310 | 0.295 |
| Historical annual growth | 5.4% | 5.5% |
| Historical annualized volatility | 5.4% | 5.2% |
| Historical maximum drawdown | -10.7% | -10.1% |

Both simulations use 261 weekly observations, 2021-11-19 through 2026-11-13,
monthly rebalancing and CAD values. All eight implemented checks pass for the
alternative. This ETF-only example reports 0% direct-stock sector coverage and
100% unclassified underlying sectors; it does not fabricate a sector split.

## Development handoff

Inputs: unchanged source CSVs and profiles, existing questionnaire and proposal
contracts, captured manifest and policy checks. Router owns integration.

| Role | Output | Status and next owner |
| --- | --- | --- |
| Portfolio / screening | Pure findings and bounded held-asset plans; exact candidate engine evaluation | Complete; integration maintainer |
| Data / risk / backtest | Reused snapshot, historical metrics, conventions and unchanged constraint limits | Complete within existing engine precision; data owner for ETF look-through if later requested |
| Evidence / compliance | Review provenance, candidate acceptance and release reconstruction | Complete; integration maintainer |
| Explanation | Vetted review, rationale and trade-off claims under existing model/fallback bounds | Complete; explanation maintainer |
| Infrastructure | Audited stage wiring and frontend result preservation | Complete locally; deployment owner for live AWS acceptance |

Checks are deterministic development checks, not independent review or a live
deployment. See the connected report and `backend/tests/test_portfolio_review.py`.
The complete backend suite passed 255 tests, with 2 skips, 2 expected failures
and 17 passing subtests. The connected local runner passed 20 checks across 14
audited real-data runs. The local Node HTTP test and changed JavaScript syntax
checks also passed; graphical browser rendering and live Bedrock were not tested.
