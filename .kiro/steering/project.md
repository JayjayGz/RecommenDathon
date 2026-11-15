# Current layout and precedence

Read `AGENTS.md`, `README.md` and `docs/architecture.md` first. The sections below retain team product concepts and pending decisions; they do not establish implemented behavior. CSVs live in `dataset/`, with `prices_daily.csv` as prices. The supplied history lacks 13 legacy profile tickers (see `docs/DATA.md`). Full evidence/compliance/API orchestration and questionnaire mapping remain pending. Python code lives in `src/alphaforge/`; launch tools through `scripts/`.

# Project conventions (AlphaForge AI, PolyFinances Datathon 2026)

## AWS and models
- AWS region is always us-east-1.
- Call Amazon Bedrock through boto3 with the Converse API. Never use InvokeModel.
- In a Converse response, never read content[0]["text"]. Join every content block that has "text"; some models return a reasoning block first.
- Default model for testing: global.amazon.nova-2-lite-v1:0
- Model for explanations and agent reasoning: global.anthropic.claude-sonnet-5 (no temperature or topP; maxTokens at least 1000).
- JSON extraction: global.anthropic.claude-haiku-4-5-20251001-v1:0 with structured outputs.
- Strands roles are a proposed language orchestration option, not an implemented runtime. Follow AGENTS.md and docs/architecture.md; numerical stages stay deterministic. If a Strands loop is later approved, bound its turns.
- Create Bedrock clients with botocore Config(retries={"max_attempts": 5, "mode": "adaptive"}).
- Never put AWS credentials, API keys or .env files in code or Git.

## Data
- Dataset lives in dataset/ (not committed; Yahoo Finance terms). Commit the scripts that rebuild it.
- Use adj_close for returns. Prices are already split-adjusted; never reapply splits.
- Prices are in each asset's listing currency: .TO tickers are CAD, everything else USD.
- Convert USD to CAD with the Bank of Canada rate from fx_usdcad_daily.csv, using pandas merge_asof(direction="backward") (last rate on or before each date).
- Portfolio backtests use only days when every holding traded (crypto weekends dropped). Say so in outputs.
- Never use data dated after the simulation's as_of_date. Monthly macro data is dated by reference month, not release date.
- Every number shown to a user states its source, period and currency.

## Product rules
- Educational simulation only. Fictional profiles. No real transactions, no real personal or banking data.
- The app shows a clear notice: "Educational simulation. Not personalized financial advice. Fictional profiles. No real transactions."
- Answers label each statement as fact (with source), assumption or scenario, and state limits.
- If data is missing, say "data not available"; never invent a number.
- Numbers are computed in Python (pandas). Models explain numbers; they never calculate them.

## Code
- Python 3.10+, pandas, numpy, streamlit. Tests with pytest.
- Prototype for a datathon: a working, explainable demo beats extra abstraction layers.
- The team IDE is Linux: use bash commands (source .venv/bin/activate).
- Demo runs with: streamlit run <app>.py
