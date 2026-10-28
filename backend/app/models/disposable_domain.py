from datetime import UTC, datetime

from pydantic import Field, field_validator

from backend.app.models.common import MongoBaseModel, PyObjectId


class DisposableDomainInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    domain: str = Field(..., min_length=3, max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, v: str) -> str:
        return v.strip().lower()
