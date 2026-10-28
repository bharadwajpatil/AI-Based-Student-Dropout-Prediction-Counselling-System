from datetime import UTC, datetime
from typing import Any
from pydantic import Field
from backend.app.models.common import MongoBaseModel, PyObjectId


class StudyPlanInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    student_id: PyObjectId
    weekly_schedule: dict[str, list[str]] = Field(default_factory=dict)
    backlog_plans: list[dict[str, Any]] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    overall_advice: str = ""
    target_attendance: float = 85.0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
