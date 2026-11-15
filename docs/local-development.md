# Start the connected application locally

From the inner repository root, containing `AGENTS.md` and `profiles.json`, run:

```bash
node scripts/start_local.mjs
```

Open http://localhost:4173. Keep that terminal running. Ctrl+C, or typing `stop`
and Enter, stops both services. This is a development launcher on loopback only;
it does not install a background service, deploy AWS resources or expose a LAN endpoint.

The launcher uses Node's built-in dotenv loader for the root `.env`, starts the
Python HTTP adapter on 127.0.0.1:8000 and starts the existing website proxy with
`/portfolio` and `/chat` connected. It does not load `plateforme/.env`.
The frontend process does not receive `AWS_*` or `BEDROCK_*` environment variables.
The Python adapter serves no files and does not log request bodies or headers.

## Configuration

Use the existing root `.env`, or copy `.env.example` and fill it locally. Keep
the real file out of Git. Nothing needs to be pasted into Python source.

```dotenv
ALPHAFORGE_MODE=local
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-5-5
AWS_BEARER_TOKEN_BEDROCK='your-token'
```

Existing terminal variables take precedence over `.env`. Restart the launcher
after changing either. For a stale Bash override, `unset VARIABLE_NAME` before
restarting lets the file supply that value. The current Bedrock adapter requires
`us-east-1`. Tokens still expire; storing a token does not renew it.

The launcher selects Python from `PYTHON_EXECUTABLE`, the active `VIRTUAL_ENV`,
a repository `.venv`, the parent directory's `.venv`, then PATH. Install the
existing backend requirements in that environment if necessary. No new package
is needed for dotenv loading. The documented frontend requirement is Node 24+.
The Python requirements include `boto3[crt]`: an existing AWS CLI login profile
can require the CRT credential-provider dependency even when a Bedrock bearer
token is configured. For an older environment, install it with
`python -m pip install "boto3[crt]"`. Startup checks client construction and reports
the dependency error without printing credentials; it still makes no model call.

Optional settings: `PORT` (website, default 4173), `BACKEND_PORT` (default 8000),
`DATA_DIR` (default dataset), `PROFILES_PATH` (default profiles.json) and `AUDIT_DIR`
(default .local-runs). Relative data/audit paths resolve against the repository root.
The local launcher requires `ALPHAFORGE_MODE=local` and always routes its website
to its own backend rather than any external API URLs from the environment.

To test the connected app without model calls, even if the file contains a model:

```bash
node scripts/start_local.mjs --offline
```

To change ports:

```bash
node scripts/start_local.mjs --port 4174 --backend-port 8001
```

An alternate file can be selected with `--env-file PATH`. The default root `.env`
is optional. The launcher checks both ports before starting services. If a port is
occupied, use the existing app, stop it in its original terminal, or select two
available ports. It does not stop an unrelated process. If either child service
fails after startup, the launcher stops its other child too; Windows shutdown
also stops the spawned Python wrapper's descendants.

## Verify a run

`http://127.0.0.1:8000/health` checks liveness and configuration only. The startup
line saying Bedrock is configured does not prove token/model access. No model
request is made merely by starting the app.

Complete the questionnaire and request a portfolio. The website calls the actual
Python handler, engine, review, evidence checks and audit store. Follow-up chat
supports the existing explicit dataset-bound edits, such as `Add NVDA 1%` as a
syntax example. This launcher does not add free-form LLM tool orchestration or
invoke a managed Bedrock Agent; the optional model still orders vetted evidence.

Inspect `.local-runs/<run-id>/result.json`: `explanation_mode: bedrock_ordered`
means an accepted model response; `fallback` means the deterministic explanation
was used. `llm_calls.json` and `compliance.json` record attempts and failures.
Audit files can contain private inputs and prompts; they are not web resources.

Only one local evaluation runs at a time. A concurrent request receives a busy
response; health stays available. The browser waits up to 130 seconds and the
proxy up to 125 seconds around the existing 120-second workflow budget. The
backend transport enforces a 64 KiB body limit and local Host/Origin checks.

## Checks and handoff

Infrastructure owns the local transport and launcher. Inputs are the existing
root configuration, source CSVs, handler and Node proxy. Compliance supports
unchanged validation, bounded model repairs and audit-before-release. No numerical
or investor policy changes are made. Next owner: the user starts the launcher
with their local configuration; deployment remains separate.

`backend/tests/test_local_server.py` checks transport boundaries, real engine and
audit requests, busy handling, dotenv precedence, credential filtering, the full
launcher with real CSVs in offline mode, and shutdown of both processes. These
checks do not establish live Bedrock access or graphical browser behavior.

A separate live replay on 2026-11-15 reached Bedrock through the actual launcher,
website proxy and Python handler: HTTP 200, PASS, `bedrock_ordered`, one model
attempt, no model errors and all seven audit artifacts. It used the repository's
fictional questionnaire and supplied market data. The safe summary is in
`.local-runs/launcher-verification/live-summary.json`; private run artifacts remain
under the corresponding run ID. This single invocation does not certify model
reliability or future token validity. No graphical browser or AWS deployment was tested.
