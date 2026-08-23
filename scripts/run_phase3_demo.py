"""Run the offline Phase 3 Case investigation demo."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.adapters.llm.deterministic import DeterministicInvestigationLLM
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.investigation.agent import InvestigationAgent
from quality_case_agent.application.investigation.tools import ReadOnlyInvestigationTools
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.contracts.knowledge import KnowledgeDocumentContract

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def main() -> int:
    inspection_store = InMemoryInspectionStore()
    metrics_store = InMemoryMetricsStore()
    case_store = InMemoryQualityCaseStore()
    ingestion = InspectionIngestionService(inspection_store)
    batches = tuple(scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10))
    for batch in batches:
        ingestion.submit_batch(batch)
    MetricsWorker(inspection_store, metrics_store).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics_store, case_store).run()
    case = detection.opened_cases[0]

    knowledge_base = InMemoryKnowledgeBase()
    effective_from = datetime(2026, 8, 1, tzinfo=UTC)
    knowledge_base.ingest(
        _document(
            "doc-fixture-manual-v3",
            "夹具维护手册",
            "3.2",
            "TECHNICAL_DOCUMENT",
            "# 4.1 定位销检查\n\n夹具定位偏移时，NG区域可能出现方向性聚集。检查定位销间隙，使用基准件复测位置，并核对换线记录。",
            effective_from,
        )
    )
    knowledge_base.ingest(
        _document(
            "case-fixture-verified-001",
            "已验证案例：定位销松动",
            "1.0",
            "VERIFIED_CASE",
            "# 验证结果\n\n历史案例中定位销松动导致工件向右上区域偏移；更换定位销并复测后NG率恢复。该案例仅作为C级经验。",
            effective_from,
        )
    )

    tools = ReadOnlyInvestigationTools(case_store, metrics_store, knowledge_base)
    result = InvestigationAgent(DeterministicInvestigationLLM(), tools).analyze(
        case.case_id, case.snapshot.snapshot_id
    )
    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "snapshot_id": case.snapshot.snapshot_id,
                "analysis": result.analysis.model_dump(mode="json"),
                "proposal": result.proposal.model_dump(mode="json") if result.proposal else None,
                "trace": result.trace.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _document(
    document_id: str,
    title: str,
    version: str,
    source_type: str,
    content: str,
    effective_from: datetime,
) -> KnowledgeDocumentContract:
    return KnowledgeDocumentContract(
        document_id=document_id,
        title=title,
        version=version,
        source_type=source_type,
        content=content,
        effective_from=effective_from,
        applicability={"station_id": "camera-01", "product_id": "part-A"},
    )


if __name__ == "__main__":
    raise SystemExit(main())
