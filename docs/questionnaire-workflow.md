# Questionnaire matching and personalized proposals

The backend accepts the supplied 16-question French form and the existing eight-answer
`rendements-seuls-v1` frontend payload. It matches against `profiles.json`, evaluates
allocations with current captured prices, and releases only checked, audited results.
This integration implements reference-template matching. It does not implement a
validated financial-risk-capacity questionnaire or claim investor suitability.

```mermaid
flowchart LR
    JSON[Questionnaire JSON] --> Validate[Validate stable answer IDs]
    Validate --> Match[Match reference templates]
    Match --> Price[Validate assets and price history]
    Price --> Macro[Check macro context for bond assets only]
    Macro --> Evaluate[Evaluate captured prices and constraints]
    Edit[Personalized request and current portfolio] --> Match
    Evaluate --> Evidence[Composition, reasons, trade-offs and limitations]
    Evidence --> Gate[Evidence and release gate]
    Gate --> Audit[Save audit]
    Audit --> Result[Frontend result or checked proposal]
```

## Input contracts

For Lambda console testing, use `action: recommend` with a `request` containing
`questionnaire` and optional `as_of`, `assessment`, and `requirements`. The complete
minimal answered French example is [questionnaire-fr.json](../backend/events/questionnaire-fr.json).
Its financial answers are fictional examples, not an investor record. It is not
an assurance that local market history is complete.

The French `questionnaire` has `langue: fr-CA`, `devise: CAD`, and the supplied
`questions` array. Each choice's `reponse` is its stable option ID, such as
`tolerance_risque_2`, not its translated label. Multiple-choice responses are arrays
of option IDs. Amounts are finite nonnegative JSON numbers. Optional text may be
`null`; answered optional text has a 1000-character limit. The required
`delai_retrait` is read from the horizon's supplementary fields. The blank supplied
form returns `MISSING_INFO / QUESTIONNAIRE_INCOMPLETE` with missing answer IDs.
Client-supplied labels, options, consignes and notes never override backend rules.

A French form can also be sent directly as the HTTP request body (or the direct Lambda event's `request`); the handler wraps it internally. For explicit `as_of`, assessment or requirements fields, use the `questionnaire` wrapper.

The old frontend form remains supported:

```json
{
  "action": "recommend",
  "request": {
    "questionnaire": {
      "version": "rendements-seuls-v1",
      "answers": {
        "risk": "low", "reaction": "concerned", "return": "5_6",
        "horizon": "10", "income": "regular", "sectors": ["technology"],
        "assets": ["stocks", "funds", "bonds"], "exclusions": "none"
      }
    },
    "as_of": "2026-11-12"
  }
}
```

Legacy requests containing `profile_id` and `changes` continue using the existing
workflow without questionnaire matching or the extra metadata input.

## Explicit matching policy

The user approved this mapping for this integration:

| Questionnaire risk | Reference band |
| --- | --- |
| very_low / tolerance_risque_1 | low |
| low / tolerance_risque_2 | low |
| medium / tolerance_risque_3 | medium |
| high / tolerance_risque_4 | high |
| very_high / tolerance_risque_5 | high |

Its identifier is `approved_five_to_three_v1`. An optional explicit
`assessment.risk_band` can carry the teammate risk assessor's `low`, `medium` or
`high` result; its use is disclosed. Desired returns, debts, income, family
situation, emergency funds, experience, horizon and liquidity answers do not
silently change risk bands or become an invented risk-capacity score. They are
retained in the private audit and listed as methodological limitations.

Within that band, the matcher rejects references with unsupported metadata,
unwanted crypto, excluded tickers, or violations of explicit weight requirements.
It ranks the remaining templates by the sum of their weights in interested asset
classes and directly held stocks in interested sectors, using metadata from
`assets_universe.csv`. Preference crosswalks are explicit in
`domain/profile_matching.py`. Interests are not exclusive asset allowlists. The
sector score does not infer ETF constituents. Ties prefer `Broad diversifier`,
then the lowest profile ID. An optional `assessment.preferred_style` restricts to
an exact existing style. Candidates and actual rejection reasons are recorded.
No old `profiles.json.validation` performance figures are used for matching or
release. The matched reference is re-evaluated against captured current inputs.

Structured `requirements` support `excluded_tickers`, `max_asset_weight_pct`, and
`max_crypto_weight_pct`. These do not weaken the reference band's own constraints.
Unresolved activity/ESG exclusions need clarification; missing metadata is not
permission to claim the exclusion was satisfied. No matching candidate returns
`NO_COMPATIBLE_REFERENCE_PROFILE`, with no automatic relaxation or substitution.

## Follow-up requests

Use `action: personalize` (or `POST /chat` through an existing HTTP adapter) with
the same questionnaire and the current `portfolio` in the returned frontend format.
Its position weights are percentages totaling 100. The backend ignores supplied
names/categories and re-resolves identifiers and metadata from its own snapshot.
Every proposed allocation and the submitted baseline are re-evaluated; the client
does not supply trusted risk metrics. Omitting `portfolio` starts from the matched
reference, which is disclosed in the evidence.

Add either a `message` or structured `changes`, never both:

```json
{ "message": "Ajouter NVIDIA 5%" }
```

```json
{ "changes": [{ "ticker": "NVDA", "add_pct": 5 }] }
```

These fragments are fields of the full request, not standalone requests.
Messages support a bounded, deterministic grammar: one exact dataset name or
ticker, with a whole percentage-point addition/reduction, or an explicit exclusion.
An amount-only reply may use the latest user message's exact asset; assistant text
is not trusted for this purpose. Missing amounts ask for clarification, rather
than inventing an allocation. Ambiguous, negated and target-total instructions
require clarification or structured changes. This is not an unrestricted chat or
financial-advice agent.

An addition is an **additional number of percentage points**, not a target total.
It uses the existing proportional non-bond funding policy. Whole-point rounding
may assign a residual to the largest reference bond holding; the actual effect is
reported. An oversized unfundable edit is invalid. An evaluable policy conflict
reports the requested conflict and releases a capped alternative only if every
implemented check passes. Conditional searched maxima are limited to the requested
range and cannot be combined as independent promises.

Both asset metadata and usable price history are required. Indices, bond yields,
FX and commodity-futures reference series are not supported portfolio holdings in
this simulation, even when their prices exist. An unresolved outside asset, missing
history, incompatible currency or unsupported constraint gets an honest error or
clarification, without a fabricated replacement or released allocation.

## Bond macro information after asset validation

After confirming supported asset membership and price history, the workflow checks
the dataset asset classes. Only evaluated bond assets (`etf_bond` in this universe)
trigger a read of `macro_rates.csv` through the snapshot source. Equities and other
supported assets are verified in `prices_weekly.csv`; their verification does not
require macro data. Bond ETFs still require prices for valuation and returns.
When bonds are present, the workflow records its exact-byte hash and
version/reference window, and checks `date, series_id, value, unit, frequency,
label, source`. Values must be finite; negative rates are valid. Duplicate
series/date rows and inconsistent units or frequencies are rejected. Missing,
invalid or wholly unavailable macro context stops a questionnaire workflow that evaluates bonds
without releasing a portfolio. A portfolio with no evaluated bond assets skips macro loading. An unknown asset is rejected before macro loading. When an equity addition is assessed in a portfolio containing bonds, macro context is explicitly scoped to those bonds, not to the equity.

The response reports the latest reference observation for each series on or
before the requested as-of date, with source, units, frequency and reference date.
These are economy-wide series used only as bond context, not equity or other asset-class forecasts. `applies_to_tickers` lists the evaluated bond assets; the release gate rejects macro context scoped to a non-bond asset. An optional
`release_date` column excludes observations released after the as-of date; absent
release dates remain explicitly unverified. The supplied file has no publication
dates and contains revised values. Therefore reference dates cannot certify
historical availability. No values are filled, and no macro-to-weight causal rule
or trading signal is invented. Macro facts contribute cited context and explicit
limitations, while allocations still follow the documented profile/funding rules.
Changing macro bytes changes audit/evidence identity even when weights stay equal.

## Output and release

Direct Lambda calls retain `status`, `run_id`, `assessment`, `profile_match`, the
detailed evidence bundle, and `audit_saved`. A passing portfolio also includes a
`recommendation` in the existing frontend contract:
`runId`, `portfolio {id, name, positions}`, `explanation`, evidence descriptions,
limitations, and `compliance`. Each position uses dataset names, classifications
and evaluated weights. The evidence explains matching, actual weight changes,
applied caps, funding, rounding, and historical metrics. It does not assert company
fundamentals, optimal suitability or future-return advantages.

For an HTTP `POST /portfolio`, the handler returns that frontend recommendation
only after release and audit succeed. For `POST /chat`, it returns `message` plus
an optional checked `proposal`. Clarifications and unsupported assets have no
proposal. Acknowledging a proposal remains a frontend action; the backend places
no trades. Failed audit storage blocks portfolio release on both routes.

Bedrock may only order supplied verified statements. The existing shared limit
of two repairs and one checked deterministic fallback is preserved. New numerical,
matching, and allocation rules never depend on model arithmetic or outside facts.

## Inputs and deployment

Questionnaire/personalization requests evaluating bonds capture five files from the same local
folder or configured S3 prefix:

```text
prices_weekly.csv
fx_usdcad_daily.csv
profiles.json
assets_universe.csv
macro_rates.csv
```

The extra metadata file is mandatory for new questionnaire requests. The macro file is
required only when evaluated holdings or requested edits include bond assets. All consumed
files are hashed in the audit manifest. Macro loading occurs only after asset membership
and required price history/cadence checks succeed. Legacy explicit-profile requests still need only the first
three files. Independent reads are not an atomic dataset release; use coherent
versioned inputs. For the existing deployment, upload
`dataset/assets_universe.csv` to `data/assets_universe.csv` and
`dataset/macro_rates.csv` to `data/macro_rates.csv`. Permit reading both objects
in the Lambda runtime policy. Rebuild/deploy the backend code.
This implementation does not modify AWS resources or create a public HTTP
endpoint. The frontend proxy needs an existing authenticated HTTP adapter, not a
Lambda ARN, in `PORTFOLIO_API_URL` and `AGENT_API_URL`.

Test locally from the repository root:

```powershell
python backend/scripts/run_workflow.py --event backend/events/questionnaire-fr.json
python -m pytest backend/tests -q
```

The supplied market snapshot still lacks reference holdings, so the real-data
example can report `MISSING_HOLDING_HISTORY`. Synthetic controls establish the
working workflow; they are not live investor or market validation.

## Shared stages instead of per-profile agents

Keep a shared matcher, portfolio evaluator, evidence builder and explanation
stage, with the 15 profiles as data. Dedicated model agents for each profile
would duplicate identical constraints, drift in policy and complicate comparison
without adding new evidence. Separate specialists are useful when they own
different methods or tools, such as data validation versus explanation, rather
than copies of the same logic with a different portfolio name.

## Implementation handoff

Inputs are the supplied French contract, the approved risk mapping, unchanged
reference profiles and source datasets. Local implementation checks passed:
189 backend tests, with 10 skipped and 2 expected failures, plus 17 subtests;
the frontend response validator ran from the integration tests, all three changed
JavaScript modules passed syntax checks, and routing/lesson structure passed.
These are deterministic checks, not independent review or a live deployment.

| Role | Task and output artifacts | Status | Next owner |
| --- | --- | --- | --- |
| Data | Questionnaire normalization, universe/price validation and bond macro parsing in `questionnaires.py` and `workflow_storage.py` | Complete locally; real reference history incomplete | Dataset owner: supply missing XBB.TO, XIU.TO and ZST.TO history |
| Screening | Dataset eligibility, explicit exclusions and preference matching in `profile_matching.py` | Complete | Integration maintainer |
| Risk | Approved risk-band mapping and explicit constraints; financial-risk-capacity scoring remains outside this implementation | Complete within agreed scope | Questionnaire team for any broader assessment model |
| Portfolio | Current-weight proposals and caps in `investor_workflow.py` and `proposals.py` | Complete | Integration maintainer |
| Backtest | Existing weekly evaluation reused for each proposal through `portfolio_engine.py` | Complete locally | Dataset owner before real-data acceptance |
| Evidence | Sourced composition, changes and bond-only macro facts in `evidence.py` | Complete | Integration maintainer |
| Explanation | Verified rationale and bounded fallback reused; no per-profile model agents | Complete | Integration maintainer |
| Compliance | Dataset, scope, evidence and audit release gates exercised by integration tests | Complete locally | Integration maintainer for live acceptance |
| Infrastructure | Snapshot ports, Lambda routes, local runner and frontend proxy integration | Complete locally; AWS unchanged | Deployment owner: upload new inputs, grant reads, rebuild and deploy |
