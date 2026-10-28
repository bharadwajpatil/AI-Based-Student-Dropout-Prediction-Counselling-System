import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_config_rejects_placeholder_jwt_secret():
    """App refuses to start if JWT_SECRET is the default insecure placeholder."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            JWT_SECRET="CHANGE_ME_TO_A_LONG_RANDOM_SECRET",
            MONGODB_URI="mongodb://localhost:27017",
        )
    assert "JWT_SECRET must be configured" in str(exc_info.value)


def test_config_rejects_short_jwt_secret():
    """App refuses to start if JWT_SECRET is too short (< 32 chars)."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            JWT_SECRET="short-secret",
            MONGODB_URI="mongodb://localhost:27017",
        )
    assert "at least 32 characters long" in str(exc_info.value)


def test_config_rejects_invalid_mongodb_uri():
    """App refuses to start if MONGODB_URI is not a mongodb connection scheme."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            JWT_SECRET="0123456789abcdef0123456789abcdef0123456789abcdef",
            MONGODB_URI="http://invalid-mongo-host",
        )
    assert "MONGODB_URI must be a valid MongoDB connection string" in str(exc_info.value)


def test_config_cors_origins():
    """Verifies that FRONTEND_URL is automatically added to CORS origins."""
    settings = Settings(
        JWT_SECRET="0123456789abcdef0123456789abcdef0123456789abcdef",
        MONGODB_URI="mongodb://localhost:27017",
        FRONTEND_URL="http://frontend.internal:3000",
    )
    origins = settings.get_cors_origins()
    assert "http://frontend.internal:3000" in origins
