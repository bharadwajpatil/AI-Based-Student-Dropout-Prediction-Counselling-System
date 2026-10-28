from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PerformanceSchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PerformanceUpsertRequest(PerformanceSchemaBase):
    academic_year: str = Field(..., min_length=4, max_length=20)
    attendance: float | None = Field(default=None, ge=0.0, le=100.0)
    classes_held: int | None = Field(default=None, ge=0)
    marks: float | None = Field(default=None, ge=0.0, le=100.0)
    backlogs: int | None = Field(default=None, ge=0, le=50)
    assignments: float | None = Field(default=None, ge=0.0, le=100.0)
    engagement: float | None = Field(default=None, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_classes_held_with_attendance(self) -> "PerformanceUpsertRequest":
        if self.attendance is not None and self.classes_held is None:
            raise ValueError("classes_held is required when attendance is provided.")
        return self


class PerformanceResponse(PerformanceSchemaBase):
    id: str
    student_id: str
    semester: int
    academic_year: str
    attendance: float | None = None
    classes_held: int | None = None
    marks: float | None = None
    backlogs: int | None = None
    assignments: float | None = None
    engagement: float | None = None
    version: int
    updated_by: str | None = None
    updated_at: datetime
