"""Bounded, provider-neutral Case investigation Agent."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from quality_case_agent.application.ports.llm import LLMClient, LLMRequest
from quality_case_agent.contracts.investigation import (
    AgentTraceEventContract,
    InvestigationOutputContract,
    InvestigationTraceContract,
)
from quality_case_agent.domain.investigation.models import ToolObservation

from .module import InvestigationRequest
from .planner import InvestigationPlanner
from .runbooks import RunbookRegistry
from .synthesizer import InvestigationSynthesizer
from .tool_registry import ToolRegistry
from .tools import ReadOnlyInvestigationTools

HISTORICAL_CASE_EVIDENCE_POLICY = (
    "历史案例是C级经验依据，只能生成候选排查方向；不得把相似度、历史根因或历史验证结果 "
    "当作当前Case根因证明。当前结论必须绑定本次Case的A级事实；行动Proposal还必须有适用的B级规范依据。"
)


@dataclass(frozen=True, slots=True)
class AgentLimits:
    max_iterations: int = 8
    max_tool_failures: int = 3
    max_retrieval_calls: int = 6
    top_k_per_retrieval: int = 5


class InvestigationAgent:
    """Run a bounded ReAct loop behind the generic InvestigationModule seam."""

    def __init__(
        self,
        llm: LLMClient,
        tools: ReadOnlyInvestigationTools,
        limits: AgentLimits | None = None,
        runbook_registry: RunbookRegistry | None = None,
    ) -> None:
        self._llm = llm
        self._limits = limits or AgentLimits()
        self._tool_registry = ToolRegistry(tools)
        self._runbooks = runbook_registry or RunbookRegistry()
        self._planner = InvestigationPlanner()
        self._synthesizer = InvestigationSynthesizer(
            model_version=getattr(llm, "model", None),
        )

    def investigate(self, request: InvestigationRequest) -> InvestigationOutputContract:
        return self.analyze(
            request.case_id,
            request.snapshot_id,
            analysis_run_id=request.analysis_run_id,
        )

    def analyze(
        self,
        case_id: str,
        snapshot_id: str,
        *,
        analysis_run_id: str | None = None,
    ) -> InvestigationOutputContract:
        run_id = analysis_run_id or self._stable_run_id(case_id, snapshot_id)
        trace: list[AgentTraceEventContract] = [
            AgentTraceEventContract(
                sequence=1,
                event_type="STARTED",
                iteration=0,
                action="investigation_started",
                arguments={"case_id": case_id, "snapshot_id": snapshot_id},
                summary="加载不可变 Case Snapshot，启动有界调查",
            )
        ]
        observations: list[ToolObservation] = []
        completed_tools: set[str] = set()
        context: dict[str, object] = {
            "case_id": case_id,
            "snapshot_id": snapshot_id,
            "snapshot": {"case_id": case_id, "snapshot_id": snapshot_id},
            "completed_tools": (),
        }
        failures = 0
        retrieval_calls = 0
        sequence = 1
        final_reason = ""
        status = "COMPLETED"
        draft_payload: dict[str, object] | None = None

        for iteration in range(self._limits.max_iterations):
            response = self._llm.complete(
                LLMRequest(
                    run_id=run_id,
                    iteration=iteration,
                    context=dict(context),
                    available_tools=self._tool_registry.names,
                    system_instruction=HISTORICAL_CASE_EVIDENCE_POLICY,
                )
            )
            decision = response.decision
            if decision.kind == "FINAL":
                draft_payload = decision.draft
                sequence += 1
                trace.append(
                    AgentTraceEventContract(
                        sequence=sequence,
                        event_type="FINAL",
                        iteration=iteration,
                        action=decision.action,
                        arguments={},
                        summary=decision.summary or "形成结构化调查输出",
                    )
                )
                final_reason = decision.summary or "完成预算内调查"
                break
            if decision.kind == "STOP":
                status = "INSUFFICIENT_EVIDENCE"
                final_reason = decision.summary or "模型请求安全停止"
                break
            if decision.action not in self._tool_registry.names:
                status = "FAILED"
                final_reason = "模型请求了未允许的工具"
                sequence += 1
                trace.append(
                    AgentTraceEventContract(
                        sequence=sequence,
                        event_type="TERMINATED",
                        iteration=iteration,
                        action=decision.action,
                        arguments=decision.arguments,
                        summary=final_reason,
                    )
                )
                break
            if decision.action == "search_knowledge_base":
                retrieval_calls += 1
                if retrieval_calls > self._limits.max_retrieval_calls:
                    status = "BUDGET_EXHAUSTED"
                    final_reason = "达到知识检索预算"
                    sequence += 1
                    trace.append(
                        AgentTraceEventContract(
                            sequence=sequence,
                            event_type="TERMINATED",
                            iteration=iteration,
                            action=decision.action,
                            arguments=decision.arguments,
                            summary=final_reason,
                        )
                    )
                    break
            sequence += 1
            trace.append(
                AgentTraceEventContract(
                    sequence=sequence,
                    event_type="TOOL_CALL",
                    iteration=iteration,
                    action=decision.action,
                    arguments=decision.arguments,
                    summary=decision.summary or "调用只读工具",
                )
            )
            observation = self._tool_registry.invoke(decision.action, decision.arguments)
            observations.append(observation)
            completed_tools.add(decision.action)
            context["completed_tools"] = tuple(sorted(completed_tools))
            if observation.success:
                self._update_context(context, decision.action, observation)
            else:
                failures += 1
            sequence += 1
            trace.append(
                AgentTraceEventContract(
                    sequence=sequence,
                    event_type="TOOL_RESULT",
                    iteration=iteration,
                    action=decision.action,
                    arguments={},
                    summary=observation.summary,
                    evidence_ids=list(observation.evidence_ids),
                )
            )
            if failures >= self._limits.max_tool_failures:
                status = "FAILED"
                final_reason = "连续只读工具失败达到上限"
                sequence += 1
                trace.append(
                    AgentTraceEventContract(
                        sequence=sequence,
                        event_type="TERMINATED",
                        iteration=iteration,
                        action=decision.action,
                        arguments={},
                        summary=final_reason,
                    )
                )
                break
        else:
            status = "BUDGET_EXHAUSTED"
            final_reason = "达到 Agent 轮次预算"

        if not final_reason:
            final_reason = "调查未形成最终输出"
        snapshot_payload = context.get("snapshot", {})
        runbook = self._runbooks.get(
            str(snapshot_payload.get("trigger_family", "DEFAULT"))
            if isinstance(snapshot_payload, dict)
            else "DEFAULT"
        )
        analysis, proposal = self._synthesizer.synthesize(
            run_id=run_id,
            case_id=case_id,
            snapshot_id=snapshot_id,
            snapshot_payload=snapshot_payload,
            observations=observations,
            status=status,
            final_reason=final_reason,
            runbook=runbook,
            draft=draft_payload,
        )
        return InvestigationOutputContract(
            analysis=analysis,
            proposal=proposal,
            trace=InvestigationTraceContract(analysis_run_id=run_id, events=trace),
        )

    def _update_context(
        self,
        context: dict[str, object],
        action: str,
        observation: ToolObservation,
    ) -> None:
        if action == "get_case_snapshot":
            context["snapshot"] = dict(observation.payload)
            snapshot = context["snapshot"]
            if isinstance(snapshot, dict):
                runbook = self._runbooks.get(str(snapshot.get("trigger_family", "DEFAULT")))
                context["investigation_plan"] = self._planner.plan(
                    snapshot,
                    runbook,
                    self._tool_registry.names,
                ).as_dict()
        elif action == "search_knowledge_base":
            context["knowledge"] = dict(observation.payload)

    @staticmethod
    def _stable_run_id(case_id: str, snapshot_id: str) -> str:
        value = uuid5(NAMESPACE_URL, f"quality-case-agent:{case_id}:{snapshot_id}")
        return f"ar-{value.hex[:16]}"
