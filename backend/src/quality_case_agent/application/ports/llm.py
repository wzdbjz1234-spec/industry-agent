"""Provider-neutral LLM tool-calling protocol."""

from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class LLMRequest:
    run_id: str
    iteration: int
    context: dict[str, object]
    available_tools: tuple[str, ...]
    system_instruction: str = ""


@dataclass(frozen=True, slots=True)
class LLMDecision:
    kind: Literal["TOOL_CALL", "FINAL", "STOP"]
    action: str
    arguments: dict[str, object] = field(default_factory=dict)
    summary: str = ""


@dataclass(frozen=True, slots=True)
class LLMResponse:
    model: str
    decision: LLMDecision


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return one bounded decision; no provider SDK leaks through this port."""
