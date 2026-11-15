"""Run a proposal assessment locally, with real local inputs and no model call."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alphaforge.application.contracts import RecommendationRequest, RequestError
from alphaforge.application.investor_requests import InvestorRequest
from alphaforge.application.orchestrator import RecommendationOrchestrator
from alphaforge.infrastructure.local_data import DEFAULT_DATA_DIR, DEFAULT_PROFILES_PATH
from alphaforge.infrastructure.workflow_storage import LocalAuditStore, LocalSnapshotSource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=Path(__file__).resolve().parents[1] / "events/recommend.json")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES_PATH)
    parser.add_argument("--audit-dir", type=Path, default=Path(".local-runs"))
    args = parser.parse_args()
    try:
        payload = json.loads(args.event.read_text(encoding="utf-8"))["request"]
        if isinstance(payload, dict) and "questions" in payload and "langue" in payload:
            payload = {"questionnaire": payload}
        contract = InvestorRequest if isinstance(payload, dict) and "questionnaire" in payload else RecommendationRequest
        request = contract.from_dict(payload)
    except (OSError, ValueError, KeyError, RequestError):
        print("Invalid event file", file=sys.stderr)
        return 2
    workflow = RecommendationOrchestrator(LocalSnapshotSource(args.data_dir, args.profiles),
                                           LocalAuditStore(args.audit_dir))
    outcome = workflow.run(request)
    print(json.dumps(outcome.payload, indent=2, allow_nan=False))
    return 0 if outcome.status in {"PASS", "CONFLICT"} else 1


if __name__ == "__main__":
    sys.exit(main())
