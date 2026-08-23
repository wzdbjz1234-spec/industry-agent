"""Common protocol envelope and primitive contract types."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Strict base model for messages crossing process boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def to_utc(value: datetime) -> datetime:
    """Require an aware timestamp and normalize it to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC)
