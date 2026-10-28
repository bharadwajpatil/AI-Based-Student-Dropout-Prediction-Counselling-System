from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, field_validator

from backend.app.models.common import MongoBaseModel, PyObjectId


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    HOD = "hod"
    ADMIN = "admin"


class UserStatus(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


class UserInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    email_verified: bool = False
    phone_e164: str | None = Field(default=None, max_length=20)
    phone_verified: bool = False
    password_hash: str = Field(..., min_length=1)
    role: UserRole
    department: str | None = Field(default=None, max_length=100)
    employee_id: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=100)
    hod_id: PyObjectId | None = None
    created_by: PyObjectId | None = None
    status: UserStatus = UserStatus.PENDING_VERIFICATION
    failed_login_count: int = Field(default=0, ge=0)
    locked_until: datetime | None = None
    token_version: int = Field(default=0, ge=0)
    last_login_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("phone_e164")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v.startswith("+"):
            # Auto-prefix default country code if missing
            return f"+91{v}" if len(v) == 10 and v.isdigit() else f"+{v}"
        return v
