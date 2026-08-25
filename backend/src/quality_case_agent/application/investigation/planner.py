"""Investigation planning from a validated Runbook and immutable Snapshot."""

from dataclasses import dataclass

from quality_case_agent.domain.runbook.models import Runbook


@dataclass(frozen=True, slots=True)
class InvestigationPlan:
    runbook_id: str
    runbook_version: str
    required_tools: tuple[str, ...]
    knowledge_query: str

    def as_dict(self) -> dict[str, object]:
        return {
            "runbook_id": self.runbook_id,
            "runbook_version": self.runbook_version,
            "required_tools": list(self.required_tools),
            "knowledge_query": self.knowledge_query,
        }


class InvestigationPlanner:
    def plan(self, snapshot: dict[str, object], runbook: Runbook, available_tools: tuple[str, ...]) -> InvestigationPlan:
        warnings = snapshot.get("data_quality_warnings", [])
        required = [tool for tool in runbook.required_tools if tool in available_tools]
        if isinstance(warnings, list) and warnings and "check_data_quality" in available_tools:
            required.insert(1, "check_data_quality")
        return InvestigationPlan(
            runbook_id=runbook.runbook_id,
            runbook_version=runbook.version,
            required_tools=tuple(dict.fromkeys(required)),
            knowledge_query=runbook.knowledge_query,
        )
