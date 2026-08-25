"""Validated tool registry seam for read-only investigation tools."""

from dataclasses import dataclass

from quality_case_agent.domain.investigation.models import ToolObservation

from .tools import ReadOnlyInvestigationTools


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    required_arguments: tuple[str, ...] = ()


class ToolRegistry:
    def __init__(self, tools: ReadOnlyInvestigationTools) -> None:
        self._tools = tools
        self._specs = {
            name: ToolSpec(name)
            for name in tools.names
        }

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def invoke(self, name: str, arguments: dict[str, object]) -> ToolObservation:
        spec = self._specs.get(name)
        if spec is None:
            return ToolObservation(name, False, "工具不在只读 Runbook allowlist 中", {})
        missing = [key for key in spec.required_arguments if key not in arguments]
        if missing:
            return ToolObservation(name, False, f"缺少必需参数：{', '.join(missing)}", {})
        return self._tools.invoke(spec.name, arguments)
