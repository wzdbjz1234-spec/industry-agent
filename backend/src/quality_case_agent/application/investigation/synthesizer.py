"""Generic evidence synthesis from observations and a validated Runbook."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from quality_case_agent.contracts.investigation import (
    EvidenceContract,
    HypothesisContract,
    InvestigationAnalysisContract,
    ProposalContract,
)
from quality_case_agent.contracts.runbook import (
    InvestigationDraftContract,
    RunbookProposalContract,
)
from quality_case_agent.domain.investigation.models import ToolObservation
from quality_case_agent.domain.runbook.models import Runbook, RunbookProposal

from .grounding import EvidenceGroundingValidator
from .policy import InvestigationSafetyPolicy


class InvestigationSynthesizer:
    def __init__(
        self,
        *,
        grounding: EvidenceGroundingValidator | None = None,
        policy: InvestigationSafetyPolicy | None = None,
        model_version: str | None = None,
        toolset_version: str = "readonly-tools-v2",
        prompt_version: str = "investigation-policy-v2",
        retrieval_index_version: str = "knowledge-index-v1",
    ) -> None:
        self._grounding = grounding or EvidenceGroundingValidator()
        self._policy = policy or InvestigationSafetyPolicy()
        self._model_version = model_version
        self._toolset_version = toolset_version
        self._prompt_version = prompt_version
        self._retrieval_index_version = retrieval_index_version

    def synthesize(
        self,
        *,
        run_id: str,
        case_id: str,
        snapshot_id: str,
        snapshot_payload: object,
        observations: list[ToolObservation],
        status: str,
        final_reason: str,
        runbook: Runbook,
        draft: dict[str, object] | None = None,
    ) -> tuple[InvestigationAnalysisContract, ProposalContract | None]:
        snapshot = snapshot_payload if isinstance(snapshot_payload, dict) else {}
        warnings = tuple(
            str(item) for item in snapshot.get("data_quality_warnings", []) if isinstance(item, str)
        )
        evidence = self._evidence(snapshot, snapshot_id, observations)
        validated_draft = self._validated_draft(draft)
        current_ids = [item.evidence_id for item in evidence if item.evidence_class == "A"]
        applicable_ids = [item.evidence_id for item in evidence if item.evidence_class in {"A", "B"}]
        complete = status == "COMPLETED" and bool(current_ids)
        hypothesis = runbook.candidate_hypotheses[0] if runbook.candidate_hypotheses else None
        draft_hypothesis = validated_draft.hypothesis if validated_draft is not None else None
        hypotheses: list[HypothesisContract] = []
        if complete and (hypothesis is not None or draft_hypothesis is not None):
            if draft_hypothesis is not None:
                hypothesis_id = draft_hypothesis.hypothesis_id
                hypothesis_title = draft_hypothesis.title
                hypothesis_description = draft_hypothesis.description
                hypothesis_confidence = draft_hypothesis.confidence
                hypothesis_missing = list(draft_hypothesis.missing_evidence)
            else:
                assert hypothesis is not None
                hypothesis_id = hypothesis.hypothesis_id
                hypothesis_title = hypothesis.title
                hypothesis_description = hypothesis.description
                hypothesis_confidence = hypothesis.default_confidence
                hypothesis_missing = list(hypothesis.missing_evidence)
            hypotheses.append(
                HypothesisContract(
                    hypothesis_id=hypothesis_id,
                    title=hypothesis_title,
                    description=hypothesis_description,
                    confidence=hypothesis_confidence if any(item.evidence_class == "B" for item in evidence) else min(hypothesis_confidence, 0.62),
                    supporting_evidence_ids=applicable_ids,
                    contradicting_evidence_ids=[],
                    missing_evidence=list(hypothesis_missing),
                )
            )
        proposal_source: RunbookProposal | RunbookProposalContract | None = runbook.proposal
        if validated_draft is not None and validated_draft.proposal is not None and proposal_source is not None:
            proposal_source = validated_draft.proposal
        proposal = self._proposal(run_id, case_id, snapshot, proposal_source, applicable_ids) if complete and proposal_source and any(item.evidence_class == "B" for item in evidence) else None
        provisional = InvestigationAnalysisContract(
            analysis_run_id=run_id,
            case_id=case_id,
            snapshot_id=snapshot_id,
            status=cast(
                Literal["COMPLETED", "INSUFFICIENT_EVIDENCE", "BUDGET_EXHAUSTED", "FAILED"],
                "COMPLETED" if complete else ("INSUFFICIENT_EVIDENCE" if status == "COMPLETED" else status),
            ),
            summary="已收集当前事实、指标对比和适用知识证据" if complete else "当前证据不足以形成可执行的确定性调查结论。",
            evidence=evidence,
            hypotheses=hypotheses,
            limitations=["Agent 仅使用只读质量工具和知识检索，不执行任意 SQL/Python 或 QMS 写操作。"],
            required_information=[],
            termination_reason=final_reason,
            runbook_id=runbook.runbook_id,
            runbook_version=runbook.version,
            toolset_version=self._toolset_version,
            prompt_version=self._prompt_version,
            model_version=self._model_version,
            retrieval_index_version=self._retrieval_index_version,
        )
        grounding = self._grounding.validate(provisional, proposal)
        policy = self._policy.decide(data_quality_warnings=warnings, grounding=grounding, complete=complete)
        final_status = policy.status_override or provisional.status
        final_hypotheses = provisional.hypotheses if policy.allow_hypotheses else []
        final_proposal = proposal if policy.allow_proposal else None
        limitations = [*provisional.limitations, *policy.limitations]
        if any(item.evidence_type == "VERIFIED_CASE" for item in evidence):
            limitations.append("历史案例属于C级经验，只能提供候选排查方向，不能证明当前Case根因。")
        analysis = provisional.model_copy(
            update={
                "status": final_status,
                "hypotheses": final_hypotheses,
                "limitations": limitations,
                "required_information": list(policy.required_information),
                "summary": (
                    "数据质量被阻断，未对当前 Case 形成根因假设；请补充所需信息后重新分析。"
                    if warnings
                    else provisional.summary
                ),
            }
        )
        return analysis, final_proposal

    @staticmethod
    def _evidence(snapshot: dict[str, object], snapshot_id: str, observations: list[ToolObservation]) -> list[EvidenceContract]:
        evidence: list[EvidenceContract] = []
        raw_windows = snapshot.get("observations", [])
        if isinstance(raw_windows, list) and raw_windows:
            first = raw_windows[0] if isinstance(raw_windows[0], dict) else {}
            ng_rate = float(first.get("ng_rate", 0.0)) if isinstance(first, dict) else 0.0
            evidence.append(EvidenceContract(
                evidence_id="EV-A-001",
                evidence_class="A",
                evidence_type="CURRENT_SNAPSHOT",
                reference=f"{snapshot_id}#/observations",
                claim=f"Snapshot包含{len(raw_windows)}个异常窗口，首窗口NG率为{ng_rate:.2f}",
                supports=[],
                applicability="DIRECT",
            ))
        if any(item.tool_name == "compare_quality_metrics" and item.success for item in observations):
            evidence.append(EvidenceContract(
                evidence_id="EV-A-002",
                evidence_class="A",
                evidence_type="METRIC_COMPARISON",
                reference=f"{snapshot_id}#/metric-comparison",
                claim="异常窗口指标对比显示NG率和分数分布持续偏离基线",
                supports=[],
                applicability="DIRECT",
            ))
        knowledge = next((item for item in observations if item.tool_name == "search_knowledge_base" and item.success), None)
        if knowledge is not None:
            raw_items = knowledge.payload.get("items", [])
            if isinstance(raw_items, list):
                for index, item in enumerate(raw_items[:5], start=1):
                    if not isinstance(item, dict):
                        continue
                    source_type = str(item.get("source_type", "TECHNICAL_DOCUMENT"))
                    evidence_class: Literal["B", "C"] = "C" if source_type == "VERIFIED_CASE" else "B"
                    claim = str(item.get("content", ""))[:1_800]
                    if evidence_class == "C":
                        claim = f"历史案例摘要（仅C级经验，不能证明本次根因）：{claim}"
                    evidence.append(EvidenceContract(
                        evidence_id=f"EV-{evidence_class}-{index:03d}",
                        evidence_class=evidence_class,
                        evidence_type=source_type,
                        reference=str(item.get("archive_uri") or item.get("evidence_id") or "knowledge:unknown"),
                        claim=claim or "检索命中适用知识片段",
                        supports=[],
                        applicability="CONTEXTUAL" if evidence_class == "C" else "APPLICABLE",
                        retrieved_at=InvestigationSynthesizer._snapshot_created_at(snapshot),
                    ))
        samples = next((item for item in observations if item.tool_name == "get_representative_samples" and item.success), None)
        if samples is not None:
            items = samples.payload.get("items", [])
            count = len(items) if isinstance(items, list) else 0
            evidence.append(EvidenceContract(
                evidence_id="EV-A-003",
                evidence_class="A",
                evidence_type="REPRESENTATIVE_SAMPLES",
                reference=f"{snapshot_id}#/representative-samples",
                claim=f"从当前Snapshot提取{count}个代表性样本供人工复核",
                supports=[],
                applicability="DIRECT",
            ))
        return evidence

    @staticmethod
    def _proposal(
        run_id: str,
        case_id: str,
        snapshot: dict[str, object],
        proposal_source: RunbookProposalContract | RunbookProposal,
        evidence_ids: list[str],
    ) -> ProposalContract:
        assert proposal_source is not None
        created_at = InvestigationSynthesizer._snapshot_created_at(snapshot)
        from quality_case_agent.contracts.investigation import ProposalStepContract

        return ProposalContract(
            proposal_id=f"prop-{run_id}",
            case_id=case_id,
            analysis_run_id=run_id,
            created_at=created_at,
            title=proposal_source.title,
            reason=proposal_source.reason,
            steps=[ProposalStepContract(order=step.order, instruction=step.instruction, expected_evidence=step.expected_evidence) for step in proposal_source.steps],
            requested_role=proposal_source.requested_role,
            priority=cast(Literal["LOW", "MEDIUM", "HIGH"], proposal_source.priority),
            risk_level=cast(Literal["LOW", "MEDIUM", "HIGH"], proposal_source.risk_level),
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def _validated_draft(draft: dict[str, object] | None) -> InvestigationDraftContract | None:
        if draft is None:
            return None
        try:
            return InvestigationDraftContract.model_validate(draft)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _snapshot_created_at(snapshot: dict[str, object]) -> datetime:
        value = snapshot.get("created_at")
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        return datetime(1970, 1, 1, tzinfo=UTC)
