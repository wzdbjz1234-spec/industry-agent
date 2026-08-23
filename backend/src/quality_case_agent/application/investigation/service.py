"""Investigation worker orchestration and Analysis Run idempotency."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from quality_case_agent.application.observability.service import (
    AnalysisMetricsRegistry,
    WorkerMetricsRegistry,
    redact_error,
)
from quality_case_agent.application.ports.investigation import (
    AnalysisRunStore,
    InvestigationEventPublisher,
)
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.contracts.investigation import (
    AnalysisCompletedEventContract,
    AnalysisFailedEventContract,
    AnalysisStartedEventContract,
    InvestigationOutputContract,
    ProposalContract,
)
from quality_case_agent.contracts.quality_case import QualityCaseOpenedEventContract
from quality_case_agent.domain.investigation.models import AnalysisRun
from quality_case_agent.domain.quality_case.models import QualityCaseEvent

from .agent import InvestigationAgent


class InvestigationService:
    """Consume ``quality.case.opened.v1`` and run one bounded Agent per snapshot event."""

    def __init__(
        self,
        agent: InvestigationAgent,
        runs: AnalysisRunStore,
        events: InvestigationEventPublisher,
        cases: QualityCaseStore | None = None,
        proposal_registrar: Callable[[InvestigationOutputContract], ProposalContract] | None = None,
        metrics: WorkerMetricsRegistry | None = None,
        analysis_metrics: AnalysisMetricsRegistry | None = None,
    ) -> None:
        self._agent = agent
        self._runs = runs
        self._events = events
        self._cases = cases
        self._proposal_registrar = proposal_registrar
        self._metrics = metrics
        self._analysis_metrics = analysis_metrics

    def set_proposal_registrar(
        self, registrar: Callable[[InvestigationOutputContract], ProposalContract]
    ) -> None:
        """Connect Proposal persistence after the composition root resolves the cycle."""

        self._proposal_registrar = registrar

    def handle_case_opened(
        self, event: QualityCaseEvent | QualityCaseOpenedEventContract
    ) -> InvestigationOutputContract:
        if event.event_type != "quality.case.opened.v1":
            raise ValueError("only quality.case.opened.v1 triggers an investigation")
        case = self._cases.get_case(event.case_id) if self._cases is not None else None
        if case is None and self._cases is not None:
            raise KeyError(f"case not found: {event.case_id}")
        snapshot_id = (
            case.snapshot.snapshot_id
            if case is not None
            else getattr(event, "snapshot_id", None) or event.case_id
        )
        key = f"{event.event_id}:{event.case_id}:{snapshot_id}"
        existing = self._runs.get_by_idempotency_key(key)
        if existing is not None:
            output = self._runs.get_output(existing.analysis_run_id)
            if output is None:
                raise RuntimeError("analysis run exists without a persisted output")
            return output
        run_id = _run_id(key)
        return self._execute(
            run_id=run_id,
            key=key,
            trigger_event_id=event.event_id,
            case_id=event.case_id,
            snapshot_id=snapshot_id,
        )

    def reanalyze(self, case_id: str, snapshot_id: str, request_id: str) -> str:
        key = f"reanalysis:{request_id}:{case_id}:{snapshot_id}"
        existing = self._runs.get_by_idempotency_key(key)
        if existing is not None:
            return existing.analysis_run_id
        run_id = _run_id(key)
        self._execute(
            run_id=run_id,
            key=key,
            trigger_event_id=f"reanalysis:{request_id}",
            case_id=case_id,
            snapshot_id=snapshot_id,
        )
        return run_id

    def _execute(
        self,
        *,
        run_id: str,
        key: str,
        trigger_event_id: str,
        case_id: str,
        snapshot_id: str,
    ) -> InvestigationOutputContract:
        started_clock = perf_counter()
        started_at = datetime.now(UTC)
        run = AnalysisRun(
            analysis_run_id=run_id,
            case_id=case_id,
            snapshot_id=snapshot_id,
            trigger_event_id=trigger_event_id,
            idempotency_key=key,
            status="STARTED",
            started_at=started_at,
        )
        self._runs.save_run(run)
        self._events.publish(
            AnalysisStartedEventContract(
                event_id=f"{run_id}:started",
                occurred_at=started_at,
                analysis_run_id=run_id,
                case_id=case_id,
                snapshot_id=snapshot_id,
                trigger_event_id=trigger_event_id,
            )
        )
        try:
            output = self._agent.analyze(case_id, snapshot_id, analysis_run_id=run_id)
        except Exception as exc:
            completed_at = datetime.now(UTC)
            run.status = "FAILED"
            run.completed_at = completed_at
            run.error_summary = redact_error(str(exc))
            self._runs.save_run(run)
            self._events.publish(
                AnalysisFailedEventContract(
                    event_id=f"{run_id}:failed",
                    occurred_at=completed_at,
                    analysis_run_id=run_id,
                    case_id=case_id,
                    snapshot_id=snapshot_id,
                    error_code="INVESTIGATION_FAILED",
                    error_summary=run.error_summary,
                )
            )
            self._observe_worker(
                run_id,
                trigger_event_id,
                started_clock,
                status="FAILED",
                error_type=type(exc).__name__,
                error=str(exc),
                error_category="SYSTEM_FAILURE",
            )
            raise
        completed_at = datetime.now(UTC)
        output_status = output.analysis.status
        run.status = output_status
        run.completed_at = completed_at
        run.proposal_id = output.proposal.proposal_id if output.proposal is not None else None
        run.trace_event_count = len(output.trace.events)
        self._runs.save_output(output)
        if output.proposal is not None and self._proposal_registrar is not None:
            self._proposal_registrar(output)
        self._runs.save_run(run)
        if output_status == "FAILED":
            self._events.publish(
                AnalysisFailedEventContract(
                    event_id=f"{run_id}:failed",
                    occurred_at=completed_at,
                    analysis_run_id=run_id,
                    case_id=case_id,
                    snapshot_id=snapshot_id,
                    error_code="AGENT_TERMINATED",
                    error_summary=output.analysis.termination_reason,
                )
            )
        else:
            self._events.publish(
                AnalysisCompletedEventContract(
                    event_id=f"{run_id}:completed",
                    occurred_at=completed_at,
                    analysis_run_id=run_id,
                    case_id=case_id,
                    snapshot_id=snapshot_id,
                    status=output_status,
                    proposal_id=run.proposal_id,
                    trace_event_count=run.trace_event_count,
                )
            )
        tool_calls = [event for event in output.trace.events if event.event_type == "TOOL_CALL"]
        retrieval_calls = sum(
            1 for event in tool_calls if event.action == "search_knowledge_base"
        )
        if self._analysis_metrics is not None:
            estimated_tokens = max(
                1,
                sum(len(event.summary) for event in output.trace.events) // 4,
            )
            self._analysis_metrics.record(
                run_id=run_id,
                case_id=case_id,
                status=output_status,
                duration_ms=int((perf_counter() - started_clock) * 1000),
                tool_call_count=len(tool_calls),
                retrieval_call_count=retrieval_calls,
                estimated_tokens=estimated_tokens,
                estimated_cost_cny=estimated_tokens * 0.00001,
            )
        self._observe_worker(
            run_id,
            trigger_event_id,
            started_clock,
            status="PROCESSED",
        )
        return output

    def _observe_worker(
        self,
        run_id: str,
        event_id: str,
        started: float,
        *,
        status: str,
        error_type: str | None = None,
        error: str | None = None,
        error_category: str | None = None,
    ) -> None:
        if self._metrics is not None:
            self._metrics.observe(
                "investigation-worker",
                status=status,
                duration_ms=int((perf_counter() - started) * 1000),
                event_id=event_id or run_id,
                error_type=error_type,
                error=error,
                error_category=error_category,
            )


def _run_id(idempotency_key: str) -> str:
    value = uuid5(NAMESPACE_URL, f"quality-case-analysis:{idempotency_key}")
    return f"ar-{value.hex[:20]}"
