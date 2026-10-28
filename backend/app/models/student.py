from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, field_validator

from backend.app.models.common import MongoBaseModel, PyObjectId


class StudentStatus(StrEnum):
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    DROPPED = "dropped"
    GRADUATED = "graduated"


class StudentInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    erp_id: str = Field(..., min_length=1, max_length=50)
    user_id: PyObjectId | None = None
    name: str = Field(..., min_length=1, max_length=120)
    institutional_email: str | None = Field(default=None, max_length=254)
    department: str = Field(..., min_length=1, max_length=100)
    semester: int = Field(..., ge=1, le=12)
    batch: str = Field(..., min_length=4, max_length=20)
    phone: str | None = Field(default=None, max_length=25)
    dob: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)
    course: str | None = Field(default=None, max_length=100)
    year: str | None = Field(default=None, max_length=50)
    division: str | None = Field(default=None, max_length=20)
    admission_year: str | None = Field(default=None, max_length=20)
    assigned_teacher_ids: list[PyObjectId] = Field(default_factory=list)
    status: StudentStatus = StudentStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("erp_id")
    @classmethod
    def normalize_erp_id(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("institutional_email")
    @classmethod
    def normalize_institutional_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().lower()
