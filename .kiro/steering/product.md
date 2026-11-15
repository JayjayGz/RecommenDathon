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
4. Each profile has a reference portfolio built by rules (docs/portfolio_rules.md, src/build_portfolios.py) and validated against its band's limits.
5. The user proposes an action (e.g. "move 20% into TSLA"). Agents analyze it against the profile and explain whether it fits, with sourced numbers, assumptions, limits and alternatives. The trace of agent and tool calls is shown.

Persona mapping (validation test): Robert -> profile 4, Mateo -> profile 10, Amira -> profile 13.

## Agents
- Orchestrator: decides which specialists to call, writes the final explained answer.
- Risk analyst: calls the risk tools (risk_measures, portfolio_compare, correlations); reports numbers with source, period, currency. Never judges fit.
- ESG evidence: finds and cites ESG/controversy evidence (no ESG data in the starter set).
- Governance checker: independent check of the proposal against the profile's limits and the simulation-only rules. Returns PASS, CONFLICT or MISSING_INFO with reasons. Hard limits are Python rules; the model explains.
- Profile loading and scoring are plain functions, not agents.

## Key files
- profiles.json: the contract. Band limits, 15 profiles with weights and validation results.
- src/build_portfolios.py: builds profiles.json from the rules.
- src/backtest_viewer.py: Streamlit page to inspect each profile's backtest.

## Open decisions
- Final asset list (team is picking its own assets; rebuild data with the starter kit's build_dataset.py).
- Growth style is too aggressive for low and medium bands (profiles 3 and 8 needed trimming).
- ESG profiles are 100% U.S. (ESGV); consider adding a Canadian ESG ETF.
- Equal weights vs inverse-volatility weights inside groups.
- All limits and thresholds are team assumptions; document them in the technical documentation.
