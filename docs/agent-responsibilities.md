# Agent Responsibilities

For coding-request routing, see the repository root `AGENTS.md` and [file-based workflow](agents-workflow.md). Those development roles guide implementation of the application agents below. The workflow also specifies one shared retry budget, a checked template fallback and structural-failure routing, clarifying the retry descriptions below.

This document describes the target runtime pipeline; see `architecture.md` for implemented modules and remaining gaps. Agents live in the Application Layer. Each has one job, a typed input and output, and calls Domain functions for any calculation. The LLM (Bedrock) is used only for language tasks: interpreting the investor and writing the explanation. It never does arithmetic.

## Ownership

| Part | Owner | Notes |
| --- | --- | --- |
| Questionnaire UI and validated financial-risk-capacity assessment | Teammates | The broader normalized contract remains `investor-profile-schema.json`. |
| Backend reference-template matching and personalization | This repo, at the user's request | See `questionnaire-workflow.md` for actual raw JSON contracts, approved risk mapping and limitations. |
| Recommendation pipeline, evidence, trade-offs, limitations, compliance gate, audit trail | This repo | Described below. |

Personas will be added later as predefined `InvestorProfile` examples. They are plain input files, so the pipeline needs no change.

## Pipeline agents

For post-questionnaire additions, the screening step first resolves the requested
name or ticker in `assets_universe.csv` and checks whether its asset class is
supported. Unknown or unsupported holdings stop before engine calls. The data
step validates `prices_weekly.csv` for the requested asset and current holdings,
and loads `macro_rates.csv` context only for evaluated bond ETFs. Bond ETFs still
need prices. The deterministic engine then checks the proposed allocation and its
portfolio impact under the existing policy; an LLM does not calculate metrics or
override a rejected change. See [the implemented request flow](questionnaire-workflow.md#follow-up-requests).

| Agent | Uses LLM | Responsibility | Output |
| --- | --- | --- | --- |
| Data Agent | No | Load the CSVs, convert currency, align calendars, record the method used | Clean return matrix and data manifest |
| Screening Agent | No | Apply the profile's exclusions and limits (sectors, tickers, asset classes, crypto cap) | Eligible assets, plus a reason for each excluded asset |
| Risk Agent | No | Compute volatility, drawdown and correlations for candidates | Risk metrics |
| Portfolio Agent | No | Build weights that fit the profile's risk level and constraints. Record the alternatives it rejected and the rule that rejected each | Weights, `rejected_alternatives` |
| Backtest Agent | No | Simulate the portfolio over the data window | Performance series and metrics |
| Explanation Agent | Yes | Write the rationale and trade-off narrative using only the Evidence Bundle | Text where every claim cites evidence IDs |
| Compliance Gate | Partly | Final check before anything is shown (see below) | Pass or fail, with reasons |

Only the Explanation Agent needs the LLM in this pipeline. Everything else is deterministic Python, which keeps runs fast, repeatable and testable.

## Evidence-grounded explanations

1. The Domain Layer builds an **Evidence Bundle**: a map of evidence ID to value, with its source file, data window and calculation method. Example: `E12: {metric: "max_drawdown", asset: "XIU.TO", value: -0.147, source: "prices_daily.csv", window: "2021-11-12..2026-11-12", method: "adj_close"}`.
2. The Explanation Agent receives the bundle and the profile, nothing else. It must tag each factual claim with an evidence ID.
3. A validator (plain code) checks that every cited ID exists, and that every number in the text matches a bundle value after rounding. Any unmatched number fails validation.
4. On repairable failure, the orchestrator retries the Explanation Agent with structured errors, at most 2 times total across evidence and wording checks. After that it falls back once to a template-based explanation built directly from validated evidence. The fallback must pass the same Compliance Gate; otherwise the run returns an explicit error. Missing or invalid calculated evidence stops the run rather than triggering prose repair.

Evidence IDs will depend on the actual input CSVs listed in `dataset/README.md`. Evidence generation remains planned; the bundle format should stay the same when data changes.

## Trade-offs

Trade-offs come from the Portfolio Agent's own decision records, not from the LLM's imagination. For each rejected or reduced asset it stores the rule and the numbers, for example "TSLA excluded: volatility E31 exceeds the limit implied by risk level E02". The Explanation Agent narrates these records and cites their evidence IDs.

## Limitations

A **Limitations Registry** in the Domain Layer produces the limitations list in code, so the LLM cannot omit or soften it. It combines:

- Fixed items from the dataset README: survivorship bias, prices in listing currency with USD/CAD conversion, calendar alignment method, `adj_close` back-adjustment, monthly macro data dated by reference month not release date, no ESG scores or fundamentals in the data.
- Data-derived items: the actual data window, assets with missing or short history, and anything listed in `data_quality_warnings.txt`.

The list is attached to every result next to the recommendation.

## Compliance Gate

The gate is the last step, and nothing reaches the user without passing it. It checks:

1. Evidence validation passed.
2. Required disclaimer ("simulation, not investment advice") and the limitations list are present.
3. No advice-style or guarantee wording (rule list, plus an optional LLM check).
4. The portfolio respects the profile's constraints (asset weights, crypto cap, exclusions).

Repairable explanation issues go back to the Explanation Agent within the shared budget of 2 retries. Exhaustion triggers one template fallback, checked by the same gate without further retries. Structural data or constraint failures stop immediately. A failed fallback returns an explicit error instead of a partial result.

## Audit trail

Each run writes to S3 under `runs/{run_id}/`:

| File | Content |
| --- | --- |
| `profile.json` | The input `InvestorProfile` |
| `data_manifest.json` | CSV file names, SHA-256 hashes, data window, alignment and conversion methods |
| `evidence.json` | The Evidence Bundle |
| `decisions.json` | Screening exclusions and the Portfolio Agent's rejected alternatives |
| `llm_calls.json` | Model ID, prompts, raw responses, retry count |
| `compliance.json` | Gate result for each attempt |
| `result.json` | Final recommendation, explanation and limitations as shown to the user |

Writes go through an `AuditStore` port in the Application Layer. The S3 adapter lives in the Infrastructure Layer, and a local-folder adapter can be used for development.

## Rules for all agents

1. Inputs and outputs are validated against typed models. Invalid output is rejected, not passed on.
2. No agent calls infrastructure directly. It uses ports defined in the Application Layer.
3. A failed agent returns an explicit error. The orchestrator stops and reports it instead of continuing with partial data.
4. Every agent's output is recorded in the audit trail.

## Orchestration

A plain Python orchestrator in the Application Layer runs the steps in the order shown in `pipeline.mmd`, inside one Lambda function. No Step Functions. Set the Lambda timeout to roughly 60 to 120 seconds.
