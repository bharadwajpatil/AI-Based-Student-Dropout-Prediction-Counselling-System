from datetime import UTC, datetime
from pydantic import Field, field_validator
from backend.app.models.common import MongoBaseModel, PyObjectId


class SubjectInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=50)
    department: str = Field(..., min_length=1, max_length=100)
    year: str = Field(..., min_length=1, max_length=50)
    semester: int = Field(..., ge=1, le=12)
    credits: int = Field(default=3, ge=1, le=10)
    academic_year: str = Field(default="2024-25", max_length=20)
    assigned_teacher_id: PyObjectId | None = None
    assigned_teacher_name: str | None = None
    hod_id: PyObjectId | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip()
