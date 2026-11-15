# Current layout and precedence

Read `AGENTS.md`, `README.md` and `docs/architecture.md` first. The sections below retain team product concepts and pending decisions; they do not establish implemented behavior. CSVs live in `dataset/`, with `prices_weekly.csv` as the committed prices file for analysis (a daily starter copy stays local only, at `dataset/starter_daily/`). The supplied history lacks 13 legacy profile tickers (see `docs/DATA.md`). The profile-ID proposal workflow now connects Lambda, evidence/release checks and S3/local auditing (docs/orchestrator.md); questionnaire mapping is implemented (`backend/src/alphaforge/domain/profile_mapping.py`); sector/ESG screening and frontend HTTP mapping remain pending. Python code lives in `backend/src/alphaforge/`; launch backend tools through `backend/scripts/` (the dataset build script is `backend/scripts/build_dataset.py`; starter dataset docs are at `docs/starter-dataset.md`).

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
- Dataset lives in dataset/. Committed to the repo by team decision (KC-ZEUS). Licence note: Yahoo data, check redistribution terms before making the repo public.
- A local backup of the dataset CSVs lives outside the repo, at `C:\Users\kenny\alphaforge_data_backup\` (Kenny's machine only, not shared, not a substitute for rebuilding).
- Prices for analysis: `dataset/prices_weekly.csv` (weekly, Friday-dated adj_close). A daily starter copy (31 tickers, 2021-11-12 to 2026-11-12) stays local only, at `dataset/starter_daily/` — not committed.
- Use adj_close for returns. Prices are already split-adjusted; never reapply splits.
- Prices are in each asset's listing currency: .TO tickers are CAD, everything else USD.
- Convert USD to CAD with the Bank of Canada rate from fx_usdcad_daily.csv, using pandas merge_asof(direction="backward") (last rate on or before each date).
- Portfolio backtests use only days when every holding traded (crypto weekends dropped). Say so in outputs.
- Never use data dated after the simulation's as_of_date. Monthly macro data is dated by reference month, not release date.
- Every number shown to a user states its source, period and currency.

## Universe
- The 15 base profiles only use the curated 34-ticker list (`dataset/asset_selection.csv`).
- A larger list (100+ tickers) exists only to support user-requested single-stock additions (e.g. "add TSLA"), never the base profiles.
- A ticker not present in `dataset/prices_weekly.csv` is reported to the user as a limitation ("data not available"); it is never guessed or substituted.

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

# What we are building

## The challenge (official brief, AlphaForge AI)
Design a self-explaining agentic solution that uses public financial data to inform investment analysis or decisions for different investor profiles. Explainability is expected: link results to sources, assumptions, observable steps and limitations. Number of agents is not a goal in itself; every component needs a clear reason to exist.

Judging: solution quality 20%, agentic intelligence and explainability 20%, data analysis and processing 20%, UX/UI 10%, AWS integration 15%, presentation and business value 15%.
AWS is a qualifying requirement: it must make a real, demonstrable contribution to how the solution works.

Deliverables: prototype + code repo with README, ~5 minute demo video, technical documentation, one-pager.

## Official personas (reference scenarios)
- Amira, 26: high risk, 15+ years, likes tech/AI and crypto but wants diversification. Test: "high risk" is not "anything goes".
- Mateo, 41: moderate risk, 8-12 years, strong ESG preferences, avoids companies with major controversies. Test: weigh more than return and risk.
- Robert, 59: low to moderate risk, 3-5 years, near retirement, preserve capital; tempted by hyped stocks. Test: push back on a request that conflicts with his profile.

## Our solution
An advisor-style simulation. A judge confirmed this framing is allowed if it is clearly labelled as a simulation, not personalized advice.

1. Questionnaire (checkboxes and single choices). "I'm not sure" on hard questions opens a short chat; the agent maps the conversation back to a form answer and the user confirms.
2. Scoring in code: risk capacity (horizon, liquidity, income stability) and risk tolerance (loss reaction, trade-off, experience), each 1-6. Risk level = the lower of the two.
3. Profile = risk band (low 1-2, medium 3-4, high 5-6) x investment style (Broad diversifier, Home country, Growth and innovation, Income and stability, Responsible ESG) = 15 profiles, plus flags (crypto allowed, ESG screen, exclusions, home bias).
4. Each profile has a reference portfolio built by rules (docs/portfolio_rules.md, backend/src/alphaforge/domain/reference_portfolios.py) and validated against its band's limits.
5. The user proposes an action (e.g. "move 20% into TSLA"). Agents analyze it against the profile and explain whether it fits, with sourced numbers, assumptions, limits and alternatives. The trace of agent and tool calls is shown.

Persona mapping (validation test): Robert -> profile 4, Mateo -> profile 10, Amira -> profile 13.

## Agents
- Orchestrator: decides which specialists to call, writes the final explained answer.
- Risk analyst: calls the risk tools (risk_measures, portfolio_compare, correlations); reports numbers with source, period, currency. Never judges fit.
- ESG evidence: finds and cites ESG/controversy evidence (no ESG data in the starter set).
- Governance checker: independent check of the proposal against the profile's limits and the simulation-only rules. Hard limits are Python rules; the model explains. In the implemented engine this is `evaluate()` (see below), not a separate agent call.
- Profile loading and scoring are plain functions, not agents.

## Engine (implemented, portfolio_engine.py — Jeffrey's error model)
- `apply_changes()` raises `ProposalError` for anything invalid or unfundable: unknown ticker, a bond targeted directly, insufficient funds to cover a request, malformed input. It never silently no-ops an invalid request.
- `evaluate()` never throws. It always returns one of four statuses: `PASS`, `CONFLICT` (a well-formed request that breaks a limit), `INVALID_REQUEST` (malformed or unfundable), `MISSING_INFO` (e.g. data unavailable, or crypto permission unknown).
- `profiles.json` is read-only to the engine, and to every user action — see "User portfolios" below for where a confirmed change actually lives.

## User portfolios (per-session; not profiles.json)
- `profiles.json` is a read-only catalog of the 15 base profiles. No user action ever modifies it.
- Each user instead has their own record: `portfolio_profile` (1-15, from profile_mapping) plus a cumulative list of confirmed changes.
- Flow: a new change starts as a draft -> `evaluate(portfolio_profile, all_changes)` -> an agent explains the result -> the user keeps it (appended to the cumulative list) or undoes it (dropped).
- Stored at `user_portfolios/{session_id}.json` (gitignored), written through one function so Jeffrey can swap the storage backend for S3 without changing callers.
- Customization is free. Every change runs through `evaluate()` first; the agent shows the consequences and the max that fits. If the user keeps a change that breaks their limits, the portfolio is labelled "Outside your profile: simulation only" (`outside_profile = true`). Caps are guidance, not hard blocks.
- Wording: say "outside your stated limits," not "not recommended" — it's a mismatch with what the user told the system about themselves, not unsolicited advice being withheld.

## Key files
- profiles.json: the contract. Band limits, 15 profiles with weights and validation results. Read-only catalog; never modified per user (see "User portfolios").
- backend/src/alphaforge/domain/reference_portfolios.py: builds profiles.json from the rules.
- backend/src/alphaforge/presentation/backtest_viewer.py: Streamlit page to inspect each profile's backtest.

## Open decisions
- Final asset list (team is picking its own assets; rebuild data with the starter generator in backend/scripts/build_dataset.py).
- Growth style is too aggressive for low and medium bands (profiles 3 and 8 needed trimming).
- ESG profiles are 100% U.S. (ESGV); consider adding a Canadian ESG ETF.
- Equal weights vs inverse-volatility weights inside groups.
- All limits and thresholds are team assumptions; document them in the technical documentation.

# Repo and teamwork (read before changing anything)

- Repo: https://github.com/JayjayGz/RecommenDathon. My work is on branch `portfolios`. Never switch branches or commit to a teammate's branch (`agents`, `test`) without asking.
- Only stage files I name or that you created for me. Never `git add .` or `git add docs` (teammates have uncommitted files in docs/). In docs/, I can commit my own files by name (DATA.md, portfolio_rules.md, or any file I tell you to add) — never commit teammates' docs.
- Data CSVs live in `dataset/` and are committed to the repo (team decision, KC-ZEUS) — check Yahoo's redistribution terms before making the repo public. See docs/DATA.md.
- Teammates' design docs: docs/architecture.md, docs/agent-responsibilities.md, docs/aws-services.md, docs/investor-profile-schema.json, docs/pipeline.mmd. Treat them as the team's source of truth; flag any conflict with this file instead of overwriting them.

# My files

- backend/scripts/build_portfolios.py: builds the 15 reference portfolios from rules and validates them against band limits. Run: `python backend/scripts/build_portfolios.py dataset profiles.json`
- backend/scripts/backtest_viewer.py: Streamlit page to inspect profile backtests. Run: `python -m streamlit run backend/scripts/backtest_viewer.py` (the sidebar defaults to dataset/)
- profiles.json: output contract read by the questionnaire, agents and app.
- docs/portfolio_rules.md: the allocation rules in words. Keep it in sync with backend/src/alphaforge/domain/reference_portfolios.py.
- dataset/asset_selection.csv and backend/scripts/universe_v2.py: our own 34-ticker universe (replaces the starter tickers once the data is rebuilt with build_dataset.py).
- backend/src/alphaforge/domain/profile_mapping.py: maps the questionnaire's 8 answers to one of the 15 profiles (band + style) plus flags. Tests in backend/tests/test_profile_mapping.py. See "Pending decisions" for the known gaps (no home-country or ESG signal in the questionnaire yet).

# Pending decisions (proposed, not yet applied)

- Growth style in low and medium bands: QQQ 50, broad U.S. 25, broad Canada 25; single tech stocks only in the high band.
- Crypto weights allow half percentages.
- After the universe_v2 data is rebuilt, map the rules to the new tickers (e.g. broad style = XIC.TO, VFV.TO, XEF.TO) and rerun validation.
- Check docs/investor-profile-schema.json against the profiles.json structure and reconcile.

# How I want to work

I'm learning: explain what you change and why, in plain language. I write the risk calculation module (backend/src/alphaforge/application/risk.py) myself; review it and write tests for it, but don't write it for me unless I ask.
