"""Quality Case and immutable snapshot domain objects."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from .metrics import QualityMetricWindow

CaseStatus = Literal[
    "WAITING_INVESTIGATION",
    "ANALYZING",
    "AWAITING_APPROVAL",
    "APPROVED_PENDING_QMS",
    "QMS_OPEN",
    "CONFIRMED",
    "ARCHIVED",
]
EpisodeStatus = Literal["ACTIVE", "RECOVERED"]


@dataclass(frozen=True, slots=True)
class QualityCaseSnapshot:
    snapshot_id: str
    case_id: str
    created_at: datetime
    trigger_family: str
    observations: tuple[QualityMetricWindow, ...]
    lookback_window_minutes: int
    baseline_ng_rate: float
    baseline_score_mean: float
    data_quality_warnings: tuple[str, ...]
    snapshot_hash: str = field(init=False)

    def __post_init__(self) -> None:
        payload = {
            "snapshot_id": self.snapshot_id,
            "case_id": self.case_id,
            "created_at": self.created_at.isoformat(),
            "trigger_family": self.trigger_family,
            "observations": [window.as_dict() for window in self.observations],
            "lookback_window_minutes": self.lookback_window_minutes,
            "baseline_ng_rate": self.baseline_ng_rate,
            "baseline_score_mean": self.baseline_score_mean,
            "data_quality_warnings": list(self.data_quality_warnings),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "snapshot_hash", hashlib.sha256(canonical.encode()).hexdigest())

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible read-only-tool representation."""

        return {
            "snapshot_id": self.snapshot_id,
            "case_id": self.case_id,
            "created_at": self.created_at.isoformat(),
            "trigger_family": self.trigger_family,
            "observations": [window.as_dict() for window in self.observations],
            "lookback_window_minutes": self.lookback_window_minutes,
            "baseline_ng_rate": self.baseline_ng_rate,
            "baseline_score_mean": self.baseline_score_mean,
            "data_quality_warnings": list(self.data_quality_warnings),
            "snapshot_hash": self.snapshot_hash,
        }


@dataclass(slots=True)
class QualityCase:
    case_id: str
    fingerprint: str
    trigger_family: str
    opened_at: datetime
    snapshot: QualityCaseSnapshot
    case_status: CaseStatus = "WAITING_INVESTIGATION"
    episode_status: EpisodeStatus = "ACTIVE"
    recovered_at: datetime | None = None
    proposal_id: str | None = None
    qms_task_id: str | None = None
    qms_task_uri: str | None = None
    qms_task_status: str | None = None
    qms_external_system: str | None = None
    confirmation_id: str | None = None
    archive_uri: str | None = None
    archive_revision: int = 0

    def mark_recovered(self, recovered_at: datetime) -> None:
        self.episode_status = "RECOVERED"
        self.recovered_at = recovered_at

    def mark_awaiting_approval(self, proposal_id: str) -> None:
        self.proposal_id = proposal_id
        self.case_status = "AWAITING_APPROVAL"

    def mark_analyzing(self) -> None:
        self.case_status = "ANALYZING"

    def mark_qms_open(
        self,
        task_id: str,
        task_uri: str | None = None,
        task_status: str | None = None,
        external_system: str | None = None,
    ) -> None:
        self.qms_task_id = task_id
        self.qms_task_uri = task_uri
        self.qms_task_status = task_status or "OPEN"
        self.qms_external_system = external_system or "MOCK_QMS"
        self.case_status = "QMS_OPEN"

    def mark_approved_pending_qms(self, proposal_id: str) -> None:
        self.proposal_id = proposal_id
        self.case_status = "APPROVED_PENDING_QMS"

    def mark_confirmed(self, confirmation_id: str) -> None:
        self.confirmation_id = confirmation_id
        self.case_status = "CONFIRMED"

    def mark_archived(self, archive_uri: str, revision: int) -> None:
        self.archive_uri = archive_uri
        self.archive_revision = revision
        self.case_status = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class QualityCaseEvent:
    event_type: Literal["quality.case.opened.v1", "quality.episode.recovered.v1"]
    case_id: str
    occurred_at: datetime
    snapshot_id: str | None = None

    @property
    def event_id(self) -> str:
        return f"{self.event_type}:{self.case_id}"
