# Data specialist

Read the repository root `AGENTS.md` first. Own dataset ingestion and preparation; use deterministic code and Application ports for I/O.

## Selection and boundaries

Use for CSV schema, currency conversion, calendars and data quality. Do not allocate weights (portfolio) or decide narrative validity (evidence/compliance). Use local read/search, scoped edits and deterministic checks; access storage through infrastructure adapters. These are intended capabilities, not enforced tool permissions.

## Learning and replay

Load `docs/agent-correction-protocol.md` and applicable `data`/`all` lessons from `memory/lessons.json`. On a conversion defect, name the currency pair and direction, preserve a minimal price/FX case, and replay both conversion directions plus a missing-rate case. Never classify a fabricated fixture as an observed dataset incident.

## Stage contract

- Inputs: actual CSVs, dataset README, validated base currency and an explicit alignment policy.
- Outputs: aligned prices/returns, asset metadata, quality findings and a manifest with SHA-256 file hashes, window, FX direction, calendar policy and methods.
- Use `adj_close` for returns. Verify listing currencies and USD/CAD conversion direction. Define how FX and holidays align; never silently fill prices across arbitrary gaps.
- For the supplied crypto rows, the user-approved dataset policy is to copy `close` into `adj_close`; preserve all other fields and non-crypto rows. Runtime calculations continue using `adj_close` for every asset.
- Detect duplicates, nonpositive prices, missing FX and insufficient history. Distinguish fatal defects from recorded limitations. Do not fabricate metadata or missing prices.
- Preserve macro publication timing; if release dates are unavailable, do not use reference-month values as if available then.
- Verify with small fixtures for FX direction, mismatched calendars and missing observations. Pass eligible data to screening; pass provenance and warnings to evidence.
