import hashlib
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from backend.app.core.config import settings

# Precomputed dummy bcrypt hash for timing attack equalization (Scenario A9)
DUMMY_BCRYPT_HASH = "$2b$12$7kGllkb/n3F4DhaCAJz.rupV7SJeMm7RysFCS3ReZoqnTooR3NW6a"

# Top common passwords to reject
COMMON_PASSWORDS = {
    "password",
    "password123",
    "1234567890",
    "123456789",
    "qwertyuiop",
    "admin12345",
    "welcome123",
    "iloveyou123",
    "sunshine123",
    "football123",
    "princess123",
    "charlie1234",
    "student123",
    "teacher123",
}


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt with a random salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def dummy_verify_password(plain_password: str = "arbitrary_input") -> bool:
    """
    Performs a dummy bcrypt verify against a precomputed hash to prevent
    timing attacks when a queried user account does not exist (Scenario A9).
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), DUMMY_BCRYPT_HASH.encode("utf-8"))


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a token or OTP for safe database storage (Ground Rule 3)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_secure_token() -> str:
    """Generates a cryptographically strong 32-byte URL-safe random string."""
    return secrets.token_urlsafe(32)


def generate_numeric_otp(length: int = 6) -> str:
    """Generates a cryptographically strong numeric OTP."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def validate_password_strength(
    password: str,
    email: str,
    previous_hashes: list[str] | None = None,
) -> None:
    """
    Enforces password security policy:
    - Minimum length: 10 characters
    - Must not be in common passwords list
    - Must not contain the email username/local-part
    - Must not match any of the previous 3 passwords
    """
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long.")

    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Password is too common and easily guessable.")

    email_local_part = email.split("@")[0].lower()
    if len(email_local_part) >= 3 and email_local_part in password.lower():
        raise ValueError("Password cannot contain your email username.")

    if previous_hashes:
        for old_hash in previous_hashes[-3:]:
            if verify_password(password, old_hash):
                raise ValueError("New password cannot be one of your last 3 passwords.")


def create_access_token(
    subject: str,
    role: str,
    token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Creates a signed JWT access token containing sub, role, token_version, exp, and jti."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "token_version": token_version,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodes and validates a JWT access token signature and expiration."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
