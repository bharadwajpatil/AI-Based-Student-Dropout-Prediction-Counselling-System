from datetime import UTC, datetime

from pydantic import Field, model_validator

from backend.app.models.common import MongoBaseModel, PyObjectId


class PerformanceInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    student_id: PyObjectId
    semester: int = Field(..., ge=1, le=12)
    academic_year: str = Field(..., min_length=4, max_length=20)
    attendance: float | None = Field(default=None, ge=0.0, le=100.0)
    classes_held: int | None = Field(default=None, ge=0)
    marks: float | None = Field(default=None, ge=0.0, le=100.0)
    backlogs: int | None = Field(default=None, ge=0, le=50)
    assignments: float | None = Field(default=None, ge=0.0, le=100.0)
    engagement: float | None = Field(default=None, ge=0.0, le=100.0)
    version: int = Field(default=1, ge=1)
    updated_by: PyObjectId | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_classes_held_with_attendance(self) -> "PerformanceInDB":
        if self.attendance is not None and self.classes_held is None:
            raise ValueError("classes_held is required when attendance is provided.")
        return self
