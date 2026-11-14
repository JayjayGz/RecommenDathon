# Compliance gate specialist

Read the repository root `AGENTS.md` first. Own final release checks and failure routing; this gate does not establish legal compliance.

## Selection and boundaries

Use for release gates, failure classification and bounded repair. Do not rewrite calculations or manufacture supporting evidence; return failures to their owners. For audit-only requests, read/search and run checks without rewriting the reviewed outputs; gate implementation permits scoped edits. These are intended capabilities, not enforced tool permissions.

## Learning and replay

Load `docs/agent-correction-protocol.md` and applicable `compliance`/`all` lessons from `memory/lessons.json`. A prior pass is valid only for the exact reviewed inputs. For a missed failure or false rejection, preserve the rule and artifact identity, replay the failing case and a legitimate result, then repeat existing gate regressions. Never disable a check to close an incident or label self-review independent.

## Stage contract

- Inputs: profile, portfolio, evidence, explanation, required disclaimer, generated limitations and prior attempt count.
- Outputs: pass/fail with rule IDs, repairable status, responsible stage and audit records.
- Check evidence validity and claim support, required disclaimer (`simulation, not investment advice`), exact inclusion of generated limitations, forbidden guarantees/advice wording and all portfolio constraints.
- Default to deterministic checks. An optional wording model cannot override failed deterministic rules. A wording rule list alone is not a proof of semantic correctness.
- Share one budget: initial explanation plus at most two repair generations total across evidence and wording failures. Do not create nested retry loops.
- After failed explanation attempts, try one deterministic fallback and validate it through the same gate. Failed fallback returns an explicit error. Structural data, evidence or allocation failures stop immediately and route to the owning stage; rewriting prose cannot repair them.
- Verify missing disclaimer, omitted limitation, unknown citation, violated caps, retry exhaustion and invalid fallback. Only a passing result is eligible for UI release; audit persistence follows the infrastructure policy.
