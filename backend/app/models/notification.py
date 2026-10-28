from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from backend.app.models.common import MongoBaseModel, PyObjectId


class NotificationInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    user_id: PyObjectId
    type: str = Field(..., min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
