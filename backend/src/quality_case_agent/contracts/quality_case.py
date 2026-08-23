"""Quality Case lifecycle and snapshot contracts."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, to_utc


class QualityCaseOpenedEventContract(ContractModel):
    """Validated event consumed by the Investigation Worker."""

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["quality.case.opened.v1"] = "quality.case.opened.v1"
    occurred_at: datetime
    case_id: str = Field(min_length=1, max_length=128)
    snapshot_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "QualityCaseOpenedEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self
