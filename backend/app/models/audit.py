from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from backend.app.models.common import MongoBaseModel, PyObjectId


class AuditLogInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    actor_id: PyObjectId | None = None
    action: str = Field(..., min_length=1, max_length=100)
    target_type: str = Field(..., min_length=1, max_length=100)
    target_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip: str | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
