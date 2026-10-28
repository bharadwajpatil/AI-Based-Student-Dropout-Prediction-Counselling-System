from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from backend.app.models.common import MongoBaseModel, PyObjectId


class TokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"
    VERIFY_PHONE = "verify_phone"
    RESET_SMS = "reset_sms"


class TokenChannel(StrEnum):
    EMAIL = "email"
    SMS = "sms"


class AuthTokenInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    user_id: PyObjectId
    purpose: TokenPurpose
    token_hash: str = Field(..., min_length=32, max_length=64)
    channel: TokenChannel
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=5, ge=1)
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RefreshTokenInDB(MongoBaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    user_id: PyObjectId
    token_hash: str = Field(..., min_length=32, max_length=64)
    family_id: str = Field(..., min_length=1)
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    ip: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
