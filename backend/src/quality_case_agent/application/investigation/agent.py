"""Bounded, provider-neutral Case investigation Agent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from quality_case_agent.application.ports.llm import LLMClient, LLMRequest
from quality_case_agent.contracts.investigation import (
    AgentTraceEventContract,
    EvidenceContract,
    HypothesisContract,
    InvestigationAnalysisContract,
    InvestigationOutputContract,
    InvestigationTraceContract,
    ProposalContract,
    ProposalStepContract,
)
from quality_case_agent.domain.investigation.models import ToolObservation

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
    """Run a small ReAct loop where every external action is allowlisted."""

    def __init__(
        self,
        llm: LLMClient,
        tools: ReadOnlyInvestigationTools,
        limits: AgentLimits | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._limits = limits or AgentLimits()

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

        for iteration in range(self._limits.max_iterations):
            response = self._llm.complete(
                LLMRequest(
                    run_id=run_id,
                    iteration=iteration,
                    context=dict(context),
                    available_tools=self._tools.names,
                    system_instruction=HISTORICAL_CASE_EVIDENCE_POLICY,
                )
            )
            decision = response.decision
            if decision.kind == "FINAL":
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
            if decision.action not in self._tools.names:
                failures += 1
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
            observation = self._tools.invoke(decision.action, decision.arguments)
            observations.append(observation)
            completed_tools.add(decision.action)
            context["completed_tools"] = tuple(sorted(completed_tools))
            if observation.success:
                if decision.action == "get_case_snapshot":
                    context["snapshot"] = dict(observation.payload)
                if decision.action == "search_knowledge_base":
                    context["knowledge"] = dict(observation.payload)
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
        analysis, proposal = self._build_output(
            run_id,
            case_id,
            snapshot_id,
            snapshot_payload,
            observations,
            status,
            final_reason,
        )
        return InvestigationOutputContract(
            analysis=analysis,
            proposal=proposal,
            trace=InvestigationTraceContract(analysis_run_id=run_id, events=trace),
        )

    def _build_output(
        self,
        run_id: str,
        case_id: str,
        snapshot_id: str,
        snapshot_payload: object,
        observations: list[ToolObservation],
        status: str,
        final_reason: str,
    ) -> tuple[InvestigationAnalysisContract, ProposalContract | None]:
        evidence: list[EvidenceContract] = []
        snapshot = snapshot_payload if isinstance(snapshot_payload, dict) else {}
        trigger_family = str(snapshot.get("trigger_family", "FIXTURE_OFFSET"))
        hypothesis_id = "H-ILL-01" if trigger_family == "ILLUMINATION_DRIFT" else "H-01"
        data_quality_warnings = [
            str(item)
            for item in snapshot.get("data_quality_warnings", [])
            if isinstance(item, str)
        ]
        data_quality_observation = next(
            (
                observation
                for observation in observations
                if observation.tool_name == "check_data_quality" and observation.success
            ),
            None,
        )
        data_quality_blocked = bool(data_quality_warnings) or (
            status == "INSUFFICIENT_EVIDENCE" and "DATA_QUALITY_BLOCKED" in final_reason
        )
        evidence_supports = [] if data_quality_blocked else [hypothesis_id]
        raw_windows = snapshot.get("observations", [])
        if isinstance(raw_windows, list) and raw_windows:
            first = raw_windows[0]
            if isinstance(first, dict):
                ng_rate = float(first.get("ng_rate", 0.0))
                upper_right = (
                    float(first.get("region_counts", {}).get("upper_right", 0))
                    if isinstance(first.get("region_counts", {}), dict)
                    else 0.0
                )
                ev_id = "EV-A-001"
                evidence.append(
                    EvidenceContract(
                        evidence_id=ev_id,
                        evidence_class="A",
                        evidence_type="CURRENT_SNAPSHOT",
                        reference=f"{snapshot_id}#/observations",
                        claim=f"Snapshot包含{len(raw_windows)}个异常窗口，首窗口NG率为{ng_rate:.2f}，upper_right NG计数为{upper_right:.0f}",
                        supports=evidence_supports,
                        applicability="DIRECT",
                    )
                )
        comparison = next(
            (
                observation
                for observation in observations
                if observation.tool_name == "compare_quality_metrics" and observation.success
            ),
            None,
        )
        if comparison is not None:
            evidence.append(
                EvidenceContract(
                    evidence_id="EV-A-002",
                    evidence_class="A",
                    evidence_type="METRIC_COMPARISON",
                    reference=f"{snapshot_id}#/metric-comparison",
                    claim="异常窗口指标对比显示NG率和空间分布持续偏离基线",
                    supports=evidence_supports,
                    applicability="DIRECT",
                )
            )
        knowledge = next(
            (
                observation
                for observation in observations
                if observation.tool_name == "search_knowledge_base" and observation.success
            ),
            None,
        )
        historical_references: list[str] = []
        if knowledge is not None:
            items = knowledge.payload.get("items", [])
            if isinstance(items, list):
                for index, item in enumerate(items[: self._limits.top_k_per_retrieval], start=1):
                    if not isinstance(item, dict):
                        continue
                    source_type = str(item.get("source_type", "TECHNICAL_DOCUMENT"))
                    evidence_class: Literal["B", "C"] = (
                        "C" if source_type == "VERIFIED_CASE" else "B"
                    )
                    archive_uri = item.get("archive_uri")
                    reference = (
                        str(archive_uri)
                        if source_type == "VERIFIED_CASE" and isinstance(archive_uri, str)
                        else str(item.get("evidence_id", "knowledge:unknown"))
                    )
                    claim = str(item.get("content", ""))[:1_800]
                    if source_type == "VERIFIED_CASE":
                        historical_references.append(reference)
                        claim = f"历史案例摘要（仅C级经验，不能证明本次根因）：{claim}"
                    evidence.append(
                        EvidenceContract(
                            evidence_id=f"EV-{evidence_class}-{index:03d}",
                            evidence_class=evidence_class,
                            evidence_type=source_type,
                            reference=reference,
                            claim=claim,
                            supports=evidence_supports,
                            applicability=(
                                "CONTEXTUAL" if source_type == "VERIFIED_CASE" else "APPLICABLE"
                            ),
                            retrieved_at=self._snapshot_created_at(snapshot),
                        )
                    )
        samples = next(
            (
                observation
                for observation in observations
                if observation.tool_name == "get_representative_samples" and observation.success
            ),
            None,
        )
        if samples is not None:
            items = samples.payload.get("items", [])
            sample_count = len(items) if isinstance(items, list) else 0
            evidence.append(
                EvidenceContract(
                    evidence_id="EV-A-003",
                    evidence_class="A",
                    evidence_type="REPRESENTATIVE_SAMPLES",
                    reference=f"{snapshot_id}#/representative-samples",
                    claim=f"从当前Snapshot提取{sample_count}个异常/正常代表性样本供人工复核",
                    supports=evidence_supports,
                    applicability="DIRECT",
                )
            )
        evidence_ids = [item.evidence_id for item in evidence]
        has_current = any(item.evidence_class == "A" for item in evidence)
        complete = status == "COMPLETED" and has_current
        if not complete:
            status = "INSUFFICIENT_EVIDENCE" if status == "COMPLETED" else status
        hypotheses = []
        proposal = None
        if has_current and not data_quality_blocked:
            if trigger_family == "ILLUMINATION_DRIFT":
                hypotheses.append(
                    HypothesisContract(
                        hypothesis_id=hypothesis_id,
                        title="光照或曝光状态发生漂移",
                        description=(
                            "异常分数和NG率整体抬升，同时缺少单一缺陷区域聚集；这与光源亮度、光源角度、"
                            "相机曝光或增益漂移的特征一致，仍需现场参数和基准件复测确认。"
                        ),
                        confidence=0.72
                        if any(item.evidence_class == "B" for item in evidence)
                        else 0.45,
                        supporting_evidence_ids=evidence_ids,
                        contradicting_evidence_ids=[],
                        missing_evidence=["当前光照强度记录", "相机曝光参数和光源角度"],
                    )
                )
            else:
                hypotheses.append(
                    HypothesisContract(
                        hypothesis_id=hypothesis_id,
                        title="夹具定位偏移或定位销状态异常",
                        description="NG样本在upper_right区域持续聚集，与夹具定位偏移的空间特征一致；当前证据仍需现场测量确认。",
                        confidence=0.86
                        if any(item.evidence_class == "B" for item in evidence)
                        else 0.62,
                        supporting_evidence_ids=evidence_ids,
                        contradicting_evidence_ids=[],
                        missing_evidence=["定位销间隙测量值", "基准件复测位置偏移量"],
                    )
                )

        if complete and any(item.evidence_class == "B" for item in evidence):
            if trigger_family == "ILLUMINATION_DRIFT":
                proposal = ProposalContract(
                    proposal_id=f"prop-{run_id}",
                    case_id=case_id,
                    analysis_run_id=run_id,
                    created_at=self._snapshot_created_at(snapshot),
                    title="检查光源、曝光与相机校准状态",
                    reason="当前分数整体抬升且缺少单一空间聚集，适用光照维护手册支持优先检查亮度、光源角度和曝光参数。",
                    steps=[
                        ProposalStepContract(
                            order=1,
                            instruction="测量当前光源亮度并检查光源角度",
                            expected_evidence="光照强度记录和光源角度",
                        ),
                        ProposalStepContract(
                            order=2,
                            instruction="核对相机曝光时间、增益和自动曝光状态",
                            expected_evidence="相机曝光参数快照",
                        ),
                        ProposalStepContract(
                            order=3,
                            instruction="使用基准件执行光照/相机校准复测",
                            expected_evidence="校准前后基准件分数和图像",
                        ),
                    ],
                    requested_role="QUALITY_ENGINEER",
                    priority="HIGH",
                    risk_level="LOW",
                    evidence_ids=evidence_ids,
                )
            else:
                proposal = ProposalContract(
                    proposal_id=f"prop-{run_id}",
                    case_id=case_id,
                    analysis_run_id=run_id,
                    created_at=self._snapshot_created_at(snapshot),
                    title="检查camera-01工位夹具定位状态",
                    reason="当前Snapshot的区域聚集与适用夹具手册均支持优先检查定位销；历史案例仅作为C级经验，不作为根因证明。",
                    steps=[
                        ProposalStepContract(
                            order=1,
                            instruction="测量定位销间隙",
                            expected_evidence="定位销间隙测量值",
                        ),
                        ProposalStepContract(
                            order=2,
                            instruction="使用基准件复测工件位置",
                            expected_evidence="基准件位置偏移量",
                        ),
                        ProposalStepContract(
                            order=3,
                            instruction="检查最近一次换线记录",
                            expected_evidence="换线时间和操作记录",
                        ),
                    ],
                    requested_role="QUALITY_ENGINEER",
                    priority="HIGH",
                    risk_level="LOW",
                    evidence_ids=evidence_ids,
                )
        required_information: list[str] = []
        if data_quality_observation is not None:
            raw_required = data_quality_observation.payload.get("required_information", [])
            if isinstance(raw_required, list):
                required_information.extend(str(item) for item in raw_required)
        if data_quality_blocked and not required_information:
            if "INSUFFICIENT_SAMPLE_COUNT" in data_quality_warnings:
                required_information.append("统一模型版本后的至少500条检测记录")
            if "MIXED_MODEL_VERSIONS" in data_quality_warnings:
                required_information.append("统一模型版本后的检测记录")
            if "DATA_MISSING" in data_quality_warnings:
                required_information.append("补齐原始检测记录与图像URI")
        if data_quality_blocked:
            status = "INSUFFICIENT_EVIDENCE"
        if data_quality_blocked:
            summary = "数据质量被阻断，未对当前Case形成根因假设；请补充所需信息后重新分析。"
        elif complete and trigger_family == "ILLUMINATION_DRIFT":
            summary = "光照/曝光漂移假设得到当前指标与适用维护手册支持，已形成待人工审批的排查Proposal。"
        elif complete:
            summary = "当前Case与夹具定位偏移假设一致，已形成待人工审批的排查Proposal。"
        else:
            summary = "当前证据不足以形成可执行的确定性调查结论。"
        analysis = InvestigationAnalysisContract(
            analysis_run_id=run_id,
            case_id=case_id,
            snapshot_id=snapshot_id,
            status=status,  # type: ignore[arg-type]
            summary=summary,
            evidence=evidence,
            hypotheses=hypotheses,
            limitations=[
                "Agent仅使用只读质量工具和知识检索，不执行任意SQL/Python或QMS写操作。",
                "历史案例相似度未转换为根因置信度，仍需人工验证。",
                *(
                    [
                        "历史案例属于C级经验，只能提供候选排查方向，不能证明当前Case根因。",
                        f"历史案例完整归档可回查：{', '.join(historical_references)}",
                    ]
                    if historical_references
                    else []
                ),
                *(
                    [
                        "数据质量检查阻断了根因分析，Agent未生成确定性根因或行动Proposal。",
                        f"数据质量警告：{', '.join(data_quality_warnings)}",
                    ]
                    if data_quality_blocked
                    else []
                ),
            ],
            required_information=required_information,
            termination_reason=final_reason,
        )
        return analysis, proposal

    @staticmethod
    def _stable_run_id(case_id: str, snapshot_id: str) -> str:
        value = uuid5(NAMESPACE_URL, f"quality-case-agent:{case_id}:{snapshot_id}")
        return f"ar-{value.hex[:16]}"

    @staticmethod
    def _snapshot_created_at(snapshot: dict[str, object]) -> datetime:
        value = snapshot.get("created_at")
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        return datetime(1970, 1, 1, tzinfo=UTC)
