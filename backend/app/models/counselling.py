import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from backend.app.models.common import MongoBaseModel, PyObjectId


class CounsellingStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    FOLLOW_UP = "follow_up"
    RESOLVED = "resolved"


class AISource(StrEnum):
    GEMINI = "gemini"
    TEMPLATE = "template"


class CounsellingNote(MongoBaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    author_id: PyObjectId
    author_name: str = Field(..., min_length=1)
    author_role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CounsellingInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    student_id: PyObjectId
    teacher_id: PyObjectId | None = None
    risk_result_id: PyObjectId
    risk_level: str = Field(..., min_length=1)
    ai_recommendation: str = Field(..., min_length=1)
    ai_source: AISource = AISource.TEMPLATE
    notes: str = ""
    status: CounsellingStatus = CounsellingStatus.PENDING
    follow_up_date: datetime | None = None
    summary: str = ""
    actions: list[str] = Field(default_factory=list)
    follow_up_in_days: int = 7
    escalate_to_hod: bool = False
    refer_to_counsellor: bool = False
    notes_timeline: list[CounsellingNote] = Field(default_factory=list)
    inputs_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

