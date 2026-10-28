from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MarksSchemaBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MarksEntryRequest(MarksSchemaBase):
    internal_marks: float | None = Field(default=None, ge=0.0, le=50.0)
    external_marks: float | None = Field(default=None, ge=0.0, le=100.0)
    practical_marks: float | None = Field(default=None, ge=0.0, le=50.0)
    assignment_marks: float | None = Field(default=None, ge=0.0, le=50.0)
    total_marks: float = Field(..., ge=0.0, le=100.0)
    attendance: float = Field(default=100.0, ge=0.0, le=100.0)
    semester: int = Field(..., ge=1, le=12)
    academic_year: str = Field(default="2024-25", max_length=20)


class SubjectMarksResponse(MarksSchemaBase):
    id: str
    student_id: str
    subject_id: str
    subject_name: str
    subject_code: str
    semester: int
    academic_year: str
    internal_marks: float | None = None
    external_marks: float | None = None
    practical_marks: float | None = None
    assignment_marks: float | None = None
    total_marks: float
    grade: str
    attendance: float
    is_backlog: bool
    entered_by: str | None = None
    updated_at: datetime


class StudentBacklogSummary(MarksSchemaBase):
    student_id: str
    student_name: str
    total_subjects: int
    passed_subjects: int
    backlog_count: int
    backlog_subjects: list[SubjectMarksResponse]
