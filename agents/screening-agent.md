# Screening specialist

Read the repository root `AGENTS.md` first. Own deterministic eligibility rules.

## Selection and boundaries

Use for eligibility and exclusions. Do not assess questionnaire risk (teammates) or implement aggregate weight caps (portfolio). Use local read/search, scoped edits and deterministic checks; do not fetch outside metadata to disguise missing inputs. These are intended capabilities, not enforced tool permissions.

## Learning and replay

Load `docs/agent-correction-protocol.md` and applicable `screening`/`all` lessons from `memory/lessons.json`. For an ignored exclusion, preserve the profile, metadata reference and expected eligible set; replay the offending exclusion and an allowed asset. Missing metadata must remain explicit rather than becoming an invented classification.

## Stage contract

- Inputs: validated profile, prepared universe and sourced asset metadata.
- Outputs: eligible assets, excluded assets with rule IDs and reasons, unsupported constraints and feasibility findings.
- Apply ticker, sector and asset-class restrictions only using available metadata. Unsupported ESG requirements need an explicit unsupported-constraint result; never silently ignore them.
- A portfolio crypto weight cap is an allocation constraint, not a blanket crypto exclusion unless the cap is zero. Pass aggregate caps to portfolio.
- Do not infer sectors or invent profile defaults. An empty eligible universe is a failure, not permission to relax exclusions.
- Verify exclusion combinations, unavailable metadata and an empty universe. Pass eligibility and decision records to portfolio and evidence.
