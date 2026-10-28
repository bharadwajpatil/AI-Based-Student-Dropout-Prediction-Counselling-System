from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.counselling import AISource, CounsellingStatus


class AICounsellingRecommendation(BaseModel):
    """Structured recommendation produced by Gemini AI or Template Fallback."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1, description="Concise diagnostic summary of student academic situation")
    actions: list[str] = Field(
        ...,
        min_length=1,
        description="Concrete mentorship, pedagogical, and study intervention actions",
    )
    follow_up_in_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Recommended follow-up review timeframe in days",
    )
    escalate_to_hod: bool = Field(
        default=False,
        description="Flag indicating if departmental leadership escalation is warranted",
    )
    refer_to_counsellor: bool = Field(
        default=False,
        description="Flag indicating immediate referral to professional campus student wellness counselor",
    )


class CounsellingNoteCreate(BaseModel):
    """Payload for adding a note to the student's counselling timeline."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1, max_length=5000, description="Observation or meeting note content")


class CounsellingNoteResponse(BaseModel):
    """Note item within the timeline."""

    model_config = ConfigDict(extra="forbid")

    id: str
    author_id: str
    author_name: str
    author_role: str
    content: str
    created_at: datetime


class CounsellingUpdate(BaseModel):
    """Payload for updating counselling case status and attributes."""

    model_config = ConfigDict(extra="forbid")

    status: CounsellingStatus | None = None
    follow_up_date: datetime | None = None
    escalate_to_hod: bool | None = None
    refer_to_counsellor: bool | None = None


class CounsellingResponse(BaseModel):
    """Detailed response for a counselling case."""

    model_config = ConfigDict(extra="forbid")

    id: str
    student_id: str
    teacher_id: str | None = None
    risk_result_id: str
    risk_level: str
    status: CounsellingStatus
    summary: str
    actions: list[str]
    follow_up_in_days: int
    follow_up_date: datetime | None = None
    escalate_to_hod: bool
    refer_to_counsellor: bool
    ai_source: AISource
    ai_recommendation: str
    is_outdated: bool = False
    risk_computed_at: datetime | None = None
    notes_timeline: list[CounsellingNoteResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CounsellingListResponse(BaseModel):
    """Paginated list of counselling cases."""

    model_config = ConfigDict(extra="forbid")

    items: list[CounsellingResponse]
    total: int
    skip: int
    limit: int
