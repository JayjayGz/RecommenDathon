# AlphaForge Lambda setup

This provisions one new AlphaForge function, a dedicated execution role and a
CloudWatch log group. It does not modify the preconfigured workshop/Kiro functions.
No Step Functions state machine is needed.

## What works now

`backend/src/alphaforge/presentation/lambda_handler.py` supports authenticated,
direct Lambda invocations. `{"action":"health"}` returns HTTP-style status 200
and `workflowConfigured`, which checks environment configuration only.
`{"action":"recommend","request":{...}}` calls the [proposal workflow](orchestrator.md)
after request validation. Without storage configuration it returns status 503
with `WORKFLOW_CONFIGURATION_UNAVAILABLE`.

The workflow supplies per-run snapshots, the existing portfolio engine, evidence,
constrained explanations, release checks and required audit persistence. The
frontend questionnaire mapper is not implemented. No public URL is created.
HTTP API v2 event parsing does not by itself connect the frontend.

## Packaging

- Template: `backend/template.yaml` (AWS SAM).
- Runtime: Python 3.13, Linux x86_64 container, 1024 MB RAM, 120-second timeout.
- Handler: `alphaforge.presentation.lambda_handler.handler`.
- Image: `backend/Dockerfile`, built with Linux dependencies from
  `backend/requirements-lambda.txt`. Direct dependency versions match the existing
  development environment; an image build is still required to verify Linux wheels.
- Logs: 14-day CloudWatch retention. The handler does not log request contents.

The Docker context is restricted to backend source and runtime dependencies.
It excludes private CSVs, profiles, development memory, credentials, tests and UI
assets. The deployed workflow uses the S3 snapshot source instead of assuming
a repository checkout. No input data is uploaded by the build. Configure existing
input/audit buckets and a reviewed runtime policy as described in the
[workflow guide](orchestrator.md#aws-configuration).

## Prerequisites

On Windows, install [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html),
[AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
and start Docker Desktop with its Linux engine. Container images avoid copying
Windows NumPy/pandas binaries to Lambda.

Use the workshop's supported local authentication method. If credentials are
temporary, the session token is required as well as the access key and secret.
Keep all three outside source code and chat. Run deployment in the same terminal
where credentials are available. An IDE terminal's environment is not necessarily
inherited by this assistant's shell.

Verify tools and the target account before building:

```powershell
aws --version
sam --version
docker version
aws sts get-caller-identity --region us-east-1
```

The deployment identity needs permission to create the stack's Lambda, execution
role, log group and deployment artifacts in S3/ECR. Workshop accounts may restrict
role creation; use the event's documented deployment permissions rather than
repurposing an IDE role or attaching administrator access.

## Test and build

From the repository root, with the existing Python environment activated:

```powershell
python -m pytest backend/tests/test_lambda_handler.py -q
cd backend
sam validate --lint --template-file template.yaml --region us-east-1
sam build --template-file template.yaml
sam local invoke AlphaForgeFunction --event events/health.json
```

Health reports `ok: true` and the environment's `workflowConfigured` value; it
makes no Bedrock calls. For a host-side local assessment with local inputs and no
AWS access, run `python backend/scripts/run_workflow.py` from the Git root.
The current incompatible data should produce MISSING_INFO, not an invented result.

Conditional policy changes also require the actual SAM translator regression:
`python backend/tests/test_sam_template.py -v` from the Git root after installing
the development requirements. On this Windows machine, SAM's bundled interpreter
can run it without another installation:

```powershell
& 'C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe' backend/tests/test_sam_template.py -v
```

Schema lint previously accepted a `Policies` shape that the SAM transform rejected.
Keep conditional managed-policy attachments as list items inside `Policies`.
After changing the source template, rerun `sam build` before `sam deploy`; otherwise
SAM can reuse the old template in `.aws-sam/build/`.

## Deploy

From `backend/`, after reviewing the target account above:

```powershell
sam deploy --guided --stack-name alphaforge-dev --region us-east-1 --capabilities CAPABILITY_IAM
```

Use `alphaforge-dev` as a separate stack. Review and confirm the changeset. SAM
will guide deployment configuration and ECR image repository setup. Deployment
creates billable AWS resources; no public invocation endpoint is included.
Subsequent deployments can use `sam deploy` from the same directory after saving
the guided configuration locally. Generated SAM files are ignored by Git.

SAM creates an execution role with basic CloudWatch logging permissions and
attaches `RuntimePolicyArn` if provided. Set `DataBucketName`, `AuditBucketName`,
`DataPrefix` and the reviewed policy ARN to enable the S3 workflow. Optional
`BedrockModelId` enables model-based ordering of verified statements; leaving it
blank uses the checked deterministic renderer. See the policy-generation command
and resource-scoping requirements in [the workflow guide](orchestrator.md#aws-configuration).
Keep the deployed role separate from the identity used to deploy the stack.

## Verify the deployed function

Still from `backend/`:

```powershell
$functionName = aws cloudformation describe-stacks --stack-name alphaforge-dev --region us-east-1 --query 'Stacks[0].Outputs[?OutputKey==`FunctionName`].OutputValue | [0]' --output text
aws lambda invoke --function-name $functionName --region us-east-1 --cli-binary-format raw-in-base64-out --payload file://events/health.json health-response.json
Get-Content health-response.json
```

Check the JSON body's `statusCode`, not only the CLI's invocation status: Lambda
can successfully invoke a handler that returns application status 503.

Do not set the frontend's `PORTFOLIO_API_URL` or `AGENT_API_URL` to a Lambda ARN.
They require an HTTP endpoint and matching contracts. Add that transport and the
questionnaire/profile mapping with authentication appropriate to the frontend/proxy.

## Implementation handoff

Infrastructure is the primary role. Inputs: existing backend package, frontend
transport contract and architecture; loaded lessons L-001 through L-006 for the
workflow integration. Outputs include handler, workflow, local/S3 adapters,
deployment parameters, offline tests and documentation. Next owners provide
compatible inputs, review the generated runtime policy and connect the frontend
contract. Numerical rules and stored reference profiles are unchanged.

The user reported deployment of the earlier health-only image. The new workflow
requires rebuilding and updating that stack; no deployment or live AWS operation
was performed by this implementation. Offline tests do not establish live model
access, bucket permissions or a complete questionnaire pipeline.
