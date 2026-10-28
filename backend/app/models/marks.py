from datetime import UTC, datetime
from pydantic import Field
from backend.app.models.common import MongoBaseModel, PyObjectId


def calculate_grade(total_marks: float) -> str:
    """Computes academic letter grade based on standard 100-point scale."""
    if total_marks >= 90:
        return "A+"
    elif total_marks >= 80:
        return "A"
    elif total_marks >= 70:
        return "B"
    elif total_marks >= 60:
        return "C"
    elif total_marks >= 40:
        return "D"
    else:
        return "F"


class SubjectMarksInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    student_id: PyObjectId
    subject_id: PyObjectId
    subject_name: str
    subject_code: str
    semester: int = Field(..., ge=1, le=12)
    academic_year: str = Field(default="2024-25", max_length=20)
    internal_marks: float | None = Field(default=None, ge=0.0, le=50.0)
    external_marks: float | None = Field(default=None, ge=0.0, le=100.0)
    practical_marks: float | None = Field(default=None, ge=0.0, le=50.0)
    assignment_marks: float | None = Field(default=None, ge=0.0, le=50.0)
    total_marks: float = Field(..., ge=0.0, le=100.0)
    grade: str = Field(default="F", max_length=5)
    attendance: float = Field(default=100.0, ge=0.0, le=100.0)
    is_backlog: bool = Field(default=False)
    entered_by: PyObjectId | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
