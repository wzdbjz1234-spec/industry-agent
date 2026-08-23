"""Phase 11 safety branches: illumination drift and insufficient evidence."""

from datetime import UTC, datetime

from quality_case_agent.adapters.embeddings.deterministic import DeterministicEmbeddingProvider
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
from quality_case_agent.domain.knowledge.models import KnowledgeDocument
from quality_case_agent.domain.quality_case.detector import (
    IlluminationDriftCaseDetector,
    InsufficientEvidenceCaseDetector,
)

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName, generate_scenario_batches


def _pipeline(scenario: ScenarioName, detector: object):
    inspection = InMemoryInspectionStore()
    metrics = InMemoryMetricsStore()
    cases = InMemoryQualityCaseStore()
    for batch in scenario_replay(scenario, seed=7, batch_size=10, replay_id="phase11"):
        InspectionIngestionService(inspection).submit_batch(batch)
    MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics, cases, detector=detector).run()
    return metrics, cases, detection


def _agent(cases: InMemoryQualityCaseStore, metrics: InMemoryMetricsStore) -> InvestigationAgent:
    knowledge = InMemoryKnowledgeBase(DeterministicEmbeddingProvider())
    knowledge.ingest(
        KnowledgeDocument(
            document_id="illumination-manual-v2",
            title="Illumination maintenance",
            version="2.0",
            source_type="TECHNICAL_DOCUMENT",
            content=(
                "Inspect light brightness, light source angle, camera exposure time, gain "
                "and use a reference part to recalibrate the camera."
            ),
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
            effective_to=None,
            applicability={"station_id": "camera-01", "product_id": "part-A"},
        )
    )
    return InvestigationAgent(
        DeterministicInvestigationLLM(),
        ReadOnlyInvestigationTools(cases, metrics, knowledge),
    )


def test_phase11_fixed_seed_scenarios_are_reproducible() -> None:
    first = generate_scenario_batches(ScenarioName.ILLUMINATION_DRIFT, seed=19)
    second = generate_scenario_batches(ScenarioName.ILLUMINATION_DRIFT, seed=19)
    assert [item.model_dump(mode="json") for item in first] == [
        item.model_dump(mode="json") for item in second
    ]
    insufficient = generate_scenario_batches(ScenarioName.INSUFFICIENT_EVIDENCE, seed=19)
    versions = {
        result.detector.model_version
        for batch in insufficient
        for result in batch.records
    }
    assert versions == {"sim-detector-1.0", "sim-detector-legacy-0.9"}


def test_illumination_drift_uses_illumination_hypothesis_and_manual() -> None:
    metrics, cases, detection = _pipeline(
        ScenarioName.ILLUMINATION_DRIFT, IlluminationDriftCaseDetector()
    )
    assert len(detection.opened_cases) == 1
    case = detection.opened_cases[0]
    output = _agent(cases, metrics).analyze(case.case_id, case.snapshot.snapshot_id)
    assert output.analysis.status == "COMPLETED"
    assert output.analysis.hypotheses[0].hypothesis_id == "H-ILL-01"
    assert "光照" in output.analysis.hypotheses[0].title
    assert output.proposal is not None
    assert "光源" in output.proposal.title


def test_insufficient_evidence_stops_without_root_cause_or_proposal() -> None:
    metrics, cases, detection = _pipeline(
        ScenarioName.INSUFFICIENT_EVIDENCE, InsufficientEvidenceCaseDetector()
    )
    assert len(detection.opened_cases) == 1
    case = detection.opened_cases[0]
    output = _agent(cases, metrics).analyze(case.case_id, case.snapshot.snapshot_id)
    assert output.analysis.status == "INSUFFICIENT_EVIDENCE"
    assert output.proposal is None
    assert output.analysis.hypotheses == []
    assert "统一模型版本后的至少500条检测记录" in output.analysis.required_information
    assert "DATA_QUALITY_BLOCKED" in output.analysis.termination_reason
    assert any(
        event.action == "check_data_quality" for event in output.trace.events
    )
