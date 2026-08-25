"""Identity, authorization and tamper-evident audit contracts."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, to_utc

Role = Literal["VIEWER", "QUALITY_ENGINEER", "APPROVER", "OPERATOR", "ADMIN"]
AuthSource = Literal["DEMO", "OIDC", "SYSTEM"]


class IdentityContract(ContractModel):
    """The minimum trusted identity context carried into application use cases."""

    actor_id: str = Field(min_length=1, max_length=128)
    subject: str = Field(min_length=1, max_length=256)
    roles: list[Role] = Field(min_length=1, max_length=8)
    organization: str = Field(min_length=1, max_length=256)
    auth_source: AuthSource
    claims_digest: str = Field(min_length=8, max_length=128)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_window(self) -> "IdentityContract":
        issued_at = to_utc(self.issued_at)
        expires_at = to_utc(self.expires_at)
        if expires_at <= issued_at:
            raise ValueError("identity expires_at must be after issued_at")
        object.__setattr__(self, "issued_at", issued_at)
        object.__setattr__(self, "expires_at", expires_at)
        return self


class AuditEventContract(ContractModel):
    """Append-only audit record; hashes make accidental mutation detectable."""

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=128)
    occurred_at: datetime
    actor_id: str = Field(min_length=1, max_length=128)
    roles: list[Role] = Field(min_length=1, max_length=8)
    organization: str = Field(min_length=1, max_length=256)
    action: str = Field(min_length=1, max_length=128)
    resource_type: str = Field(min_length=1, max_length=128)
    resource_id: str = Field(min_length=1, max_length=160)
    correlation_id: str = Field(min_length=1, max_length=160)
    causation_id: str | None = Field(default=None, max_length=160)
    trace_id: str | None = Field(default=None, max_length=160)
    policy_version: str = Field(min_length=1, max_length=64)
    claims_digest: str = Field(min_length=8, max_length=128)
    metadata: dict[str, object] = Field(default_factory=dict)
    previous_hash: str | None = Field(default=None, max_length=128)
    event_hash: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "AuditEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self
