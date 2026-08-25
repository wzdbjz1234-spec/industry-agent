"""Mock QMS task creation and signed result webhook use cases."""

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from quality_case_agent.application.ports.approval import ProposalStore
from quality_case_agent.application.ports.qms import QmsClient, QmsTransientError
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.contracts.approval import ApprovalEventContract
from quality_case_agent.contracts.qms import (
    CaseConfirmedEventContract,
    QmsTaskCreatedEventContract,
    QmsTaskResultContract,
)

from .modes import QmsMode, QmsModePolicy
from .resilience import CircuitBreaker, TokenBucketRateLimiter


def sign_qms_result(result: QmsTaskResultContract, secret: bytes) -> str:
    """Create the canonical HMAC used by both Mock QMS and the API webhook."""

    canonical = json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_qms_result_with_timestamp(
    result: QmsTaskResultContract,
    secret: bytes,
    *,
    timestamp: str,
    nonce: str,
) -> str:
    """Sign body + timestamp + nonce so a captured webhook cannot be replayed."""

    canonical = _canonical_result(result)
    payload = f"{timestamp}.{nonce}.{canonical}"
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _canonical_result(result: QmsTaskResultContract) -> str:
    return json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class QmsIntegrationService:
    def __init__(
        self,
        proposals: ProposalStore,
        cases: QualityCaseStore,
        qms: QmsClient,
        *,
        mode: QmsMode = "SANDBOX",
        rate_limiter: TokenBucketRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._proposals = proposals
        self._cases = cases
        self._qms = qms
        self._mode = QmsModePolicy.validate(mode)
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

    @property
    def mode(self) -> QmsMode:
        return self._mode

    def handle_approved(self, event: ApprovalEventContract) -> QmsTaskCreatedEventContract:
        if event.event_type != "quality.investigation.approved.v1":
            raise ValueError("only approved events can create QMS tasks")
        approved_id = event.approved_proposal_id or event.proposal_id
        proposal = self._proposals.get_proposal(approved_id)
        if proposal is None:
            raise KeyError(f"approved Proposal not found: {approved_id}")
        self._circuit_breaker.before_call()
        if not self._rate_limiter.acquire():
            raise QmsTransientError("QMS rate limit exceeded")
        try:
            task = self._qms.create_task(proposal)
        except QmsTransientError:
            self._circuit_breaker.record_failure()
            raise
        else:
            self._circuit_breaker.record_success()
        case = self._cases.get_case(event.case_id)
        if case is None:
            raise KeyError(f"case not found: {event.case_id}")
        if QmsModePolicy.allows_external_write(self._mode):
            case.mark_qms_open(
                task.task_id,
                task.task_uri,
                task.status,
                task.external_system,
            )
            self._cases.save_case(case)
        return QmsTaskCreatedEventContract(
            event_id=f"evt-qms-task-created:{task.task_id}",
            occurred_at=task.created_at,
            task=task,
        )


class QmsWebhookService:
    """Verify signed QMS results and protect against event replay."""

    def __init__(
        self,
        cases: QualityCaseStore,
        secret: bytes,
        *,
        clock: Callable[[], datetime] | None = None,
        max_age: timedelta = timedelta(days=7),
        max_future_skew: timedelta = timedelta(minutes=5),
    ) -> None:
        if max_age <= timedelta(0) or max_future_skew < timedelta(0):
            raise ValueError("webhook time-window settings must be non-negative")
        self._cases = cases
        self._secret = secret
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_age = max_age
        self._max_future_skew = max_future_skew
        self._processed_events: dict[str, CaseConfirmedEventContract] = {}
        self._results: dict[str, QmsTaskResultContract] = {}
        self._seen_nonces: set[tuple[str, str]] = set()

    def process(
        self,
        result: QmsTaskResultContract,
        signature: str,
        *,
        timestamp: str | None = None,
        nonce: str | None = None,
    ) -> CaseConfirmedEventContract:
        if (timestamp is None) != (nonce is None):
            raise ValueError("QMS webhook timestamp and nonce must be provided together")
        if timestamp is not None and nonce is not None:
            self._validate_timestamp(timestamp)
            if not nonce or len(nonce) > 128:
                raise ValueError("QMS webhook nonce is invalid")
            expected = sign_qms_result_with_timestamp(
                result,
                self._secret,
                timestamp=timestamp,
                nonce=nonce,
            )
            nonce_key = (result.event_id, nonce)
            if nonce_key in self._seen_nonces and result.event_id not in self._processed_events:
                raise ValueError("QMS webhook nonce has already been used")
        else:
            expected = self.sign(result)
        if not hmac.compare_digest(expected, signature):
            raise ValueError("invalid QMS webhook signature")
        if timestamp is not None and nonce is not None:
            self._seen_nonces.add((result.event_id, nonce))
        now = self._clock().astimezone(UTC)
        if result.occurred_at < now - self._max_age:
            raise ValueError("QMS result is outside the allowed time window")
        if result.occurred_at > now + self._max_future_skew:
            raise ValueError("QMS result occurred_at is in the future")
        existing = self._processed_events.get(result.event_id)
        if existing is not None:
            return existing
        case = self._cases.get_case(result.case_id)
        if case is None:
            raise KeyError(f"case not found: {result.case_id}")
        if case.qms_task_id != result.task_id:
            raise ValueError("QMS task does not belong to the Case")
        case.mark_confirmed(result.confirmation_id)
        self._cases.save_case(case)
        event = CaseConfirmedEventContract(
            event_id=f"evt-case-confirmed:{result.confirmation_id}",
            occurred_at=result.occurred_at,
            case_id=result.case_id,
            confirmation_id=result.confirmation_id,
            verification_status=result.verification.status,
            knowledge_promotion_eligible=(
                result.verification.status == "VERIFIED_EFFECTIVE"
                and bool(result.actual_root_cause.description.strip())
                and bool(result.actual_actions)
            ),
            confirmed_by=result.confirmed_by,
        )
        self._processed_events[result.event_id] = event
        self._results[result.case_id] = result
        return event

    def get_result(self, case_id: str) -> QmsTaskResultContract | None:
        return self._results.get(case_id)

    def sign(self, result: QmsTaskResultContract) -> str:
        return sign_qms_result(result, self._secret)

    def sign_with_timestamp(self, result: QmsTaskResultContract, *, timestamp: str, nonce: str) -> str:
        return sign_qms_result_with_timestamp(result, self._secret, timestamp=timestamp, nonce=nonce)

    def _validate_timestamp(self, timestamp: str) -> datetime:
        try:
            value = datetime.fromtimestamp(float(timestamp), tz=UTC)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("QMS webhook timestamp is invalid") from exc
        now = self._clock().astimezone(UTC)
        if value < now - self._max_age or value > now + self._max_future_skew:
            raise ValueError("QMS webhook timestamp is outside the allowed time window")
        return value
