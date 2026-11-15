# AlphaForge backend

The Python backend lives here: `src/alphaforge/` contains presentation, application,
domain and infrastructure layers; `scripts/` contains developer entry points;
`tests/` contains offline regressions. `pyproject.toml` defines the package and
`requirements.txt` lists development dependencies.

From the repository root:

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -e ./backend
python -m pytest
python -m streamlit run backend/scripts/backtest_viewer.py
```

Tests can also run from this directory with `python -m pytest`.
After moving the package, rerun the editable install in any existing environment.
Imports remain `from alphaforge.bootstrap import create_engine`.

Shared CSV inputs remain in `../dataset/` and reference profiles in
`../profiles.json`. Runtime defaults resolve these paths independently of the
working directory. Explicit input/output paths are relative to the caller.
Project workflow checks remain at `../scripts/check_agent_workflow.py`.

See [project setup](../README.md) and [architecture](../docs/architecture.md).

For the Lambda handler, container build and separate AlphaForge deployment, see
[Lambda setup](../docs/lambda-setup.md). Recommendation requests now run the
[proposal workflow](../docs/orchestrator.md), with snapshot loading, evidence,
checked explanations and audit-before-release. Configure storage and the reviewed
runtime policy before enabling the deployed workflow.

## Migration verification

Infrastructure role; inputs were the existing Python package, scripts, tests and
package configuration. Shared dataset and profile locations were retained (lesson
L-006); L-001 and L-002 were loaded but their triggers were not engaged.

Outputs: this backend directory, updated repository defaults, test configuration,
launch commands and documentation. Status: complete. Next owner: backend developers.

Checks run with the existing workspace virtual environment:

- Root offline suite: 49 passed, 8 skipped, 2 xfailed; 17 subtests passed.
- From `backend/`, repository-layout suite: 6 passed.
- Portfolio-builder and Bedrock smoke-test `--help` entry points succeeded.
- Project workflow structural check and all eight checker self-tests passed.
- `git diff --check` passed; `profiles.json` has no diff.

The eight skips concern unavailable legacy dataset holdings; the two expected
failures concern the unimplemented risk module. No AWS calls, dataset downloads
or profile regeneration were performed.
