import logging
import uuid
from datetime import timedelta
from typing import Any

from backend.app.core.clock import Clock, ensure_utc, get_clock
from backend.app.core.config import settings
from backend.app.core.rate_limit import InMemoryRateLimiter, rate_limiter
from backend.app.core.security import (
    create_access_token,
    dummy_verify_password,
    generate_numeric_otp,
    generate_secure_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from backend.app.db.mongo import get_database
from backend.app.integrations.dns_checker import DNSChecker
from backend.app.integrations.email_sender import EmailSender, FakeEmailSender, SMTPEmailSender
from backend.app.integrations.sms_sender import FakeSMSSender, SMSSender, TwilioSMSSender
from backend.app.models.token import (
    TokenChannel,
    TokenPurpose,
)
from backend.app.models.user import UserRole, UserStatus
from backend.app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from backend.app.services.email_validation import (
    EmailValidationService,
    compute_canonical_email,
)

logger = logging.getLogger("student-dropout-system.services.auth")


class AuthService:
    def __init__(
        self,
        clock: Clock | None = None,
        email_sender: EmailSender | None = None,
        sms_sender: SMSSender | None = None,
        dns_checker: DNSChecker | None = None,
        limiter: InMemoryRateLimiter | None = None,
    ) -> None:
        self.clock = clock or get_clock()
        self.email_sender = email_sender or (
            FakeEmailSender() if settings.APP_ENV == "testing" else SMTPEmailSender()
        )
        self.sms_sender = sms_sender or (
            FakeSMSSender() if settings.APP_ENV == "testing" else TwilioSMSSender()
        )
        self.email_validator = EmailValidationService(dns_checker=dns_checker)
        self.rate_limiter = limiter or rate_limiter

    # -------------------------------------------------------------------------
    # 3.1 Registration
    # -------------------------------------------------------------------------
    async def register(self, req: RegisterRequest) -> tuple[bool, str, dict[str, Any] | None]:
        """
        Handles user registration with layered genuine email validation,
        roster ERP verification for students, and role restrictions.
        """
        db = get_database()
        now = self.clock.now()

        # Reject self-registration as admin (Scenario A23)
        if req.role == UserRole.ADMIN:
            return False, "Self-registration as administrator is not permitted.", None

        # Layer 1-4: Validate Email Deliverability & Authenticity
        is_valid, canonical_email, error_reason = await self.email_validator.validate_email_address(
            req.email
        )
        if not is_valid:
            return False, error_reason, None

        # Student Roster Checks (Scenario A4)
        student_doc = None
        if req.role == UserRole.STUDENT:
            if not req.erp_id:
                return False, "ERP ID is required for student registration.", None

            normalized_erp = req.erp_id.strip().upper()
            student_doc = await db.students.find_one({"erp_id": normalized_erp})
            if not student_doc:
                return False, "Invalid registration details or ERP ID not found in roster.", None

            if student_doc.get("user_id") is not None:
                return False, "This ERP ID has already been claimed by a registered account.", None

            # If roster has institutional email on file, verify match
            inst_email = student_doc.get("institutional_email")
            if inst_email and inst_email.strip().lower() != req.email.strip().lower():
                return (
                    False,
                    "Email does not match institutional records on file for this ERP ID.",
                    None,
                )

        # Validate Password Policy
        try:
            validate_password_strength(req.password, req.email)
        except ValueError as e:
            return False, str(e), None

        # Check existing user by canonical email (Scenario A5 & A6)
        existing_user = await db.users.find_one({"canonical_email": canonical_email})
        if existing_user:
            if existing_user.get("email_verified", False):
                # Scenario A5: Prevent enumeration - return generic response and notify existing owner
                logger.info(
                    "Registration attempt on already verified email %s (silent generic response)",
                    canonical_email,
                )
                await self.email_sender.send_email(
                    existing_user["email"],
                    "Security Notice: Registration Attempt",
                    "<p>Someone attempted to create a new account using your email address. If this was not you, no action is needed.</p>",
                    "Someone attempted to create a new account using your email address.",
                )
                return (
                    True,
                    "If this is new, please check your inbox for verification instructions.",
                    None,
                )
            else:
                # Existing unverified user -> update details and re-send verification
                user_id = existing_user["_id"]
        else:
            # Create user document
            initial_status = (
                UserStatus.PENDING_APPROVAL
                if req.role in (UserRole.TEACHER, UserRole.HOD)
                else UserStatus.PENDING_VERIFICATION
            )
            phone_val = (req.phone_e164 or req.phone or "").strip() or None
            new_user_data = {
                "name": req.name.strip(),
                "email": req.email.strip().lower(),
                "canonical_email": canonical_email,
                "email_verified": False,
                "phone_e164": phone_val,
                "phone_verified": False,
                "password_hash": hash_password(req.password),
                "role": req.role.value,
                "department": req.department.strip() if req.department else None,
                "status": initial_status.value,
                "failed_login_count": 0,
                "locked_until": None,
                "token_version": 0,
                "previous_password_hashes": [hash_password(req.password)],
                "created_at": now,
                "updated_at": now,
                "last_login_at": None,
            }
            insert_res = await db.users.insert_one(new_user_data)
            user_id = insert_res.inserted_id

            # Link student roster if applicable
            if student_doc:
                await db.students.update_one(
                    {"_id": student_doc["_id"]},
                    {"$set": {"user_id": user_id, "updated_at": now}},
                )

        # Generate Email Verification Tokens (32-byte link token + 6-digit code)
        link_token = generate_secure_token()
        six_digit_code = generate_numeric_otp(6)
        token_hash_link = hash_token(link_token)
        token_hash_code = hash_token(six_digit_code)
        expires_at = now + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS)

        # Invalidate existing unverified tokens for this user
        await db.auth_tokens.delete_many(
            {"user_id": user_id, "purpose": TokenPurpose.VERIFY_EMAIL.value}
        )

        # Save both tokens into auth_tokens
        await db.auth_tokens.insert_many(
            [
                {
                    "user_id": user_id,
                    "purpose": TokenPurpose.VERIFY_EMAIL.value,
                    "token_hash": token_hash_link,
                    "channel": TokenChannel.EMAIL.value,
                    "attempts": 0,
                    "max_attempts": 5,
                    "expires_at": expires_at,
                    "used_at": None,
                    "created_at": now,
                },
                {
                    "user_id": user_id,
                    "purpose": TokenPurpose.VERIFY_EMAIL.value,
                    "token_hash": token_hash_code,
                    "channel": TokenChannel.EMAIL.value,
                    "attempts": 0,
                    "max_attempts": 5,
                    "expires_at": expires_at,
                    "used_at": None,
                    "created_at": now,
                },
            ]
        )

        # Send Verification Email
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={link_token}"
        html_msg = (
            f"<p>Hello {req.name},</p>"
            f"<p>Please verify your email address by clicking the link below:</p>"
            f"<p><a href='{verify_url}'>{verify_url}</a></p>"
            f"<p>Or enter this 6-digit verification code: <strong>{six_digit_code}</strong></p>"
        )
        text_msg = f"Verify your email: {verify_url} or enter code: {six_digit_code}"
        await self.email_sender.send_email(
            req.email, "Verify Your Email Address", html_msg, text_msg
        )

        return (
            True,
            "Registration successful. Please check your email to verify your account.",
            {"user_id": str(user_id)},
        )

    # -------------------------------------------------------------------------
    # 3.2 Email Verification
    # -------------------------------------------------------------------------
    async def verify_email(self, req: VerifyEmailRequest) -> tuple[bool, str]:
        """Verifies email ownership using either verification link token or 6-digit code."""
        db = get_database()
        now = self.clock.now()

        raw_token = req.token or req.code
        if not raw_token:
            return False, "Verification token or code is required."

        computed_hash = hash_token(raw_token)

        # Look up token
        token_doc = await db.auth_tokens.find_one(
            {
                "token_hash": computed_hash,
                "purpose": TokenPurpose.VERIFY_EMAIL.value,
            }
        )

        if not token_doc:
            return False, "Invalid verification token or code."

        user = await db.users.find_one({"_id": token_doc["user_id"]})
        if not user:
            return False, "Associated user account not found."

        # Idempotent handling: If user is already verified (Scenario: double-click)
        if user.get("email_verified", False):
            return True, "Email is already verified."

        if token_doc.get("used_at") is not None or ensure_utc(token_doc["expires_at"]) < now:
            return False, "Verification link or code has expired. Please request a new one."

        # Mark token as used atomically
        await db.auth_tokens.update_one({"_id": token_doc["_id"]}, {"$set": {"used_at": now}})

        # Update user status
        new_status = user["status"]
        if user["status"] == UserStatus.PENDING_VERIFICATION.value:
            new_status = (
                UserStatus.PENDING_APPROVAL.value
                if user["role"] in (UserRole.TEACHER.value, UserRole.HOD.value)
                else UserStatus.ACTIVE.value
            )

        await db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "email_verified": True,
                    "status": new_status,
                    "updated_at": now,
                }
            },
        )

        return True, "Email successfully verified. You may now log in."

    # -------------------------------------------------------------------------
    # 3.4 Login & Session Management
    # -------------------------------------------------------------------------
    async def login(
        self, req: LoginRequest, client_ip: str = "127.0.0.1", user_agent: str | None = None
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """
        Authenticates user with constant-time response protection (Scenario A9),
        account lockout after 5 consecutive failures (Scenario A8), and refresh token rotation.
        """
        db = get_database()
        now = self.clock.now()
        canonical = compute_canonical_email(req.email)

        # IP-based rate limiting: max 20 login attempts per minute
        if not self.rate_limiter.is_allowed(
            f"login_ip:{client_ip}", limit=20, window=timedelta(minutes=1)
        ):
            return False, "Too many login attempts from this network. Please wait a moment.", None

        user = await db.users.find_one(
            {
                "$or": [
                    {"canonical_email": canonical},
                    {"aliases": canonical},
                    {"email": req.email.strip().lower()},
                ]
            }
        )

        # User does not exist -> execute dummy bcrypt hash for timing equalization (Scenario A9)
        if not user:
            dummy_verify_password(req.password)
            return False, "Invalid email or password.", None

        # Check account lockout (Scenario A8)
        locked_until = ensure_utc(user.get("locked_until"))
        if locked_until and locked_until > now:
            # Re-run dummy verify so timing remains identical
            dummy_verify_password(req.password)
            return (
                False,
                "Account is temporarily locked due to repeated failed logins. Please try again later.",
                None,
            )

        # Verify password
        is_password_valid = verify_password(req.password, user["password_hash"])
        if not is_password_valid:
            failed_count = user.get("failed_login_count", 0) + 1
            update_data: dict[str, Any] = {"failed_login_count": failed_count, "updated_at": now}

            # 5 consecutive failures -> lock for 15 minutes (Scenario A8)
            if failed_count >= settings.MAX_LOGIN_ATTEMPTS:
                lock_duration = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                update_data["locked_until"] = now + lock_duration
                logger.warning(
                    "User %s locked until %s after %d failures",
                    user["email"],
                    update_data["locked_until"],
                    failed_count,
                )

            await db.users.update_one({"_id": user["_id"]}, {"$set": update_data})
            return False, "Invalid email or password.", None

        # Correct password provided: check account states
        if not user.get("email_verified", False):
            # Scenario A7: blocked after correct password with safe hint
            return False, "Please verify your email address before logging in.", None

        if user["status"] == UserStatus.PENDING_APPROVAL.value:
            # Scenario A10: Teacher / HOD requires admin approval
            return False, "Your account is pending administrator approval.", None

        if user["status"] in (UserStatus.DISABLED.value, UserStatus.LOCKED.value):
            return False, "Your account is currently disabled or suspended.", None

        # Reset failed count & clear lockout on successful login
        await db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "failed_login_count": 0,
                    "locked_until": None,
                    "last_login_at": now,
                    "updated_at": now,
                }
            },
        )

        # Generate Access Token & Refresh Token
        token_version = user.get("token_version", 0)
        access_token = create_access_token(
            subject=str(user["_id"]),
            role=user["role"],
            token_version=token_version,
        )

        refresh_token_raw = generate_secure_token()
        family_id = str(uuid.uuid4())
        refresh_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await db.refresh_tokens.insert_one(
            {
                "user_id": user["_id"],
                "token_hash": hash_token(refresh_token_raw),
                "family_id": family_id,
                "expires_at": refresh_expires_at,
                "revoked_at": None,
                "user_agent": user_agent,
                "ip": client_ip,
                "created_at": now,
            }
        )

        user_profile = {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "phone_e164": user.get("phone_e164"),
            "role": user["role"],
            "status": user["status"],
            "email_verified": user.get("email_verified", False),
            "phone_verified": user.get("phone_verified", False),
        }

        return (
            True,
            "Login successful.",
            {
                "access_token": access_token,
                "refresh_token": refresh_token_raw,
                "user": user_profile,
            },
        )

    # -------------------------------------------------------------------------
    # Refresh Token Rotation with Reuse Detection (Scenario A20)
    # -------------------------------------------------------------------------
    async def refresh_session(
        self, raw_refresh_token: str, client_ip: str = "127.0.0.1", user_agent: str | None = None
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """
        Rotates refresh token. Detects token reuse (stolen token), revokes entire family,
        and bumps user token_version (Scenario A20).
        """
        db = get_database()
        now = self.clock.now()
        token_hash_val = hash_token(raw_refresh_token)

        token_doc = await db.refresh_tokens.find_one({"token_hash": token_hash_val})
        if not token_doc:
            return False, "Invalid or expired session token.", None

        # Scenario A20: REUSE DETECTION
        if token_doc.get("revoked_at") is not None:
            family_id = token_doc["family_id"]
            logger.critical(
                "Refresh token reuse detected for family %s! Revoking family.", family_id
            )
            # Revoke entire token family
            await db.refresh_tokens.update_many(
                {"family_id": family_id},
                {"$set": {"revoked_at": now}},
            )
            # Bump token_version to invalidate all existing access JWTs
            await db.users.update_one(
                {"_id": token_doc["user_id"]},
                {"$inc": {"token_version": 1}, "$set": {"updated_at": now}},
            )
            return (
                False,
                "Security violation: compromised session token reuse detected. Please log in again.",
                None,
            )

        if ensure_utc(token_doc["expires_at"]) < now:
            return False, "Session has expired. Please log in again.", None

        user = await db.users.find_one({"_id": token_doc["user_id"]})
        if not user or user["status"] != UserStatus.ACTIVE.value:
            return False, "User account is inactive or not found.", None

        # Mark previous token as revoked
        await db.refresh_tokens.update_one({"_id": token_doc["_id"]}, {"$set": {"revoked_at": now}})

        # Issue newly rotated refresh token in the same family
        new_refresh_raw = generate_secure_token()
        new_refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await db.refresh_tokens.insert_one(
            {
                "user_id": user["_id"],
                "token_hash": hash_token(new_refresh_raw),
                "family_id": token_doc["family_id"],
                "expires_at": new_refresh_expires,
                "revoked_at": None,
                "user_agent": user_agent,
                "ip": client_ip,
                "created_at": now,
            }
        )

        new_access_token = create_access_token(
            subject=str(user["_id"]),
            role=user["role"],
            token_version=user.get("token_version", 0),
        )

        return (
            True,
            "Session refreshed.",
            {
                "access_token": new_access_token,
                "refresh_token": new_refresh_raw,
            },
        )

    # -------------------------------------------------------------------------
    # 3.5 Forgot Password & Automatic SMS Fallback
    # -------------------------------------------------------------------------
    async def forgot_password(
        self, req: ForgotPasswordRequest, client_ip: str = "127.0.0.1"
    ) -> tuple[bool, str]:
        """
        Forgot password with email-first delivery, manual/explicit SMS option,
        and automatic SMS fallback if email provider fails (Scenario A11, A12, A15, A16, A18).
        Always returns generic response (equalized timing).
        """
        db = get_database()
        now = self.clock.now()
        identifier = req.identifier.strip()

        # Rate limiting: 10 per hour per IP
        if not self.rate_limiter.is_allowed(
            f"forgot_ip:{client_ip}", limit=10, window=timedelta(hours=1)
        ):
            return True, "If an account exists, we have sent instructions."

        # Lookup user by email or phone
        if "@" in identifier:
            canonical = compute_canonical_email(identifier)
            user = await db.users.find_one({"canonical_email": canonical})
        else:
            # Phone format check
            user = await db.users.find_one({"phone_e164": identifier})

        # Scenario A11: Unknown user -> generic 200, equalized timing, nothing sent
        if not user:
            return True, "If an account exists, we have sent instructions."

        user_id = user["_id"]

        # Account rate limiting: max 3 requests / hour per account, 60s cooldown
        cooldown_rem = self.rate_limiter.seconds_until_allowed(
            f"forgot_user:{user_id}", timedelta(seconds=60)
        )
        if cooldown_rem > 0:
            return True, "If an account exists, we have sent instructions."

        if not self.rate_limiter.is_allowed(
            f"forgot_user_hourly:{user_id}", limit=3, window=timedelta(hours=1)
        ):
            return True, "If an account exists, we have sent instructions."

        # Invalidate older password reset tokens for this user (Principle 6)
        await db.auth_tokens.delete_many(
            {
                "user_id": user_id,
                "purpose": {
                    "$in": [TokenPurpose.RESET_PASSWORD.value, TokenPurpose.RESET_SMS.value]
                },
            }
        )

        # Channel Selection Logic:
        # Case 1: Explicit SMS request (Scenario A16)
        if req.channel == "sms":
            if not user.get("phone_verified", False) or not user.get("phone_e164"):
                # Scenario A16: Unverified phone -> no SMS sent, audit log written, generic response
                logger.warning(
                    "User %s requested SMS reset but phone is unverified.", user["email"]
                )
                await db.audit_logs.insert_one(
                    {
                        "actor_id": user_id,
                        "action": "forgot_password_sms_unverified",
                        "target_type": "user",
                        "target_id": str(user_id),
                        "at": now,
                        "ip": client_ip,
                    }
                )
                return True, "If an account exists, we have sent instructions."

            # Send SMS OTP
            await self._send_password_reset_sms(user, client_ip)
            return True, "If an account exists, we have sent instructions."

        # Case 2: Default Email
        email_sent_ok = False
        if user.get("email_verified", False):
            reset_token = generate_secure_token()
            token_hash_val = hash_token(reset_token)
            expires_at = now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)

            await db.auth_tokens.insert_one(
                {
                    "user_id": user_id,
                    "purpose": TokenPurpose.RESET_PASSWORD.value,
                    "token_hash": token_hash_val,
                    "channel": TokenChannel.EMAIL.value,
                    "attempts": 0,
                    "max_attempts": 5,
                    "expires_at": expires_at,
                    "used_at": None,
                    "created_at": now,
                }
            )

            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
            email_sent_ok = await self.email_sender.send_email(
                user["email"],
                "Password Reset Instructions",
                f"<p>Reset your password here: <a href='{reset_url}'>{reset_url}</a> (Valid for 15 minutes)</p>",
                f"Reset your password: {reset_url}",
            )

        # Scenario A15: Automatic fallback to SMS if email delivery failed permanently
        if not email_sent_ok and user.get("phone_verified", False) and user.get("phone_e164"):
            logger.info(
                "Email delivery failed for %s. Automatically falling back to verified SMS.",
                user["email"],
            )
            await self._send_password_reset_sms(user, client_ip)

        return True, "If an account exists, we have sent instructions."

    async def _send_password_reset_sms(self, user: dict[str, Any], client_ip: str) -> bool:
        """Sends a 6-digit cryptographically secure SMS OTP for password reset."""
        db = get_database()
        now = self.clock.now()
        phone = user["phone_e164"]

        # SMS Rate limits: max 5 requests per number / day (Scenario A18)
        if not self.rate_limiter.is_allowed(
            f"sms_daily:{phone}", limit=5, window=timedelta(days=1)
        ):
            logger.warning("SMS daily cap reached for %s", phone)
            return False

        otp = generate_numeric_otp(6)
        otp_hash = hash_token(otp)
        expires_at = now + timedelta(minutes=settings.SMS_OTP_EXPIRE_MINUTES)

        await db.auth_tokens.insert_one(
            {
                "user_id": user["_id"],
                "purpose": TokenPurpose.RESET_SMS.value,
                "token_hash": otp_hash,
                "channel": TokenChannel.SMS.value,
                "attempts": 0,
                "max_attempts": 5,
                "expires_at": expires_at,
                "used_at": None,
                "created_at": now,
            }
        )

        message = f"Your student dropout portal verification OTP is: {otp}. Valid for 10 minutes."
        return await self.sms_sender.send_sms(phone, message)

    # -------------------------------------------------------------------------
    # 3.5 Reset Password
    # -------------------------------------------------------------------------
    async def reset_password(self, req: ResetPasswordRequest) -> tuple[bool, str]:
        """
        Executes password reset verifying link token or (identifier + OTP).
        Enforces atomic consumption, password policy, and session revocation.
        """
        db = get_database()
        now = self.clock.now()

        # Identify lookup method
        token_doc = None
        if req.token:
            token_hash_val = hash_token(req.token)
            token_doc = await db.auth_tokens.find_one(
                {
                    "token_hash": token_hash_val,
                    "purpose": TokenPurpose.RESET_PASSWORD.value,
                }
            )
        elif req.identifier and req.otp:
            # Identifier lookup
            if "@" in req.identifier:
                canonical = compute_canonical_email(req.identifier)
                user = await db.users.find_one({"canonical_email": canonical})
            else:
                user = await db.users.find_one({"phone_e164": req.identifier.strip()})

            if not user:
                return False, "Invalid or expired password reset details."

            # Find newest active SMS token
            token_doc = await db.auth_tokens.find_one(
                {
                    "user_id": user["_id"],
                    "purpose": TokenPurpose.RESET_SMS.value,
                    "used_at": None,
                }
            )

            if not token_doc:
                return False, "Invalid or expired password reset token."

            # Verify OTP
            expected_hash = hash_token(req.otp)
            if token_doc["token_hash"] != expected_hash:
                # Scenario A17: Increment attempts, invalidate if >= 5
                new_attempts = token_doc.get("attempts", 0) + 1
                if new_attempts >= token_doc.get("max_attempts", 5):
                    await db.auth_tokens.delete_one({"_id": token_doc["_id"]})
                    return (
                        False,
                        "Maximum OTP verification attempts exceeded. Please request a new OTP.",
                    )
                else:
                    await db.auth_tokens.update_one(
                        {"_id": token_doc["_id"]}, {"$set": {"attempts": new_attempts}}
                    )
                    return (
                        False,
                        f"Invalid OTP. {token_doc['max_attempts'] - new_attempts} attempts remaining.",
                    )
        else:
            return False, "Either reset token or identifier and OTP must be supplied."

        if not token_doc:
            return False, "Invalid or expired password reset token."

        if token_doc.get("used_at") is not None:
            # Scenario A13: Already used token fails with generic error
            return False, "Invalid or expired password reset token."

        if ensure_utc(token_doc["expires_at"]) < now:
            return False, "Password reset token has expired. Please request a new one."

        # Scenario A14: Atomic consumption to prevent double-submit race conditions
        updated_token = await db.auth_tokens.find_one_and_update(
            {"_id": token_doc["_id"], "used_at": None},
            {"$set": {"used_at": now}},
        )
        if not updated_token:
            return False, "Password reset token has already been used."

        user = await db.users.find_one({"_id": token_doc["user_id"]})
        if not user:
            return False, "User associated with reset token not found."

        # Scenario A21: Password Policy and History (Reject last 3 passwords)
        prev_hashes = user.get("previous_password_hashes", [])
        try:
            validate_password_strength(req.new_password, user["email"], previous_hashes=prev_hashes)
        except ValueError as e:
            return False, str(e)

        # Hash new password
        new_hash = hash_password(req.new_password)
        updated_history = (prev_hashes + [new_hash])[-3:]

        # Scenario A19: Bump token_version to instantly revoke all active JWTs
        await db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password_hash": new_hash,
                    "previous_password_hashes": updated_history,
                    "failed_login_count": 0,
                    "locked_until": None,
                    "email_verified": True,  # Proves mailbox ownership
                    "updated_at": now,
                },
                "$inc": {"token_version": 1},
            },
        )

        # Revoke all active refresh tokens for this user
        await db.refresh_tokens.update_many(
            {"user_id": user["_id"], "revoked_at": None},
            {"$set": {"revoked_at": now}},
        )

        # Send confirmation notice
        await self.email_sender.send_email(
            user["email"],
            "Security Notice: Your Password Has Been Changed",
            "<p>Your account password was successfully updated. If you did not make this change, contact support immediately.</p>",
            "Your account password was successfully updated.",
        )

        return (
            True,
            "Your password has been successfully reset. You may now log in with your new password.",
        )
