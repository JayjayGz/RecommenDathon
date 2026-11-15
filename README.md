# AlphaForge / Recommand

An educational portfolio simulation for the AlphaForge datathon. The French web interface collects a questionnaire and displays illustrative results; Python computes portfolio changes, historical metrics and policy checks. Bedrock supplies a text-generation adapter. No transactions are performed.

## Repository layout

```text
plateforme/                       Web presentation: index.html, src/, assets/, HTTP proxy
backend/src/alphaforge/
  presentation/backtest_viewer.py  Streamlit reference-portfolio viewer
  application/                  PortfolioEngine, reference build/comparison, storage and LLM ports
  domain/                       Pure allocation, proposal, calendar, FX and backtest functions
  infrastructure/               Local CSV/JSON repository and Bedrock adapter
  bootstrap.py                  Local application/infrastructure composition
backend/scripts/                Dataset/profile build, viewer and Bedrock entry points
backend/tests/                  Offline regressions, adapters and dataset compatibility checks
backend/pyproject.toml          Python package configuration
backend/requirements.txt        Python dependencies
scripts/                        Project workflow checks
dataset/                       Local CSV inputs and dataset README (CSVs ignored by Git)
profiles.json                   Existing 15-profile contract; unchanged by reorganization
docs/                           Architecture, calculation API, data and AWS documentation
agents/                         Flat development role instructions
memory/                         Scoped development lessons
```

The Git root is the inner `RecommenDathon/` directory containing this README and `AGENTS.md`. Run the commands below there. See [architecture and migration map](docs/architecture.md).

## Run locally

For the connected website and Python backend, use the existing root `.env` and
run `node scripts/start_local.mjs` from this directory, then open
http://localhost:4173. It loads configuration and starts both services; Ctrl+C
stops both. `--offline` uses the deterministic explanation without model calls.
See [local setup and verification](docs/local-development.md).

Python 3.10+:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pip install -e ./backend
python -m pytest
python -m streamlit run backend/scripts/backtest_viewer.py
```

On Linux/macOS, activate with `source .venv/bin/activate`. An existing interpreter/environment can be reused. The viewer defaults to `dataset/` and reads `profiles.json` at the Git root.

Web UI (Node.js 24+, no npm dependencies):

```powershell
cd plateforme
npm start
```

Open http://localhost:4173. See [frontend setup](plateforme/README.md) and its [HTTP contracts](plateforme/docs/AGENT_INTEGRATION.md) for optional external services.

## Use the calculation API

After installing the package:

```python
from alphaforge.bootstrap import create_engine

engine = create_engine()
profile = engine.get_profile(4)
result = engine.evaluate(4, [{"ticker": "TSLA", "add_pct": 20}])
```

Tests run from the Git root or `backend/`; each `pytest.ini` resolves the backend package source. Scripts resolve the package relative to their own location. Runtime application code accepts a `PortfolioRepository` port; `create_engine()` wires the local implementation. See [API behavior](docs/portfolio_api.md).

## Current status and limitations

- Calculations, proposal validation, offline Bedrock tests and a local UI are implemented.
- `dataset/prices_weekly.csv` is the active prices file. Weekly observations annualize at 52/year; actual daily history remains supported at 252/year. See the [data notes](docs/DATA.md) for snapshot coverage and FX conventions. Saved results from older methods need a fresh evaluation.
- The per-ticker risk module remains an unimplemented teammate-owned contract at `backend/src/alphaforge/application/risk.py`.
- The [proposal workflow](docs/orchestrator.md) connects the Lambda handler, engine, evidence, constrained explanations, release checks and S3/local auditing. Questionnaire reference matching, follow-up requests and the local HTTP proxy are implemented. Broader financial-risk-capacity scoring, ESG screening, per-ticker risk and deployed endpoint configuration remain pending. Unconnected web portfolios are illustrative.
- [Portfolio review and optional alternatives](docs/portfolio-review.md) provide deterministic composition, direct-stock sector coverage, concentration, risk and profile findings, plus bounded engine-checked suggestions and cited trade-offs.
- Dataset downloads, profile regeneration and AWS calls are explicit operations; tests do not deploy or contact AWS.

Development instructions start at [AGENTS.md](AGENTS.md). The agreed deterministic pipeline is described in [architecture.md](docs/architecture.md); Strands roles in team notes are proposals, not an implemented runtime.

The [Lambda setup guide](docs/lambda-setup.md) covers container packaging and deployment.
Configure the existing input/audit buckets and reviewed runtime policy to enable
the proposal workflow; health checks work without that configuration.

### Questionnaire matching and personalization

The backend now accepts the supplied French questionnaire, matches an existing reference profile using the approved risk-band map and sourced preference metadata, and evaluates personalized additions against that profile. Read [the workflow and API contracts](docs/questionnaire-workflow.md). New requests require `assets_universe.csv` alongside the existing snapshot inputs, plus `macro_rates.csv` only for evaluated bond assets; missing reference price history still blocks portfolio release. No live deployment is implied.
