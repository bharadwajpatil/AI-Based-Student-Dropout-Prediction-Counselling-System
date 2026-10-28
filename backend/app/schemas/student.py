from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.models.student import StudentStatus


class StudentSchemaBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


class StudentCreateRequest(StudentSchemaBase):
    erp_id: str | None = Field(default=None, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    institutional_email: str | None = Field(default=None, max_length=254)
    email: str | None = Field(default=None, max_length=254)
    department: str = Field(..., min_length=1, max_length=100)
    semester: int = Field(..., ge=1, le=12)
    batch: str = Field(..., min_length=4, max_length=20)
    phone: str | None = None
    dob: str | None = None
    gender: str | None = None
    address: str | None = None
    course: str | None = None
    year: str | None = None
    division: str | None = None
    admission_year: str | None = None
    password: str | None = None
    authorize_account: bool = True
    assigned_teacher_ids: list[str] = Field(default_factory=list)
    status: StudentStatus = StudentStatus.ACTIVE

    @field_validator("erp_id")
    @classmethod
    def normalize_erp_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip().upper()
        return stripped if stripped else None

    @field_validator("institutional_email", "email")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().lower()

    @model_validator(mode="after")
    def sync_email_fields(self) -> "StudentCreateRequest":
        if not self.institutional_email and self.email:
            self.institutional_email = self.email
        elif self.institutional_email and not self.email:
            self.email = self.institutional_email
        return self


class StudentUpdateRequest(StudentSchemaBase):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    institutional_email: str | None = Field(default=None, max_length=254)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    semester: int | None = Field(default=None, ge=1, le=12)
    batch: str | None = Field(default=None, min_length=4, max_length=20)
    phone: str | None = None
    dob: str | None = None
    gender: str | None = None
    address: str | None = None
    course: str | None = None
    year: str | None = None
    division: str | None = None
    admission_year: str | None = None
    assigned_teacher_ids: list[str] | None = None
    status: StudentStatus | None = None

    @field_validator("institutional_email")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().lower()


class StudentResponse(StudentSchemaBase):
    id: str
    erp_id: str
    user_id: str | None = None
    name: str
    institutional_email: str | None = None
    department: str
    semester: int
    batch: str
    phone: str | None = None
    dob: str | None = None
    gender: str | None = None
    address: str | None = None
    course: str | None = None
    year: str | None = None
    division: str | None = None
    admission_year: str | None = None
    assigned_teacher_ids: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class StudentListResponse(StudentSchemaBase):
    items: list[StudentResponse]
    next_cursor: str | None = None
    total: int
    has_more: bool


class FacultyResponse(StudentSchemaBase):
    id: str
    name: str
    email: str
    department: str | None = None
    role: str
    assigned_student_count: int = 0


class AssignStudentsRequest(StudentSchemaBase):
    student_ids: list[str]


