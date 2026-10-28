from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SubjectSchemaBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SubjectCreateRequest(SubjectSchemaBase):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=50)
    department: str = Field(..., min_length=1, max_length=100)
    year: str = Field(..., min_length=1, max_length=50)
    semester: int = Field(..., ge=1, le=12)
    credits: int = Field(default=3, ge=1, le=10)
    academic_year: str = Field(default="2024-25", max_length=20)
    assigned_teacher_id: str | None = None


class SubjectUpdateRequest(SubjectSchemaBase):
    name: str | None = None
    code: str | None = None
    department: str | None = None
    year: str | None = None
    semester: int | None = None
    credits: int | None = None
    academic_year: str | None = None
    assigned_teacher_id: str | None = None


class AssignTeacherToSubjectRequest(SubjectSchemaBase):
    teacher_id: str = Field(..., min_length=1)


class BulkAssignSubjectsToTeacherRequest(SubjectSchemaBase):
    subject_ids: list[str] = Field(..., min_length=1)


class SubjectResponse(SubjectSchemaBase):
    id: str
    name: str
    code: str
    department: str
    year: str
    semester: int
    credits: int
    academic_year: str
    assigned_teacher_id: str | None = None
    assigned_teacher_name: str | None = None
    hod_id: str | None = None
    created_at: datetime
    updated_at: datetime
