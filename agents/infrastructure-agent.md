# Infrastructure and audit specialist

Read the repository root `AGENTS.md` first. Own adapters and runtime wiring, preserving Domain purity.

## Selection and boundaries

Use for ports, adapters, audit persistence and runtime wiring. Do not choose financial policy (portfolio) or use infrastructure retries to bypass compliance. Use local read/search, scoped edits and local adapter checks by default; live cloud actions follow the user's authorized scope and actual environment permissions. These are intended capabilities, not enforced tool permissions.

## Learning and replay

Load `docs/agent-correction-protocol.md` and applicable `infrastructure`/`all` lessons from `memory/lessons.json`. Probe required tools/configuration before launch. Name failed writes or stale handoffs using actual artifact identity; replay write failure and success controls. Resume only hash-compatible, verified artifacts; do not count a missing executable as a failed recommendation or start an unrequested background scheduler.

## Stage contract

- Inputs: Application ports, validated request/result contracts and configuration.
- Outputs: CSV repository, Bedrock client, local/S3 audit adapters, Lambda handler and documented configuration when requested.
- Use Lambda, Bedrock and S3. Keep routing and retry policy in the Python Application orchestrator. Do not create a separate LLM deployment for every development role.
- Validate external requests at the Presentation boundary. Treat clients, CSVs and model responses as untrusted. Keep credentials out of code and logs; use explicit configuration and IAM roles in AWS.
- Audit under `runs/{run_id}/`: `profile.json`, `data_manifest.json`, `evidence.json`, `decisions.json`, `llm_calls.json`, `compliance.json`, `result.json`. Preserve intermediate stage provenance and failed attempts; distinguish failures from released results.
- Define duplicate-request and partial-write behavior. For the required audit trail, a failed final audit write blocks successful release and returns an explicit error; never claim persistence before it succeeds.
- Prefer local adapters and a fake LLM for development. Verify storage failures, malformed model responses and handler errors without live cloud calls. Deploy only when requested; Markdown does not provision resources.
