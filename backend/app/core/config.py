from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root where .env resides
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "student-dropout-system"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "1.0.0"

    # Networking / CORS
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    ALLOWED_ORIGINS: list[str] = Field(default_factory=list)

    # MongoDB
    MONGODB_URI: str = Field(default="")
    MONGODB_DATABASE: str = "student_dropout_db"
    MONGODB_MAX_RETRIES: int = 5
    MONGODB_RETRY_DELAY: float = 1.0  # seconds

    # JWT Authentication
    JWT_SECRET: str = Field(default="")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email / SMTP
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USE_TLS: bool = False
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "no-reply@studentdropout.dev"
    SMTP_FROM_NAME: str = "Student Dropout System"

    # Gemini AI
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # SMS / Twilio
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_PHONE_NUMBER: str | None = None

    # Security & Policies
    SECURITY_HEADERS_ENABLED: bool = True
    HSTS_ENABLED: bool = False
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_GLOBAL_PER_MINUTE: int = 240
    RATE_LIMIT_AUTH_PER_MINUTE: int = 30
    MAX_REQUEST_SIZE_BYTES: int = 2 * 1024 * 1024  # 2MB
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15MB
    PASSWORD_RESET_EXPIRE_MINUTES: int = 15
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    SMS_OTP_EXPIRE_MINUTES: int = 10
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Risk Engine
    RISK_ENGINE_VERSION: str = "1.0.0"

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v or v.strip() == "CHANGE_ME_TO_A_LONG_RANDOM_SECRET":
            raise ValueError(
                "CRITICAL: JWT_SECRET must be configured with a secure random secret "
                "and cannot be empty or the placeholder value."
            )
        if len(v) < 32:
            raise ValueError(
                "CRITICAL: JWT_SECRET must be at least 32 characters long for security."
            )
        return v

    @field_validator("MONGODB_URI")
    @classmethod
    def validate_mongodb_uri(cls, v: str) -> str:
        if not v or not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError(
                "CRITICAL: MONGODB_URI must be a valid MongoDB connection string "
                "starting with mongodb:// or mongodb+srv://"
            )
        return v

    def get_cors_origins(self) -> list[str]:
        origins = list(self.ALLOWED_ORIGINS)
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins


# Instantiate global settings (refuses to start if required values are invalid/missing)
settings = Settings()
