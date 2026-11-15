# Proposal workflow and Lambda connection

The handler now calls `RecommendationOrchestrator.run()` for the existing
`profile_id`/`changes` contract. This is a synchronous assessment workflow in one
Lambda. Questionnaire matching and dataset-bound chat edits also use this workflow;
see [questionnaire contracts](questionnaire-workflow.md). Broader financial-risk-capacity
scoring, ESG screening and the teammate-owned per-ticker risk module remain pending.

## Request and response

Direct invocation:

```json
{
  "action": "recommend",
  "request": {
    "profile_id": 4,
    "changes": [{"ticker": "TSLA", "add_pct": 5}],
    "as_of": "2026-11-12"
  }
}
```

`changes` is required and may be empty; at most 40 changes are accepted. An edit
is exactly `{"exclude":"TICKER"}` or `{"ticker":"TICKER","add_pct":5}`.
Additions are integer percentage points between -100 and 100; booleans and extra
fields are rejected. `as_of` is optional and defaults to the current UTC date;
future dates are rejected and later input observations are excluded.

HTTP API v2 / Function URL event shapes use `POST /portfolio` with the inner
request object as the JSON body, including base64-body support. This handler
support does not provision an HTTP endpoint. `POST /chat` accepts the validated
questionnaire, current portfolio and dataset-bound edits described in
[the follow-up contract](questionnaire-workflow.md#follow-up-requests).

| Outcome | HTTP status | Meaning |
| --- | --- | --- |
| PASS | 200 | Requested allocation passed the implemented historical/profile checks |
| CONFLICT | 200 | Requested allocation failed checks; any returned alternative independently passed |
| INVALID_REQUEST | 400 | Invalid request/profile/proposal |
| MISSING_INFO | 422 | Missing/invalid inputs or unsupported observation frequency |
| FAILED | 500 | Internal workflow or release-check failure |
| AUDIT_FAILED | 503 | Required audit could not be saved; no portfolio returned |
| TIMEOUT | 504 | Workflow stopped to preserve its final audit budget |

An audited CONFLICT assessment can contain a passing adjusted portfolio. If
neither branch passes, no `portfolio` field is returned. Workflow completion
and a passing portfolio are different outcomes. Error payloads do not expose
bucket names, file paths, SDK responses, prompts or partial recommendations.
Invalid transport inputs fail before workflow creation and are not stored as
investor runs.

`GET /health` or `{"action":"health"}` checks handler liveness and returns
`workflowConfigured`. That flag checks configuration only; it does not prove
that bucket access, model access, input quality or an assessment will succeed.

## Execution

1. Load a fresh input snapshot and record the hashes of the actual source bytes.
2. Exclude observations after the as-of date; validate dates, duplicates, positive
   prices/FX, currencies, reference weights and configured policy limits.
3. Require holdings/history and consistent daily or weekly cadence. Weekly returns
   annualize at 52 observations/year; daily returns use 252. Record the selected
   convention in the manifest and validation output. Reject mixed or sparse cadence
   and verify the common-date calendar again before computing metrics. These checks
   do not certify a trading calendar or substitute missing profile holdings.
4. Call the existing `PortfolioEngine.evaluate()` against the captured snapshot.
   All engine reads within the run resolve to those same captured inputs.
5. Build typed evidence entries, failed-check facts and mandatory limitations.
   Evidence IDs contain the run ID and refer to a hash of the input manifest.
   For questionnaire requests, first run deterministic portfolio review and bounded
   engine-checked alternatives. Findings, rationale and qualifying trade-offs enter
   the evidence bundle before explanation; rejected trials stay in the audit.
   See [review and suggestion methods](portfolio-review.md).
6. Optionally ask Bedrock to order those verified statements. Its response is
   restricted to `{"claim_ids":[...]}` containing every supplied ID exactly once.
   Free-form explanations are deliberately not accepted in this version.
   Python renders the vetted statements, citations, disclaimer and limitations.
7. Share one budget of an initial model generation plus at most two repairs.
   Invalid JSON, unknown/duplicate/omitted claims and model failures share that
   budget. A deterministic fallback passes the same final checks. Structural
   failures do not consume explanation repair attempts.
8. Save all seven audit artifacts; only then return the public result.

The gate checks evidence identity/content and any released portfolio's implemented
checks and weight sum. It does not establish legal suitability, universal semantic
correctness of arbitrary prose, or ESG compliance. The wording surface is bounded
because the model cannot write new sentences in this version.

Runtime state, evidence, retry counts and input snapshots are fresh per invocation.
Reusable clients are cached by the handler. Each invocation receives a new UUID;
duplicate invocations are separate assessments and may incur separate model calls.
This is not a request-deduplication or durable-resume mechanism.

## Audit contract

The store writes `profile.json`, `data_manifest.json`, `evidence.json`,
`decisions.json`, `llm_calls.json`, `compliance.json` and finally `result.json`
under `runs/{run_id}/`. Records include transitions, method/version metadata,
calculated decisions and successful/failed model attempts. Raw prompts and model
responses remain in the private audit, not in application logs or error responses.
The public evidence provides factual lineage; it omits storage credentials.

Local stores refuse existing run directories. S3 stores use conditional creates
(`IfNoneMatch: *`), and a failed write stops subsequent writes. The final
`result.json` is the commit record. Earlier objects without it are partial runs.
A lost final-write acknowledgement returns failure even if the object reached S3;
inspect the run rather than assuming it was released. There is no multi-object S3
transaction or automatic recovery. Failed assessments are audited when storage and
the remaining execution time permit it.

## Local use

From the Git root with the Python environment activated:

```powershell
python backend/scripts/run_workflow.py --event backend/events/recommend.json
```

This uses the existing local dataset and profiles, writes `.local-runs/`, and
uses the checked deterministic explanation. It does not download data or call
AWS. Missing or incompatible history produces MISSING_INFO. Offline controls use
fictional flat-price fixtures; `scripts/check_pipeline_e2e.py` additionally exercises
the actual source CSVs through local HTTP transports and persisted audit checks.

To invoke the handler locally on the host instead, set `ALPHAFORGE_MODE=local`.
Optional `DATA_DIR`, `PROFILES_PATH` and `AUDIT_DIR` override local paths. The
Lambda image excludes local data; its deployed mode should be `s3`.

## AWS configuration

No resources are deployed by this implementation. The SAM template accepts:

| Parameter | Purpose |
| --- | --- |
| DataBucketName | Existing private bucket holding inputs |
| DataPrefix | Prefix without trailing slash, default `inputs` |
| AuditBucketName | Existing private bucket for `runs/` audit writes |
| RuntimePolicyArn | Reviewed managed runtime-permissions policy attached to the function's own execution role |
| BedrockModelId | Optional accessible model/inference profile ID; blank selects deterministic rendering |

Place `prices_weekly.csv`, `fx_usdcad_daily.csv` and `profiles.json` under the
configured input prefix. Input objects should be immutable/versioned for
reproducibility. Each downloaded object's ETag/version ID and SHA-256 are recorded;
this does not imply the three independently uploaded objects came from a single
coordinated dataset release. Use a coherent release prefix when uploading them.

S3/audit storage must be configured together with the reviewed policy. If any
are omitted, the template leaves the workflow disabled. Health remains available.
No bucket, HTTP endpoint, workshop resource or secret is created or modified.

Use IAM Policy Autopilot to generate a baseline from the actual SDK call sites.
Run from the Git root after installing `uv` if `uvx` is unavailable:

```powershell
$repoPath = (Get-Location).Path
$sdkFiles = @(
  (Join-Path $repoPath 'backend/src/alphaforge/bootstrap.py'),
  (Join-Path $repoPath 'backend/src/alphaforge/infrastructure/workflow_storage.py'),
  (Join-Path $repoPath 'backend/src/alphaforge/infrastructure/bedrock.py')
)
$accountId = aws sts get-caller-identity --query Account --output text --region us-east-1
uvx iam-policy-autopilot@latest generate-policies $sdkFiles --region us-east-1 --account $accountId --pretty
```

Review the generated policy before creating/attaching it. Runtime resource names
are configuration values: scope reads to the three input objects and writes to
the audit bucket's `runs/` prefix. Optional Bedrock access must include the chosen
inference profile and underlying model resources/destination regions. If the
buckets use a customer-managed KMS key, its IAM/key policies need the relevant
permissions as well. The baseline generator does not prove runtime access or
capture all cross-region/KMS requirements. No policy is generated or attached by
the application itself.

From `backend/`, update the existing stack with your actual values:

```powershell
sam build
sam deploy --guided
```

Enter the parameter values when prompted; keep existing stack name and region.
Review the role-policy attachment and function environment changes. Deployments
must use the newly built image. SAM's saved configuration is local and ignored.

The Lambda remains at a 120-second timeout. Engine search loops stop when fewer
than 25 seconds remain; new model attempts require at least 45 seconds. The
Lambda-specific Bedrock client uses one transport attempt, a two-second connect
timeout and twelve-second read timeout. Separate S3 read/audit clients use
bounded transport settings. These are best-effort deadline controls, not hard
cancellation of pandas/native computation or a guarantee against platform timeout.

## Development handoff

Primary owner: infrastructure/integration. Supporting roles: data, screening,
risk, portfolio, backtest, evidence, explanation and compliance; lessons L-001
through L-006 were loaded. L-002's shared retry policy and L-003 through L-006's
calculation/input boundaries apply. No profile rules, stored reference weights,
datasets or the teammate-owned risk implementation were changed.

Next owner: provide compatible historical data, review the runtime policy and
configure the existing stack; questionnaire/profile owners implement their
mapping and frontend HTTP adapter separately. See the implementation test files
for deterministic evidence; these checks are not an independent review.

Implementation status: complete for the profile-ID proposal contract. Verification:
112 passed, 8 skipped, 2 xfailed; 17 subtests passed. The skips are legacy dataset
integration cases; expected failures concern the existing risk stub. SAM
`validate --lint` reported a valid template, with local SAM metadata permission
warnings. Python parsing, diff checks, workflow structure and eight checker
self-tests passed. An actual local-input run returned audited MISSING_INFO and
no portfolio because input validation failed. No datasets/profile weights were
changed, and no live AWS calls, image deployment or model invocation were run.

Lesson L-007 records the observed deadline-loop indentation failure, its repair
and passing replay controls. No checkpoint/resume or deduplication guarantees are
claimed. Next owner: deployer/configuration owner, then frontend/profile team.
