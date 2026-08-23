"""Case confirmation archive and trusted knowledge promotion use case."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from quality_case_agent.application.ports.approval import ProposalStore
from quality_case_agent.application.ports.archive import CaseArchiveStore, VerifiedCaseIndex
from quality_case_agent.application.ports.investigation import AnalysisRunStore
from quality_case_agent.application.ports.knowledge import KnowledgeBase
from quality_case_agent.application.ports.qms import QmsClient
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.application.qms.service import QmsWebhookService
from quality_case_agent.contracts.approval import ApprovalEventContract
from quality_case_agent.contracts.investigation import InvestigationOutputContract, ProposalContract
from quality_case_agent.contracts.knowledge import CaseArchivedEventContract
from quality_case_agent.contracts.qms import (
    CaseConfirmedEventContract,
    QmsTaskContract,
    QmsTaskResultContract,
)
from quality_case_agent.domain.knowledge.models import KnowledgeDocument, VerifiedCaseIndexRecord
from quality_case_agent.domain.quality_case.models import QualityCase


class CaseArchiveService:
    def __init__(
        self,
        archive: CaseArchiveStore,
        index: VerifiedCaseIndex,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._archive = archive
        self._index = index
        self._knowledge_base = knowledge_base
        self._events: dict[str, CaseArchivedEventContract] = {}

    def archive(
        self,
        case: QualityCase,
        investigation: InvestigationOutputContract,
        approved_proposal_id: str,
        qms_task: QmsTaskContract,
        result: QmsTaskResultContract,
        *,
        approval_event: ApprovalEventContract | None = None,
        approved_proposal: ProposalContract | None = None,
    ) -> CaseArchivedEventContract:
        existing = self._events.get(result.event_id)
        if existing is not None:
            return existing
        if case.case_id != result.case_id or case.qms_task_id != qms_task.task_id:
            raise ValueError("archive inputs do not belong to the same Case/QMS task")
        revision = case.archive_revision + 1
        occurred_at = result.occurred_at.astimezone(UTC)
        date_prefix = occurred_at.strftime("%Y-%m-%d")
        archive_uri = (
            f"case_archive/{occurred_at:%Y/%m/%d}/{date_prefix}_{case.case_id}_r{revision}.json"
        )
        payload = {
            "schema_version": "1.0",
            "archived_at": occurred_at.isoformat(),
            "case": {
                "case_id": case.case_id,
                "episode_status": case.episode_status,
                "case_status": "CONFIRMED",
            },
            "snapshot": case.snapshot.as_dict(),
            "investigation": investigation.model_dump(mode="json"),
            "approved_proposal_id": approved_proposal_id,
            "approval": (
                approval_event.model_dump(mode="json")
                if approval_event is not None
                else {"approved_proposal_id": approved_proposal_id}
            ),
            "approved_proposal": (
                approved_proposal.model_dump(mode="json")
                if approved_proposal is not None
                else {"proposal_id": approved_proposal_id}
            ),
            "qms_task": qms_task.model_dump(mode="json"),
            "human_confirmation": result.model_dump(mode="json"),
            "integrity": {"content_hash": ""},
        }
        canonical_without_hash = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        content_hash = hashlib.sha256(canonical_without_hash.encode("utf-8")).hexdigest()
        payload["integrity"] = {"content_hash": f"sha256:{content_hash}"}
        serialized = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        self._archive.put(archive_uri, serialized, content_hash)

        eligible = (
            result.verification.status == "VERIFIED_EFFECTIVE"
            and bool(result.actual_root_cause.description.strip())
            and bool(result.actual_actions)
        )
        index_document_id = None
        if eligible:
            index_document_id = f"verified-case:{case.case_id}:r{revision}"
            text = (
                f"日期：{date_prefix}\n案例：{case.case_id}\n"
                f"工位：{case.snapshot.observations[0].station_id}\n"
                f"产品：{case.snapshot.observations[0].product_id}\n"
                f"异常表现：NG率达到{case.snapshot.observations[-1].ng_rate:.2%}，"
                f"异常区域集中于upper_right。\n"
                f"人工确认根因：{result.actual_root_cause.description}\n"
                f"实际措施：{'、'.join(result.actual_actions)}\n"
                f"验证结果：{result.verification.status}，样本数{result.verification.sample_count}。"
            )
            index_record = VerifiedCaseIndexRecord(
                document_id=index_document_id,
                text=text,
                metadata={
                    "case_id": case.case_id,
                    "date_prefix": date_prefix,
                    "factory_id": case.snapshot.observations[0].factory_id,
                    "line_id": case.snapshot.observations[0].line_id,
                    "station_id": case.snapshot.observations[0].station_id,
                    "product_id": case.snapshot.observations[0].product_id,
                    "trigger_family": case.trigger_family,
                    "root_cause_code": result.actual_root_cause.code,
                    "case_status": "CONFIRMED",
                    "verification_status": result.verification.status,
                    "archive_uri": archive_uri,
                    "archive_revision": str(revision),
                    "indexed_at": occurred_at.isoformat(),
                },
                content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
            self._index.index(index_record)
            if self._knowledge_base is not None:
                self._knowledge_base.ingest(
                    KnowledgeDocument(
                        document_id=index_document_id,
                        title=f"已验证案例 {case.case_id}",
                        version=f"archive-r{revision}",
                        source_type="VERIFIED_CASE",
                        content=text,
                        # Historical cases remain searchable after indexing; the
                        # incident date is retained as structured metadata instead
                        # of acting as a document expiry time.
                        effective_from=datetime(1970, 1, 1, tzinfo=UTC),
                        effective_to=None,
                        applicability=index_record.metadata,
                    )
                )

        case.mark_archived(archive_uri, revision)
        event = CaseArchivedEventContract(
            event_id=f"evt-case-archived:{result.event_id}:r{revision}",
            occurred_at=occurred_at,
            case_id=case.case_id,
            archive_uri=archive_uri,
            knowledge_index_status="INDEXED" if eligible else "NOT_ELIGIBLE",
            knowledge_document_id=index_document_id,
            content_hash=content_hash,
        )
        self._events[result.event_id] = event
        return event


@dataclass(frozen=True, slots=True)
class CaseClosureOutcome:
    """The two durable business events produced by one signed QMS result."""

    confirmation: CaseConfirmedEventContract
    archived: CaseArchivedEventContract


class CaseClosureService:
    """Orchestrate signed confirmation, full archive, and trusted-case promotion."""

    def __init__(
        self,
        webhook: QmsWebhookService,
        archive: CaseArchiveService,
        proposals: ProposalStore,
        runs: AnalysisRunStore,
        cases: QualityCaseStore,
        qms: QmsClient,
    ) -> None:
        self._webhook = webhook
        self._archive = archive
        self._proposals = proposals
        self._runs = runs
        self._cases = cases
        self._qms = qms

    def process(
        self, result: QmsTaskResultContract, signature: str
    ) -> CaseClosureOutcome:
        task = self._qms.get_task(result.task_id)
        if task is None:
            raise KeyError(f"QMS task not found: {result.task_id}")
        if task.case_id != result.case_id:
            raise ValueError("QMS task does not belong to the submitted Case")
        confirmation = self._webhook.process(result, signature)
        case = self._cases.get_case(result.case_id)
        if case is None:
            raise KeyError(f"case not found: {result.case_id}")

        approval_event = self._find_approval_event(task.proposal_id, result.case_id)
        proposal = self._proposals.get_proposal(task.proposal_id)
        if proposal is None:
            raise KeyError(f"approved Proposal not found: {task.proposal_id}")
        investigation = self._runs.get_output(proposal.analysis_run_id)
        if investigation is None:
            raise KeyError(f"Analysis Run output not found: {proposal.analysis_run_id}")

        archived = self._archive.archive(
            case,
            investigation,
            task.proposal_id,
            task,
            result,
            approval_event=approval_event,
            approved_proposal=proposal,
        )
        self._cases.save_case(case)
        return CaseClosureOutcome(confirmation=confirmation, archived=archived)

    def _find_approval_event(
        self, approved_proposal_id: str, case_id: str
    ) -> ApprovalEventContract:
        for event in reversed(tuple(self._proposals.list_events())):
            if (
                event.event_type == "quality.investigation.approved.v1"
                and event.case_id == case_id
                and (
                    event.approved_proposal_id == approved_proposal_id
                    or event.proposal_id == approved_proposal_id
                )
            ):
                return event
        raise KeyError(f"approval event not found for Proposal: {approved_proposal_id}")
