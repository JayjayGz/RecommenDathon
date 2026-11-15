"""Model-independent port for a single text generation, not an agent tool loop."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model_id: str
    stop_reason: str
    request_id: str | None
    usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict, repr=False)


class LLMCallError(RuntimeError):
    """Explicit model failure; raw output is for the audit store, never the UI."""

    def __init__(self, code: str, message: str, *, request_id: str | None = None,
                 raw_response: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.request_id = request_id
        self.raw_response = raw_response


class LLMClient(Protocol):
    def generate(self, *, system: str, prompt: str,
                 max_tokens: int = 1024) -> LLMResponse:
        """Generate once. The application owns validation and repair budgets."""
        ...
