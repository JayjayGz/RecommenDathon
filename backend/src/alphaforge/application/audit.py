"""Required run persistence port. result.json is the final commit record."""
from typing import Protocol

ARTIFACTS = ("profile", "data_manifest", "evidence", "decisions", "llm_calls", "compliance", "result")


class AuditStore(Protocol):
    def save(self, run_id: str, artifacts: dict) -> None:
        """Write all artifacts, result last; raise on any failed write."""
        ...
