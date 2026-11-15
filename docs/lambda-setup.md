# AlphaForge Lambda setup

This provisions one new AlphaForge function, a dedicated execution role and a
CloudWatch log group. It does not modify the preconfigured workshop/Kiro functions.
No Step Functions state machine is needed.

## What works now

`backend/src/alphaforge/presentation/lambda_handler.py` supports authenticated,
direct Lambda invocations. `{"action":"health"}` returns HTTP-style status 200
and `pipelineReady: false`. `{"action":"recommend"}` returns 503 with
`PIPELINE_NOT_READY`. A successful invocation proves handler liveness only.

The orchestrator, evidence/compliance release checks, S3 adapters and frontend
contract mapper are not implemented. No portfolio is released by this bootstrap.
No public URL is created. The handler understands HTTP API v2 event shapes for
future integration; this alone does not connect the frontend.

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
assets. The current local CSV adapter is not a Lambda storage adapter: it assumes
the repository checkout and cannot load S3. Connect an S3-backed repository before
wiring the portfolio engine into the deployed handler. No input data is uploaded
by the build.

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
sam local invoke AlphaForgeFunction --event events/recommend.json
```

Expected bodies: health reports `ok: true, pipelineReady: false`; recommend reports
`PIPELINE_NOT_READY` with status 503. These commands make no Bedrock calls.

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

SAM creates an execution role with basic CloudWatch logging permissions. The
bootstrap has no S3 or Bedrock permissions because it does not use those services.
When wiring the pipeline, add narrowly scoped input-object reads, audit writes
under `runs/`, and `bedrock:InvokeModel` on the chosen model/inference profile and
its underlying model resources. Keep the deployed role separate from the identity
used to deploy the stack.

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
They require an HTTP endpoint and matching contracts. Add that transport after
the orchestrator and its release checks work, with authentication appropriate to
the frontend/proxy.

## Implementation handoff

Infrastructure is the primary role. Inputs: existing backend package, frontend
transport contract and architecture; loaded lessons L-001, L-002 and L-006.
Outputs: handler, image definition, SAM template, sample events, offline transport
tests and this guide. The next owner wires the application orchestrator and
S3/audit interfaces; calculations and reference profiles are unchanged.

Files are prepared for review. Cloud deployment requires available AWS credentials,
AWS/SAM CLI and a working Docker engine. This document is not evidence of a live
deployment, tested account permissions or a complete recommendation pipeline.

Offline verification on 2026-11-15: the full suite returned 66 passed, 8 skipped,
2 xfailed and 17 subtests passed. Skips concern unavailable legacy dataset
holdings; expected failures concern the existing risk stub. Template YAML,
resource inventory, Dockerfile context path and sample-event JSON checks passed,
as did `git diff --check`. `profiles.json` has no diff. These checks do not replace
`sam validate --lint`, an actual Linux image build or a deployed smoke test.

Deployment status: blocked by environment prerequisites. The session's SDK found
no credentials or AWS profiles; AWS/SAM CLI were absent from PATH; the Docker
engine was unavailable. No cloud resources were created or modified.
