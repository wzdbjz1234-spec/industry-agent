"""FastAPI application for the Phase 5–7 offline vertical slice."""

from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from quality_case_agent.adapters.embeddings.deterministic import DeterministicEmbeddingProvider
from quality_case_agent.adapters.identity.oidc import OidcIdentityAdapter
from quality_case_agent.adapters.in_memory.approval import InMemoryProposalStore
from quality_case_agent.adapters.in_memory.archive import (
    InMemoryCaseArchiveStore,
    InMemoryVerifiedCaseIndex,
)
from quality_case_agent.adapters.in_memory.audit import InMemoryAuditLog
from quality_case_agent.adapters.in_memory.investigation import (
    InMemoryAnalysisRunStore,
    InMemoryInvestigationEventPublisher,
)
from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.adapters.in_memory.monitoring import InMemoryMonitoringBaselineStore
from quality_case_agent.adapters.in_memory.qms import InMemoryQmsDeliveryStore
from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.adapters.knowledge.parsing import MarkdownDocumentParser, PdfDocumentParser
from quality_case_agent.adapters.llm.deepseek import DeepSeekInvestigationLLM
from quality_case_agent.adapters.llm.deterministic import DeterministicInvestigationLLM
from quality_case_agent.adapters.observability.otel import OtelTelemetry
from quality_case_agent.adapters.observability.prometheus import PrometheusMetrics
from quality_case_agent.adapters.postgres.audit import SqlAlchemyAuditLog
from quality_case_agent.adapters.qms.http import HttpQmsClient
from quality_case_agent.adapters.qms.mock import MockQmsAdapter
from quality_case_agent.adapters.vision.efficientad import EfficientADImagePipelineAdapter
from quality_case_agent.application.approval.service import ProposalApprovalService
from quality_case_agent.application.archival.service import CaseArchiveService, CaseClosureService
from quality_case_agent.application.audit.service import AuditService
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.evaluation.roi import calculate_roi
from quality_case_agent.application.evaluation.runner import EvaluationRunner
from quality_case_agent.application.identity.policy import (
    AuthorizationDenied,
    HeaderIdentityProvider,
    IdentityPolicy,
)
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.investigation.agent import AgentLimits, InvestigationAgent
from quality_case_agent.application.investigation.service import InvestigationService
from quality_case_agent.application.investigation.tools import ReadOnlyInvestigationTools
from quality_case_agent.application.knowledge.service import KnowledgeService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.application.monitoring.service import MonitoringReport, MonitoringService
from quality_case_agent.application.observability.service import (
    AnalysisMetricsRegistry,
    CaseEventTimelineProjection,
    WorkerMetricsRegistry,
)
from quality_case_agent.application.ports.audit import AuditLog
from quality_case_agent.application.ports.identity import (
    IdentityAuthenticationError,
    IdentityProvider,
)
from quality_case_agent.application.ports.inspection import InspectionResultStore
from quality_case_agent.application.ports.investigation import AnalysisRunStore
from quality_case_agent.application.ports.metrics import QualityMetricsStore
from quality_case_agent.application.ports.monitoring import MonitoringBaselineStore
from quality_case_agent.application.ports.qms import QmsClient, QmsDeliveryRecord
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.application.qms.modes import ShadowQmsAdapter
from quality_case_agent.application.qms.service import QmsIntegrationService, QmsWebhookService
from quality_case_agent.application.qms.worker import QmsIntegrationWorker
from quality_case_agent.application.vision import (
    InMemoryVisionEventStore,
    VisionFrame,
    VisionProcessingError,
    VisionProcessingResult,
    VisionProcessingService,
    VisionSchemeRegistry,
    VisionStreamWorker,
)
from quality_case_agent.application.vision.stream import VisionQueueFullError
from quality_case_agent.bootstrap import build_persistent_resources
from quality_case_agent.config import RuntimeSettings
from quality_case_agent.contracts.approval import ProposalDecisionContract
from quality_case_agent.contracts.evaluation import (
    EvaluationConfigContract,
    EvaluationReportContract,
    ROICalculationRequestContract,
)
from quality_case_agent.contracts.identity import IdentityContract
from quality_case_agent.contracts.investigation import InvestigationOutputContract
from quality_case_agent.contracts.knowledge import (
    KnowledgeDocumentContract,
    KnowledgeDocumentUploadContract,
    KnowledgeTextUploadContract,
)
from quality_case_agent.contracts.monitoring import (
    MonitoringDecisionContract,
    MonitoringReportContract,
)
from quality_case_agent.contracts.qms import QmsTaskResultContract
from quality_case_agent.contracts.vision import (
    AnomlibDetectionRequestContract,
    PublicDatasetReplayRequestContract,
    VisionFrameRequestContract,
    VisionJobContract,
    VisionStatusContract,
)
from quality_case_agent.domain.knowledge.models import KnowledgeDocument
from quality_case_agent.domain.quality_case.detector import (
    CaseDetector,
    IlluminationDriftCaseDetector,
    InsufficientEvidenceCaseDetector,
)
from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


@dataclass(slots=True)
class ApplicationContainer:
    knowledge: KnowledgeService
    proposals: InMemoryProposalStore
    approval: ProposalApprovalService
    investigations: InvestigationService
    runs: AnalysisRunStore
    cases: QualityCaseStore
    events: InMemoryInvestigationEventPublisher
    inspection: InspectionResultStore
    metrics: QualityMetricsStore
    monitoring: MonitoringService
    knowledge_base: InMemoryKnowledgeBase
    qms: QmsClient
    qms_delivery: InMemoryQmsDeliveryStore
    qms_worker: QmsIntegrationWorker
    archive_store: InMemoryCaseArchiveStore
    verified_case_index: InMemoryVerifiedCaseIndex
    closure: CaseClosureService
    timeline: CaseEventTimelineProjection
    worker_metrics: WorkerMetricsRegistry
    analysis_metrics: AnalysisMetricsRegistry
    prometheus_metrics: PrometheusMetrics
    telemetry: OtelTelemetry
    evaluation_reports: list[EvaluationReportContract]
    vision_events: InMemoryVisionEventStore
    vision_registry: VisionSchemeRegistry
    vision_service: VisionProcessingService
    vision_worker: VisionStreamWorker
    llm_provider: str
    llm_model: str
    identity_provider: IdentityProvider
    identity_policy: IdentityPolicy
    audit: AuditService
    audit_log: AuditLog


def _investigation_llm() -> DeterministicInvestigationLLM | DeepSeekInvestigationLLM:
    """Select the explicit runtime provider; offline remains the safe default."""

    provider = os.getenv("QUALITY_LLM_PROVIDER", "deterministic").strip().lower()
    if provider in {"", "deterministic", "offline"}:
        return DeterministicInvestigationLLM()
    if provider == "deepseek":
        return DeepSeekInvestigationLLM.from_env()
    raise ValueError("QUALITY_LLM_PROVIDER must be deterministic or deepseek")


def build_demo_container(*, agent_limits: AgentLimits | None = None) -> ApplicationContainer:
    """Compose adapters; production mode selects durable core stores explicitly."""

    settings = RuntimeSettings.from_env()
    inspection: InspectionResultStore
    metrics: QualityMetricsStore
    cases: QualityCaseStore
    runs: AnalysisRunStore
    monitoring_baselines: MonitoringBaselineStore
    if settings.mode == "production":
        resources = build_persistent_resources(settings)
        inspection = resources.inspection
        metrics = resources.metrics
        cases = resources.cases
        runs = resources.runs
        monitoring_baselines = resources.monitoring_baselines
    else:
        inspection = InMemoryInspectionStore()
        metrics = InMemoryMetricsStore()
        cases = InMemoryQualityCaseStore()
        runs = InMemoryAnalysisRunStore()
        monitoring_baselines = InMemoryMonitoringBaselineStore()
    knowledge_base = InMemoryKnowledgeBase(DeterministicEmbeddingProvider())
    knowledge = KnowledgeService(knowledge_base)
    _seed_demo_knowledge(knowledge_base)
    event_publisher = InMemoryInvestigationEventPublisher()
    llm = _investigation_llm()
    prometheus_metrics = PrometheusMetrics()
    telemetry = OtelTelemetry()
    worker_metrics = WorkerMetricsRegistry(prometheus_metrics)
    analysis_metrics = AnalysisMetricsRegistry(
        prometheus_metrics,
        provider=str(getattr(llm, "provider", "unknown")),
        model=str(getattr(llm, "model", "unknown")),
    )
    monitoring = MonitoringService(
        inspection,
        monitoring_baselines,
        exporter=prometheus_metrics,
    )
    tools = ReadOnlyInvestigationTools(cases, metrics, knowledge_base, inspection)
    investigation = InvestigationService(
        InvestigationAgent(llm, tools, limits=agent_limits),
        runs,
        event_publisher,
        cases,
        metrics=worker_metrics,
        analysis_metrics=analysis_metrics,
    )
    proposals = InMemoryProposalStore()
    audit_log: AuditLog = (
        SqlAlchemyAuditLog(resources.database)
        if settings.mode == "production"
        else InMemoryAuditLog()
    )
    audit = AuditService(audit_log)
    oidc_url = os.getenv("QUALITY_OIDC_USERINFO_URL")
    identity_provider: IdentityProvider = (
        OidcIdentityAdapter(oidc_url)
        if oidc_url
        else HeaderIdentityProvider(required=settings.mode == "production")
    )
    identity_policy = IdentityPolicy()
    approval = ProposalApprovalService(proposals, cases, investigation, audit=audit)
    investigation.set_proposal_registrar(approval.register_output)
    if settings.qms_mode == "SHADOW":
        qms: QmsClient = ShadowQmsAdapter()
    elif settings.mode == "production":
        if not settings.qms_base_url:
            raise ValueError("QUALITY_QMS_BASE_URL is required for non-shadow production QMS")
        qms = HttpQmsClient(settings.qms_base_url, mode=settings.qms_mode)
    else:
        qms = MockQmsAdapter()
    qms_delivery = InMemoryQmsDeliveryStore()
    qms_worker = QmsIntegrationWorker(
        QmsIntegrationService(proposals, cases, qms, mode=settings.qms_mode),
        qms_delivery,
        metrics=worker_metrics,
    )
    archive_store = InMemoryCaseArchiveStore()
    verified_case_index = InMemoryVerifiedCaseIndex()
    webhook = QmsWebhookService(cases, b"phase9-demo-secret")
    closure = CaseClosureService(
        webhook,
        CaseArchiveService(archive_store, verified_case_index, knowledge_base),
        proposals,
        runs,
        cases,
        qms,
    )

    def refresh_vision_case_pipeline(_batch: object) -> None:
        with telemetry.operation("quality.case.pipeline", attributes={"source": "vision"}) as operation:
            MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))
            detection = QualityCaseDetectionService(metrics, cases).run()
            for event in detection.events:
                if event.event_type == "quality.case.opened.v1":
                    investigation.handle_case_opened(event)
            operation.succeed(case_count=len(detection.opened_cases))

    vision_events = InMemoryVisionEventStore()
    vision_registry = VisionSchemeRegistry()
    _register_configured_efficientad(vision_registry)
    vision_service = VisionProcessingService(
        vision_registry,
        InspectionIngestionService(inspection),
        vision_events,
        post_ingest=refresh_vision_case_pipeline,
    )
    vision_worker = VisionStreamWorker(vision_service)
    return ApplicationContainer(
        knowledge=knowledge,
        proposals=proposals,
        approval=approval,
        investigations=investigation,
        runs=runs,
        cases=cases,
        events=event_publisher,
        inspection=inspection,
        metrics=metrics,
        monitoring=monitoring,
        knowledge_base=knowledge_base,
        qms=qms,
        qms_delivery=qms_delivery,
        qms_worker=qms_worker,
        archive_store=archive_store,
        verified_case_index=verified_case_index,
        closure=closure,
        timeline=CaseEventTimelineProjection(),
        worker_metrics=worker_metrics,
        analysis_metrics=analysis_metrics,
        prometheus_metrics=prometheus_metrics,
        telemetry=telemetry,
        evaluation_reports=[],
        vision_events=vision_events,
        vision_registry=vision_registry,
        vision_service=vision_service,
        vision_worker=vision_worker,
        llm_provider=str(getattr(llm, "provider", "unknown")),
        llm_model=str(getattr(llm, "model", "unknown")),
        identity_provider=identity_provider,
        identity_policy=identity_policy,
        audit=audit,
        audit_log=audit_log,
    )


def _register_configured_efficientad(registry: VisionSchemeRegistry) -> None:
    """Enable the real EfficientAD adapter only when its model directory is configured."""

    model_dir = os.getenv("QUALITY_VISION_EFFICIENTAD_MODEL_DIR")
    if not model_dir:
        return
    raw_roi = os.getenv("QUALITY_VISION_EFFICIENTAD_ROI", "1418,564,173,196")
    roi_values = tuple(int(value.strip()) for value in raw_roi.split(","))
    if len(roi_values) != 4:
        raise ValueError("QUALITY_VISION_EFFICIENTAD_ROI must be x,y,width,height")
    threshold = float(os.getenv("QUALITY_VISION_EFFICIENTAD_THRESHOLD", "0.2"))
    device = os.getenv("QUALITY_VISION_EFFICIENTAD_DEVICE", "cpu")
    adapter = EfficientADImagePipelineAdapter.from_directory(
        Path(model_dir),
        roi=roi_values,
        threshold=threshold,
        device=device,
        model_version=os.getenv("QUALITY_VISION_EFFICIENTAD_MODEL_VERSION"),
    )
    registry.register("efficientad", adapter)


def _seed_demo_knowledge(knowledge_base: InMemoryKnowledgeBase) -> None:
    for document_id, source_type, content in (
        (
            "fixture-manual-v4",
            "TECHNICAL_DOCUMENT",
            "# Pin inspection\n\nMeasure fixture positioning pin gap and verify with a reference part.",
        ),
        (
            "illumination-manual-v2",
            "TECHNICAL_DOCUMENT",
            (
                "# Illumination maintenance\n\n"
                "When anomaly scores rise across multiple image regions, inspect light brightness, "
                "light source angle, camera exposure time, gain and auto-exposure status. Use a "
                "reference part to recalibrate the camera and compare scores before and after the "
                "adjustment."
            ),
        ),
    ):
        knowledge_base.ingest(
            KnowledgeDocument(
                document_id=document_id,
                title=document_id,
                version="4.0" if document_id == "fixture-manual-v4" else "2.0",
                source_type=source_type,
                content=content,
                effective_from=datetime(2026, 8, 1, tzinfo=UTC),
                effective_to=None,
                applicability={"station_id": "camera-01", "product_id": "part-A"},
            )
        )


def create_app(container: ApplicationContainer | None = None) -> FastAPI:
    container = container or build_demo_container()
    app = FastAPI(title="Quality Case Investigation Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def sync_timeline() -> None:
        for case_event in container.cases.events:
            container.timeline.record(case_event, source="case-store")
        for investigation_event in container.events.list_events():
            container.timeline.record(investigation_event, source="investigation-worker")
        for proposed_event in container.proposals.list_proposed_events():
            container.timeline.record(proposed_event, source="proposal-store")
        for approval_event in container.proposals.list_events():
            container.timeline.record(approval_event, source="approval-store")
        for record in (
            *container.qms_worker.pending(),
            *container.qms_worker.processed(),
            *container.qms_worker.dlq(),
        ):
            container.timeline.record_delivery(record)
            if record.result is not None:
                container.timeline.record(record.result, source="qms-integration-worker")

    def authenticated(request: Request, action: str) -> IdentityContract:
        try:
            identity = container.identity_provider.authenticate(request.headers)
            container.identity_policy.authorize(identity, action)
            return identity
        except IdentityAuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.get("/api/v1/identity/me")
    def identity_me(request: Request) -> dict[str, object]:
        identity = authenticated(request, "proposal.read")
        return identity.model_dump(mode="json")

    @app.get("/api/v1/qms/status")
    def qms_status(request: Request) -> dict[str, object]:
        authenticated(request, "qms.shadow")
        return {"mode": container.qms_worker.mode, "external_write_enabled": container.qms_worker.mode != "SHADOW"}

    @app.get("/api/v1/audit/events")
    def audit_events(request: Request, limit: int = Query(default=200, ge=1, le=1_000)) -> list[dict[str, object]]:
        authenticated(request, "audit.read")
        return [event.model_dump(mode="json") for event in container.audit_log.list_events(limit=limit)]

    @app.get("/api/v1/audit/export")
    def audit_export(request: Request) -> Response:
        authenticated(request, "audit.export")
        return Response(content=container.audit_log.export_jsonl(), media_type="application/x-ndjson")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "quality-case-agent-api",
            "mode": (
                "offline-deterministic"
                if container.llm_provider == "deterministic"
                else "configured-provider"
            ),
            "llm": {"provider": container.llm_provider, "model": container.llm_model},
            "qms": {"mode": container.qms_worker.mode, "external_write_enabled": container.qms_worker.mode != "SHADOW"},
            "trace_id": "health-local",
            "vision_schemes": list(container.vision_registry.names()),
        }

    @app.get("/api/v1/vision/schemes")
    def vision_schemes() -> dict[str, object]:
        return {
            "registered": list(container.vision_registry.names()),
            "default_input": "efficientad",
            "anomlib_input": "/api/v1/vision/anomlib/detections",
        }

    @app.get("/api/v1/vision/status", response_model=VisionStatusContract)
    def vision_status() -> VisionStatusContract:
        return container.vision_worker.status()

    @app.post("/api/v1/vision/frames", response_model=VisionJobContract)
    def submit_vision_frame(request: VisionFrameRequestContract) -> VisionJobContract:
        try:
            frame = _vision_frame_from_request(request)
            return container.vision_worker.submit(frame)
        except KeyError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except VisionQueueFullError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc

    @app.get("/api/v1/vision/jobs/{job_id}", response_model=VisionJobContract)
    def vision_job(job_id: str) -> VisionJobContract:
        result = container.vision_worker.get(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"vision job not found: {job_id}")
        return result

    @app.get("/api/v1/vision/events")
    def vision_events(event_type: str | None = Query(default=None)) -> list[object]:
        return list(container.vision_events.list_events(event_type=event_type))

    @app.post("/api/v1/vision/anomlib/detections")
    def ingest_anomlib_detection(request: AnomlibDetectionRequestContract) -> dict[str, object]:
        try:
            result = container.vision_service.process_anomlib_detection(request)
        except VisionProcessingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _vision_result_payload(result)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                    "details": {},
                    "trace_id": "api-local",
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "request validation failed",
                    "details": exc.errors(),
                    "trace_id": "api-local",
                }
            },
        )

    @app.post("/api/v1/knowledge/documents")
    def ingest_document(document: KnowledgeDocumentContract) -> object:
        try:
            return container.knowledge.ingest(document)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/knowledge/documents/upload")
    def upload_document(request: KnowledgeTextUploadContract) -> object:
        try:
            parser = (
                PdfDocumentParser()
                if request.content_type == "application/pdf"
                else MarkdownDocumentParser()
            )
            metadata = KnowledgeDocumentUploadContract.model_validate(
                request.model_dump(exclude={"content"})
            )
            return container.knowledge.ingest_upload(
                metadata, request.content.encode("utf-8"), parser=parser
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/knowledge/search")
    def search_knowledge(
        query: str = Query(min_length=1),
        station_id: str | None = None,
        product_id: str | None = None,
        trigger_family: str | None = None,
        date_prefix: str | None = None,
        source_type: str | None = None,
        top_k: int = Query(default=5, ge=1, le=20),
    ) -> list[object]:
        filters = {
            key: value
            for key, value in {
                "station_id": station_id,
                "product_id": product_id,
                "trigger_family": trigger_family,
                "date_prefix": date_prefix,
            }.items()
            if value is not None
        }
        source_types = (source_type,) if source_type is not None else ()
        return list(
            container.knowledge.search(
                query,
                source_types=source_types,
                filters=filters,
                top_k=top_k,
            )
        )

    @app.get("/api/v1/proposals/pending")
    def pending_proposals(request: Request) -> list[object]:
        authenticated(request, "proposal.read")
        return list(container.proposals.list_pending())

    @app.post("/api/v1/proposals/{proposal_id}/decisions")
    def decide_proposal(request: Request, proposal_id: str, decision: ProposalDecisionContract) -> object:
        identity = authenticated(request, "proposal.decide")
        if decision.proposal_id != proposal_id:
            raise HTTPException(status_code=422, detail="proposal_id does not match path")
        try:
            approval_event = container.approval.decide(decision)
            qms_event = container.qms_worker.handle(approval_event)
            container.audit.record(
                identity,
                event_type="quality.proposal.decision.audit.v1",
                action=decision.decision,
                resource_type="proposal",
                resource_id=proposal_id,
                correlation_id=decision.decision_id,
                causation_id=approval_event.event_id,
                metadata={"comment": decision.comment, "approved_proposal_id": approval_event.approved_proposal_id},
            )
            return {"approval_event": approval_event, "qms_task_event": qms_event}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/analysis/runs")
    def analysis_runs() -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for run in container.runs.list_runs():
            item = asdict(run)
            output = container.runs.get_output(run.analysis_run_id)
            if output is not None:
                item.update(
                    {
                        "summary": output.analysis.summary,
                        "termination_reason": output.analysis.termination_reason,
                        "required_information": output.analysis.required_information,
                        "evidence_classes": sorted(
                            {evidence.evidence_class for evidence in output.analysis.evidence}
                        ),
                    }
                )
            items.append(item)
        return items

    @app.get("/api/v1/analysis/runs/{analysis_run_id}")
    def analysis_output(analysis_run_id: str) -> InvestigationOutputContract:
        output = container.runs.get_output(analysis_run_id)
        if output is None:
            raise HTTPException(status_code=404, detail="analysis run not found")
        return output

    @app.get("/api/v1/analysis/events")
    def analysis_events() -> list[object]:
        """Return the same structured events that an SSE adapter can stream later."""

        return list(container.events.list_events())

    @app.get("/api/v1/evaluation/dataset")
    def evaluation_dataset() -> dict[str, object]:
        runner = EvaluationRunner()
        return {
            "dataset_version": runner.dataset.version,
            "scenarios": [
                {
                    "scenario_id": item.scenario_id,
                    "scenario": item.scenario,
                    "expected_status": item.expected_status,
                    "required_tools": item.required_tools,
                }
                for item in runner.dataset.scenarios
            ],
        }

    @app.post("/api/v1/evaluation/run")
    def run_evaluation(config: EvaluationConfigContract) -> EvaluationReportContract:
        report = EvaluationRunner().run(config)
        container.evaluation_reports.append(report)
        return report

    @app.post("/api/v1/evaluation/matrix")
    def run_evaluation_matrix(
        configs: list[EvaluationConfigContract],
    ) -> list[EvaluationReportContract]:
        reports = EvaluationRunner().run_matrix(tuple(configs))
        container.evaluation_reports.extend(reports)
        return list(reports)

    @app.get("/api/v1/evaluation/reports")
    def evaluation_reports() -> list[EvaluationReportContract]:
        return list(container.evaluation_reports)

    @app.post("/api/v1/roi/calculate")
    def calculate_roi_endpoint(request: ROICalculationRequestContract) -> object:
        return calculate_roi(request)

    @app.get("/api/v1/cases")
    def cases() -> list[object]:
        return list(container.cases.list_cases())

    @app.get("/api/v1/cases/{case_id}")
    def case_detail(case_id: str) -> object:
        case = container.cases.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
        return case

    @app.get("/api/v1/cases/{case_id}/archive")
    def case_archive(case_id: str) -> object:
        case = container.cases.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
        if case.archive_uri is None:
            raise HTTPException(status_code=404, detail="case has not been archived")
        try:
            return json.loads(container.archive_store.get(case.archive_uri).decode("utf-8"))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="archive object not found") from exc

    @app.get("/api/v1/case-library")
    def case_library() -> list[dict[str, object]]:
        return [
            {
                "document_id": record.document_id,
                "text": record.text,
                "metadata": dict(record.metadata),
                "content_sha256": record.content_sha256,
                "archive_uri": record.metadata.get("archive_uri"),
            }
            for record in container.verified_case_index.list_records()
        ]

    @app.get("/api/v1/case-library/{case_id}")
    def case_library_archive(case_id: str) -> object:
        """Resolve a historical-case summary to its complete immutable archive."""

        case = container.cases.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
        if case.archive_uri is None:
            raise HTTPException(status_code=404, detail="case has not been archived")
        try:
            return json.loads(container.archive_store.get(case.archive_uri).decode("utf-8"))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="archive object not found") from exc

    @app.get("/api/v1/case-library/{case_id}/archive")
    def case_library_archive_alias(case_id: str) -> object:
        return case_library_archive(case_id)

    @app.post("/api/v1/integrations/qms/task-results")
    def qms_task_result(
        result: QmsTaskResultContract,
        x_qms_signature: str = Header(alias="X-QMS-Signature"),
        x_qms_timestamp: str | None = Header(default=None, alias="X-QMS-Timestamp"),
        x_qms_nonce: str | None = Header(default=None, alias="X-QMS-Nonce"),
    ) -> dict[str, object]:
        try:
            outcome = container.closure.process(
                result,
                x_qms_signature,
                timestamp=x_qms_timestamp,
                nonce=x_qms_nonce,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        container.timeline.record(outcome.confirmation, source="qms-webhook")
        container.timeline.record(outcome.archived, source="case-archive")
        webhook_identity = HeaderIdentityProvider(
            default_actor_id="system:qms-webhook",
            default_role="OPERATOR",
            default_organization="qms",
        ).authenticate({})
        container.audit.record(
            webhook_identity,
            event_type="qms.task.result.audit.v1",
            action="WEBHOOK_ACCEPTED",
            resource_type="qms_task",
            resource_id=result.task_id,
            correlation_id=result.event_id,
            metadata={"confirmation_id": result.confirmation_id, "signature": x_qms_signature},
        )
        return {
            "confirmation_event": outcome.confirmation,
            "archive_event": outcome.archived,
        }

    @app.get("/api/v1/qms/tasks")
    def qms_tasks(request: Request) -> dict[str, list[object]]:
        authenticated(request, "qms.shadow")
        return {"items": list(container.qms.list_tasks())}

    @app.get("/api/v1/qms/delivery")
    def qms_delivery() -> dict[str, list[dict[str, object]]]:
        def serialize(delivery: QmsDeliveryRecord) -> dict[str, object]:
            task = delivery.result.task if delivery.result is not None else None
            return {
                "event_id": delivery.event.event_id,
                "event_type": delivery.event.event_type,
                "event_occurred_at": delivery.event.occurred_at.isoformat(),
                "case_id": delivery.event.case_id,
                "consumer_group": delivery.consumer_group,
                "attempts": delivery.attempts,
                "state": delivery.state,
                "last_error": delivery.last_error,
                "last_error_type": delivery.last_error_type,
                "last_error_at": (
                    delivery.last_error_at.isoformat() if delivery.last_error_at else None
                ),
                "created_at": delivery.created_at.isoformat(),
                "updated_at": delivery.updated_at.isoformat(),
                "task_id": task.task_id if task is not None else None,
                "result": delivery.result.model_dump(mode="json") if delivery.result else None,
            }

        return {
            "pending": [serialize(item) for item in container.qms_worker.pending()],
            "processed": [serialize(item) for item in container.qms_worker.processed()],
            "dlq": [serialize(item) for item in container.qms_worker.dlq()],
        }

    @app.post("/api/v1/qms/retry-pending")
    def retry_qms_pending(
        request: Request,
        x_operator_id: str = Header(default="system", alias="X-Operator-Id"),
    ) -> list[object]:
        identity = authenticated(request, "qms.retry")
        result: list[object] = list(container.qms_worker.retry_pending(identity.actor_id))
        container.audit.record(
            identity,
            event_type="qms.delivery.retry.audit.v1",
            action="RETRY_PENDING",
            resource_type="qms_delivery",
            resource_id="pending",
            correlation_id=f"retry-pending:{identity.actor_id}",
            metadata={"requested_operator_id": x_operator_id},
        )
        sync_timeline()
        return result

    @app.get("/api/v1/cases/{case_id}/timeline")
    def case_timeline(case_id: str) -> list[dict[str, object]]:
        if container.cases.get_case(case_id) is None:
            raise HTTPException(status_code=404, detail="case not found")
        sync_timeline()
        return [entry.as_dict() for entry in container.timeline.list(case_id=case_id)]

    @app.get("/api/v1/operations/timeline")
    def operations_timeline(
        case_id: str | None = None, trace_id: str | None = None
    ) -> list[dict[str, object]]:
        sync_timeline()
        return [
            entry.as_dict() for entry in container.timeline.list(case_id=case_id, trace_id=trace_id)
        ]

    @app.get("/api/v1/operations/workers")
    def operations_workers() -> dict[str, object]:
        return {
            "workers": container.worker_metrics.snapshot(),
            "qms_pending": len(container.qms_worker.pending()),
            "qms_dlq": len(container.qms_worker.dlq()),
            "qms_processed": len(container.qms_worker.processed()),
        }

    @app.post("/api/v1/monitoring/baseline")
    def build_monitoring_baseline(
        window_minutes: int = Query(default=1, ge=1, le=60),
        baseline_version: str = Query(default="1.0", min_length=1, max_length=32),
    ) -> dict[str, object]:
        baselines = container.monitoring.build_baselines(
            window_minutes=window_minutes,
            baseline_version=baseline_version,
        )
        return {
            "baseline_count": len(baselines),
            "baselines": [baseline.as_dict() for baseline in baselines],
        }

    @app.get("/api/v1/monitoring/health", response_model=MonitoringReportContract)
    def monitoring_health(
        window_minutes: int = Query(default=1, ge=1, le=60),
    ) -> MonitoringReportContract:
        report = container.monitoring.evaluate(window_minutes=window_minutes)
        return _monitoring_report_contract(report)

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        """Prometheus scrape endpoint with no case/document high-cardinality labels."""

        return Response(
            content=container.prometheus_metrics.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/api/v1/operations/delivery")
    def operations_delivery() -> dict[str, list[dict[str, object]]]:
        return qms_delivery()

    @app.get("/api/v1/operations/analysis-metrics")
    def operations_analysis_metrics() -> list[dict[str, object]]:
        return container.analysis_metrics.list()

    @app.get("/api/v1/operations/retry-audit")
    def operations_retry_audit() -> list[dict[str, object]]:
        return [item.as_dict() for item in container.qms_worker.retry_audit()]

    @app.post("/api/v1/operations/retry-pending")
    def operations_retry_pending(
        request: Request,
        x_operator_id: str = Header(default="system", alias="X-Operator-Id"),
    ) -> list[object]:
        identity = authenticated(request, "qms.retry")
        result: list[object] = list(container.qms_worker.retry_pending(identity.actor_id))
        container.audit.record(
            identity,
            event_type="qms.delivery.retry.audit.v1",
            action="RETRY_PENDING",
            resource_type="qms_delivery",
            resource_id="pending",
            correlation_id=f"retry-pending:{identity.actor_id}",
            metadata={"requested_operator_id": x_operator_id},
        )
        sync_timeline()
        return result

    @app.post("/api/v1/operations/retry-dlq/{event_id}")
    def operations_retry_dlq(
        request: Request,
        event_id: str,
        x_operator_id: str | None = Header(default=None, alias="X-Operator-Id"),
    ) -> object:
        if not x_operator_id or not x_operator_id.strip():
            raise HTTPException(status_code=403, detail="X-Operator-Id is required")
        try:
            identity = authenticated(request, "qms.retry")
            result = container.qms_worker.retry_dlq(event_id, operator_id=identity.actor_id)
            container.audit.record(
                identity,
                event_type="qms.delivery.retry.audit.v1",
                action="RETRY_DLQ",
                resource_type="qms_delivery",
                resource_id=event_id,
                correlation_id=f"retry-dlq:{event_id}:{identity.actor_id}",
                metadata={"requested_operator_id": x_operator_id},
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        sync_timeline()
        return result

    def _run_fixture_demo(
        *,
        detector: CaseDetector | None = None,
        scenario: ScenarioName = ScenarioName.FIXTURE_OFFSET,
        start_at: datetime | None = None,
        replay_id: str | None = None,
    ) -> dict[str, object]:
        """Drive the local simulator through detection and the Investigation Worker."""

        for batch in scenario_replay(
            scenario,
            seed=7,
            batch_size=10,
            start_at=start_at,
            replay_id=replay_id,
        ):
            InspectionIngestionService(container.inspection).submit_batch(batch)
        MetricsWorker(container.inspection, container.metrics).run(window_minutes=(1, 5))
        detection = QualityCaseDetectionService(
            container.metrics, container.cases, detector=detector
        ).run()
        for event in detection.events:
            if event.event_type == "quality.case.opened.v1":
                container.investigations.handle_case_opened(event)
        return {"case_ids": [case.case_id for case in container.cases.list_cases()]}

    @app.post("/api/v1/demo/fixture-offset")
    def seed_fixture_demo() -> dict[str, object]:
        return _run_fixture_demo()

    @app.post("/api/v1/demo/fixture-offset/repeat")
    def seed_fixture_repeat_demo() -> dict[str, object]:
        """Create a second deterministic episode after the first case is archived."""

        return _run_fixture_demo(
            start_at=datetime(2026, 8, 23, 2, 0, tzinfo=UTC),
            replay_id="repeat-01",
        )

    @app.post("/api/v1/demo/illumination-drift")
    def seed_illumination_demo() -> dict[str, object]:
        return _run_fixture_demo(
            scenario=ScenarioName.ILLUMINATION_DRIFT,
            detector=IlluminationDriftCaseDetector(),
            replay_id="illumination-01",
        )

    @app.post("/api/v1/demo/insufficient-evidence")
    def seed_insufficient_evidence_demo() -> dict[str, object]:
        return _run_fixture_demo(
            scenario=ScenarioName.INSUFFICIENT_EVIDENCE,
            detector=InsufficientEvidenceCaseDetector(),
            replay_id="insufficient-01",
        )

    @app.post("/api/v1/demo/public-dataset-replay")
    def replay_public_dataset(
        request: PublicDatasetReplayRequestContract,
    ) -> dict[str, object]:
        """Replay label-consistent public samples through the production contracts.

        The lightweight demo uses deterministic normalized detector outputs. A real
        dataset runner can replace this source while keeping the same Vision/Inspection
        contract and downstream Case/Agent workflow.
        """

        if request.dataset == "VisA":
            scenario = ScenarioName.ILLUMINATION_DRIFT
            detector: CaseDetector | None = IlluminationDriftCaseDetector()
            frame_count = 60
        elif request.category.lower() == "cable":
            scenario = ScenarioName.INSUFFICIENT_EVIDENCE
            detector = InsufficientEvidenceCaseDetector()
            frame_count = 12
        else:
            scenario = ScenarioName.FIXTURE_OFFSET
            detector = None
            frame_count = 70
        replay_id = f"public-{request.dataset.lower().replace(' ', '-')}-{request.category.lower()}"
        result = _run_fixture_demo(
            scenario=scenario,
            detector=detector,
            replay_id=replay_id,
        )
        return {
            **result,
            "replay": {
                "dataset": request.dataset,
                "category": request.category,
                "model": request.model,
                "seed": request.seed,
                "fps": request.fps,
                "frame_count": frame_count,
                "source_mode": "DETERMINISTIC_NORMALIZED_OUTPUTS",
                "normalized_contract": "inspection.result.batch.v1",
            },
        }

    return app


def _vision_frame_from_request(request: VisionFrameRequestContract) -> VisionFrame:
    image: object
    if request.image_path is not None:
        image = Path(request.image_path)
    else:
        assert request.image_base64 is not None
        encoded = request.image_base64.split(",", 1)[-1]
        try:
            image = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("image_base64 is not valid base64") from exc
    return VisionFrame(
        frame_id=request.frame_id,
        inspected_at=request.inspected_at,
        factory_id=request.factory_id,
        line_id=request.line_id,
        station_id=request.station_id,
        product_id=request.product_id,
        unit_id=request.unit_id,
        batch_id=request.batch_id,
        image=image,
        scheme=request.scheme,
        image_uri=request.image_uri,
        metadata=request.metadata,
    )


def _vision_result_payload(result: VisionProcessingResult) -> dict[str, object]:
    return {
        "record": result.record,
        "receipt": asdict(result.receipt),
        "events": list(result.events),
    }


def _monitoring_report_contract(report: MonitoringReport) -> MonitoringReportContract:
    decisions = [MonitoringDecisionContract.model_validate(decision.as_dict()) for decision in report.decisions]
    return MonitoringReportContract(
        evaluated_at=report.evaluated_at,
        window_count=len(report.windows),
        baseline_count=len(report.baselines),
        decisions=decisions,
    )


app = create_app()
