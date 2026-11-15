# Connecting Bedrock to AlphaForge

## What is implemented

`backend/src/alphaforge/application/llm.py` defines a model-independent text-generation port. `backend/src/alphaforge/infrastructure/bedrock.py` implements it with boto3 Converse, SDK credential discovery, bounded transport retries and explicit failed/incomplete responses. All text blocks are joined even when reasoning appears first. Usage, request ID, model ID and raw successful/incomplete output are available for a future AuditStore integration; this adapter does not persist artifacts itself.

`backend/scripts/bedrock_smoke_test.py` makes one logical live generation request only when explicitly run. `backend/tests/test_bedrock.py` uses mocks and a botocore stub, with no network or real credentials.

This change does not implement a production explanation prompt, Evidence Bundle validation, compliance gate, S3 audit persistence, Lambda handler or Strands tool loop. Never present its raw output as a validated recommendation.

## Which agents use a model?

The canonical target in `docs/architecture.md` and `docs/agent-responsibilities.md` is the deterministic pipeline below. Strands orchestrator, risk analyst, ESG evidence and governance concepts in `CLAUDE.md` are proposals, not implemented runtime agents. The shared boto3 connection supports language calls in either approach; Markdown role files do not become deployed agents automatically.

| Existing pipeline role | Bedrock use |
| --- | --- |
| Data, Screening, Risk, Portfolio, Backtest | None for calculations; deterministic Python |
| Evidence and limitations | None; code builds provenance and checks claims |
| Explanation | Converse generates language from validated evidence |
| Compliance | Deterministic release checks; optional language review later |
| Infrastructure | Supplies the SDK adapter; it is not an LLM reasoning stage |

In the Strands design, an LLM risk analyst can choose Python risk tools and explain their outputs. That does not mean replacing the tool calculations with a model. Each language role has its own instructions and allowed tools, while several roles can use the same model/profile ID. Model access, Bedrock Agents resources and Strands software agents are different concepts; a Strands agent does not require creating a managed Bedrock Agent resource.

The development files under `agents/` are not production system prompts. They contain development, editing and incident-memory instructions. Do not send these files or development lessons to a production investor-facing model. Write separate runtime prompts that name the role, permitted evidence, output contract and tool boundaries.

## First live test on Windows

Use the SAME PowerShell terminal where the event's temporary credentials worked. From the inner Git repository containing `AGENTS.md`, use your configured Python interpreter:

```powershell
python backend/scripts/bedrock_smoke_test.py
```

On the current machine, the existing virtual environment is in the parent workspace. If it is not activated, the equivalent command is:

```powershell
..\.venv\Scripts\python.exe backend/scripts/bedrock_smoke_test.py
```

The script uses `us-east-1` and the team's test profile `global.amazon.nova-2-lite-v1:0`. It prints the active account ID, model/profile and response. This is a billable model call and may cause SDK transport retries; no live call is part of offline tests. Account access has not been verified by adding this code. Installing dependencies uses `python -m pip install -r backend/requirements.txt` with the chosen interpreter if needed.

To use another accessible model/profile:

```powershell
python backend/scripts/bedrock_smoke_test.py --model-id YOUR_MODEL_OR_INFERENCE_PROFILE_ID
```

`CLAUDE.md` names `global.anthropic.claude-sonnet-5` for explanation/reasoning and Haiku for extraction. These are team configuration choices, not proof that the event account can invoke them. Start with the connection test; confirm any model in the Bedrock console before production use. The adapter sends no temperature/topP and uses at least 1000 output tokens to follow the team convention. A global profile may process requests in other regions even though the source client is us-east-1.

## Call the port from application code

Composition/wiring code supplies the infrastructure adapter; application stages depend on `LLMClient`:

```python
from alphaforge.application.llm import LLMClient

def request_draft(llm: LLMClient, system: str, evidence_json: str):
    return llm.generate(system=system, prompt=evidence_json, max_tokens=2048)
```

Create the adapter once in the wiring code using `BedrockLLMClient.connect(BedrockSettings(model_id=...))`. Add `src` to the Python path or package the source for deployment; the smoke script already sets that path for itself. Do not hard-code credentials. Locally boto3 reads the event terminal credentials; Lambda uses its execution role.

One `generate` call is one application generation attempt. SDK retries for throttling/network failures are a separate transport budget (adaptive, up to five retries under the team's `max_attempts` configuration). They can extend wall time beyond a single request timeout; coordinate them with the eventual Lambda deadline. The application owns the shared initial explanation + two repair generations + checked deterministic fallback policy (lesson L-002); the adapter has no extra prose-repair loop.

Record prompts, returned metadata/raw output and failures through AuditStore when that port is implemented. Keep those run artifacts private and separate from development lessons. Failure to persist the required final audit must block result release. An independent compliance check must still run after language generation.

## Permissions and troubleshooting

- Converse needs `bedrock:InvokeModel` on the selected resources; there is no need to grant a fictitious `bedrock:Converse` action. Inference profiles also require permissions for their underlying model resources/destination regions.
- `AccessDeniedException`: verify event account, provider prerequisites, model availability and IAM/profile permissions. Do not broaden the role to administrator to hide the failure.
- Expired/missing credentials: recopy the event PowerShell credentials into the same terminal and rerun. The SDK does not need the `aws` executable on PATH.
- Import error: install the dependencies into the same Python interpreter you use to run the script.
- Truncation or guardrail refusal: the adapter returns an explicit error, not a successful explanation. Missing evidence is not repaired by increasing token limits.

## Offline checks

```powershell
python -m pytest backend/tests -q
```

Sources: [Converse API and permissions](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html), [model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html), [cross-region inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html), [Nova 2 Lite profile IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-lite.html).
