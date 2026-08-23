"""Run the offline Phase 5–7 knowledge, investigation and approval demo."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from quality_case_agent.adapters.in_memory.approval import InMemoryProposalStore
from quality_case_agent.adapters.in_memory.investigation import (
    InMemoryAnalysisRunStore,
    InMemoryInvestigationEventPublisher,
)
from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.adapters.knowledge.parsing import MarkdownDocumentParser
from quality_case_agent.adapters.llm.deterministic import DeterministicInvestigationLLM
from quality_case_agent.application.approval.service import ProposalApprovalService
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.investigation.agent import InvestigationAgent
from quality_case_agent.application.investigation.service import InvestigationService
from quality_case_agent.application.investigation.tools import ReadOnlyInvestigationTools
from quality_case_agent.application.knowledge.service import KnowledgeService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.contracts.approval import ProposalDecisionContract
from quality_case_agent.contracts.knowledge import KnowledgeDocumentUploadContract

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def main() -> int:
    inspection = InMemoryInspectionStore()
    metrics = InMemoryMetricsStore()
    cases = InMemoryQualityCaseStore()
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        InspectionIngestionService(inspection).submit_batch(batch)
    MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics, cases).run()
    case = detection.opened_cases[0]

    knowledge_base = InMemoryKnowledgeBase()
    knowledge = KnowledgeService(knowledge_base)
    for document_id, title, source_type, file_name, content in (
        (
            "fixture-manual-v4",
            "Fixture positioning manual",
            "TECHNICAL_DOCUMENT",
            "fixture-positioning-v4.md",
            "# Pin inspection\n\nMeasure fixture positioning pin gap and verify with a reference part.",
        ),
        (
            "fixture-case-verified-001",
            "Verified fixture case",
            "VERIFIED_CASE",
            "fixture-case.md",
            "# Verified result\n\nA loose positioning pin caused upper-right offset and recovered after replacement.",
        ),
    ):
        metadata = KnowledgeDocumentUploadContract(
            document_id=document_id,
            title=title,
            version="4.0" if source_type == "TECHNICAL_DOCUMENT" else "1.0",
            source_type=source_type,
            file_name=file_name,
            content_type="text/markdown",
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
            applicability={"station_id": "camera-01", "product_id": "part-A"},
        )
        knowledge.ingest_upload(metadata, content.encode("utf-8"), parser=MarkdownDocumentParser())

    runs = InMemoryAnalysisRunStore()
    analysis_events = InMemoryInvestigationEventPublisher()
    tools = ReadOnlyInvestigationTools(cases, metrics, knowledge_base, inspection)
    investigation = InvestigationService(
        InvestigationAgent(DeterministicInvestigationLLM(), tools),
        runs,
        analysis_events,
        cases,
    )
    proposals = InMemoryProposalStore()
    approval = ProposalApprovalService(proposals, cases, investigation)
    investigation.set_proposal_registrar(approval.register_output)
    opened_event = next(event for event in cases.events if event.event_type == "quality.case.opened.v1")
    output = investigation.handle_case_opened(opened_event)
    replay = investigation.handle_case_opened(opened_event)
    assert output.proposal is not None

    decision = ProposalDecisionContract(
        decision_id="phase5-7-demo-decision-001",
        proposal_id=output.proposal.proposal_id,
        case_id=case.case_id,
        decision="APPROVE_WITH_CHANGES",
        decided_by="quality-engineer-demo",
        decided_at=datetime(2026, 8, 23, 10, 45, tzinfo=UTC),
        comment="先检查光照，再测量定位销间隙",
        approved_steps=["检查光源角度和亮度", "测量定位销间隙", "使用基准件复测工件位置"],
    )
    approved = approval.decide(decision)
    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "analysis_run_id": output.analysis.analysis_run_id,
                "analysis_replay_is_same": output.model_dump(mode="json") == replay.model_dump(mode="json"),
                "trace_event_count": len(output.trace.events),
                "evidence_classes": sorted({item.evidence_class for item in output.analysis.evidence}),
                "pending_proposals_after_approval": len(proposals.list_pending()),
                "approved_proposal_id": approved.approved_proposal_id,
                "original_proposal_preserved": proposals.get_proposal(output.proposal.proposal_id)
                is not None,
                "analysis_event_count": len(analysis_events.list_events()),
                "case_status": cases.list_cases()[0].case_status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
