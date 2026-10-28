from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from backend.app.models.common import MongoBaseModel, PyObjectId


class ImportStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportJobInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    created_by: PyObjectId
    filename: str = Field(..., min_length=1, max_length=255)
    status: ImportStatus = ImportStatus.PENDING
    total: int = Field(default=0, ge=0)
    succeeded: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
