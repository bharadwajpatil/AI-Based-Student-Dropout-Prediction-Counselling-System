from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.user import UserRole


class AuthSchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(AuthSchemaBase):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=10, max_length=128)
    phone: str | None = Field(default=None, max_length=20)
    phone_e164: str | None = Field(default=None, max_length=20)
    role: UserRole
    department: str | None = Field(default=None, max_length=100)
    erp_id: str | None = Field(default=None, max_length=50)


class LoginRequest(AuthSchemaBase):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class VerifyEmailRequest(AuthSchemaBase):
    token: str | None = Field(default=None, max_length=128)
    code: str | None = Field(default=None, min_length=6, max_length=6)


class ResendVerificationRequest(AuthSchemaBase):
    email: str = Field(..., min_length=3, max_length=254)


class ForgotPasswordRequest(AuthSchemaBase):
    identifier: str = Field(..., min_length=3, max_length=254)
    channel: str | None = Field(default="email", pattern="^(email|sms)$")


class ResetPasswordRequest(AuthSchemaBase):
    token: str | None = Field(default=None, max_length=128)
    identifier: str | None = Field(default=None, max_length=254)
    otp: str | None = Field(default=None, min_length=6, max_length=6)
    new_password: str = Field(..., min_length=10, max_length=128)


class VerifyPhoneRequest(AuthSchemaBase):
    phone: str = Field(..., max_length=20)
    otp: str = Field(..., min_length=6, max_length=6)


class UserProfileResponse(AuthSchemaBase):
    id: str
    name: str
    email: str
    phone_e164: str | None = None
    role: str
    status: str
    email_verified: bool
    phone_verified: bool


class TokenResponse(AuthSchemaBase):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse


class GenericMessageResponse(AuthSchemaBase):
    message: str
    details: dict[str, Any] | None = None
