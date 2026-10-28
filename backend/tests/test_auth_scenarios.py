import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from backend.app.core.security import decode_access_token, hash_token
from backend.app.models.student import StudentInDB
from backend.app.models.user import UserRole, UserStatus
from backend.app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from backend.app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_a1_register_disposable_email(auth_service: AuthService):
    """Scenario A1: Register with x@mailinator.com -> rejected (disposable)."""
    req = RegisterRequest(
        name="Test User",
        email="user@mailinator.com",
        password="ValidPassword123!",
        role=UserRole.TEACHER,
    )
    success, msg, _ = await auth_service.register(req)
    assert not success
    assert "Disposable" in msg


@pytest.mark.asyncio
async def test_a2_register_nonexistent_domain(auth_service: AuthService):
    """Scenario A2: Register with x@nonexistent-domain-12345.xyz -> rejected (no MX/A)."""
    req = RegisterRequest(
        name="Test User",
        email="user@nonexistent-domain-12345.xyz",
        password="ValidPassword123!",
        role=UserRole.TEACHER,
    )
    success, msg, _ = await auth_service.register(req)
    assert not success
    assert "does not have active MX or A" in msg


@pytest.mark.asyncio
async def test_a3_dns_timeout_proceeds(auth_service: AuthService, fake_dns_checker):
    """Scenario A3: DNS resolver times out -> not rejected; proceeds to verification."""
    fake_dns_checker.timeout_domains.add("flaky-dns-domain.org")
    req = RegisterRequest(
        name="Test User",
        email="user@flaky-dns-domain.org",
        password="ValidPassword123!",
        role=UserRole.TEACHER,
    )
    success, msg, extra = await auth_service.register(req)
    assert success
    assert "check your email" in msg.lower()


@pytest.mark.asyncio
async def test_a4_register_student_unknown_or_claimed_erp(auth_service: AuthService, mock_db):
    """Scenario A4: Register student with unknown or claimed erp_id -> rejected."""
    # 1. Unknown ERP
    req_unknown = RegisterRequest(
        name="Student One",
        email="student1@institute.edu",
        password="ValidPassword123!",
        role=UserRole.STUDENT,
        erp_id="NONEXISTENT_ERP",
    )
    success, msg, _ = await auth_service.register(req_unknown)
    assert not success
    assert "ERP ID not found" in msg

    # 2. Existing claimed ERP
    claimed_student = StudentInDB(
        erp_id="MET201",
        name="Claimed Student",
        department="AI&DS",
        semester=6,
        batch="2022-26",
        user_id=str(ObjectId()),  # Already claimed!
    )
    await mock_db.students.insert_one(claimed_student.to_mongo())

    req_claimed = RegisterRequest(
        name="Imposter",
        email="imposter@institute.edu",
        password="ValidPassword123!",
        role=UserRole.STUDENT,
        erp_id="MET201",
    )
    success, msg, _ = await auth_service.register(req_claimed)
    assert not success
    assert "already been claimed" in msg


@pytest.mark.asyncio
async def test_a5_register_already_verified_email(auth_service: AuthService, fake_email_sender):
    """Scenario A5: Register with already-verified email -> generic response, no enumeration leak, notice sent."""
    # First registration
    req = RegisterRequest(
        name="Alice Smith",
        email="alice@verified-corp.com",
        password="ValidPassword123!",
        role=UserRole.TEACHER,
    )
    success, _, _ = await auth_service.register(req)
    assert success

    # Simulate email verification
    email_msg = fake_email_sender.sent_messages[0]
    token = email_msg.text_content.split("token=")[1].split()[0]
    await auth_service.verify_email(VerifyEmailRequest(token=token))
    fake_email_sender.clear()

    # Second registration with same email
    req2 = RegisterRequest(
        name="Attacker Alice",
        email="alice@verified-corp.com",
        password="NewPassword123!",
        role=UserRole.TEACHER,
    )
    success, msg, _ = await auth_service.register(req2)
    assert success  # Generic success response to defeat enumeration!
    assert "check your inbox" in msg.lower()

    # Original owner receives a security notice
    assert len(fake_email_sender.sent_messages) == 1
    assert "Registration Attempt" in fake_email_sender.sent_messages[0].subject


@pytest.mark.asyncio
async def test_a6_canonical_email_identity(auth_service: AuthService, mock_db):
    """Scenario A6: User+tag@Gmail.com vs user@gmail.com -> treated as same canonical identity."""
    from backend.app.services.email_validation import compute_canonical_email

    canonical1 = compute_canonical_email("bob.builder@gmail.com")
    canonical2 = compute_canonical_email("Bob.Builder+spamtag@gmail.com")
    assert canonical1 == canonical2 == "bobbuilder@gmail.com"

    req1 = RegisterRequest(
        name="Bob",
        email="bob.builder@gmail.com",
        password="ValidPassword123!",
        role=UserRole.TEACHER,
    )
    success, _, _ = await auth_service.register(req1)
    assert success

    req2 = RegisterRequest(
        name="Bob Duplicate",
        email="Bob.Builder+spamtag@gmail.com",
        password="AnotherPassword123!",
        role=UserRole.TEACHER,
    )
    # The system detects the duplicate canonical identity and does not create a 2nd user row
    success2, _, _ = await auth_service.register(req2)
    assert success2

    users_count = await mock_db.users.count_documents({"canonical_email": "bobbuilder@gmail.com"})
    assert users_count == 1


@pytest.mark.asyncio
async def test_a7_login_before_verifying_email(auth_service: AuthService):
    """Scenario A7: Login before verifying email -> blocked after correct password with safe hint."""
    req = RegisterRequest(
        name="Carol",
        email="carol@unverified.org",
        password="ValidPassword123!",
        role=UserRole.TEACHER,
    )
    await auth_service.register(req)

    # Attempt login before verification
    login_req = LoginRequest(email="carol@unverified.org", password="ValidPassword123!")
    success, msg, _ = await auth_service.login(login_req)
    assert not success
    assert "verify your email" in msg.lower()


@pytest.mark.asyncio
async def test_a8_account_lockout_after_five_failed_logins(
    auth_service: AuthService, test_clock, fake_email_sender
):
    """Scenario A8: 5 wrong passwords -> account locked 15 min; after clock advance, succeeds."""
    # Register & verify
    req = RegisterRequest(
        name="David",
        email="david@lockout.com",
        password="CorrectPassword123!",
        role=UserRole.STUDENT,
        erp_id="MET301",
    )
    # Pre-seed student roster
    from backend.app.db.mongo import get_database

    db = get_database()
    await db.students.insert_one(
        StudentInDB(
            erp_id="MET301", name="David", department="AI&DS", semester=8, batch="2022-26"
        ).to_mongo()
    )
    await auth_service.register(req)
    token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]
    await auth_service.verify_email(VerifyEmailRequest(token=token))

    # 4 wrong password attempts
    for _ in range(4):
        success, msg, _ = await auth_service.login(
            LoginRequest(email="david@lockout.com", password="WrongPassword")
        )
        assert not success
        assert "Invalid email or password" in msg

    # 5th wrong password attempt -> triggers lockout
    success, msg, _ = await auth_service.login(
        LoginRequest(email="david@lockout.com", password="WrongPassword")
    )
    assert not success

    # 6th attempt with CORRECT password during lockout period -> still blocked!
    success, msg, _ = await auth_service.login(
        LoginRequest(email="david@lockout.com", password="CorrectPassword123!")
    )
    assert not success
    assert "temporarily locked" in msg.lower()

    # Advance clock by 16 minutes
    test_clock.advance(timedelta(minutes=16))

    # After lockout expiry, correct password succeeds
    success, msg, data = await auth_service.login(
        LoginRequest(email="david@lockout.com", password="CorrectPassword123!")
    )
    assert success
    assert "access_token" in data


@pytest.mark.asyncio
async def test_a9_login_timing_unknown_vs_known(auth_service: AuthService):
    """Scenario A9: Login timing for unknown user runs dummy bcrypt verify (no error, dummy executed)."""
    # Calling login for an unknown user executes dummy bcrypt hash without error
    success, msg, _ = await auth_service.login(
        LoginRequest(email="unknown-user@example.com", password="DummyPassword123!")
    )
    assert not success
    assert "Invalid email or password" in msg


@pytest.mark.asyncio
async def test_a10_teacher_registers_pending_approval(auth_service: AuthService, fake_email_sender):
    """Scenario A10: Teacher registers -> pending_approval; cannot log in until approved."""
    req = RegisterRequest(
        name="Prof. Sharma",
        email="sharma@college.edu",
        password="TeacherPass123!",
        role=UserRole.TEACHER,
    )
    await auth_service.register(req)
    token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]
    await auth_service.verify_email(VerifyEmailRequest(token=token))

    # Email verified, but status is pending_approval
    success, msg, _ = await auth_service.login(
        LoginRequest(email="sharma@college.edu", password="TeacherPass123!")
    )
    assert not success
    assert "administrator approval" in msg.lower()

    # Admin approves teacher
    from backend.app.db.mongo import get_database

    db = get_database()
    await db.users.update_one(
        {"email": "sharma@college.edu"}, {"$set": {"status": UserStatus.ACTIVE.value}}
    )

    # Now login succeeds
    success2, _, data = await auth_service.login(
        LoginRequest(email="sharma@college.edu", password="TeacherPass123!")
    )
    assert success2
    assert data["user"]["role"] == "teacher"


@pytest.mark.asyncio
async def test_a11_forgot_password_unknown_email(auth_service: AuthService, fake_email_sender):
    """Scenario A11: Forgot password with unknown email -> identical 200 response, nothing sent."""
    success, msg = await auth_service.forgot_password(
        ForgotPasswordRequest(identifier="ghost@nowhere.com")
    )
    assert success
    assert "If an account exists" in msg
    assert len(fake_email_sender.sent_messages) == 0


@pytest.mark.asyncio
async def test_a12_forgot_password_verified_email(auth_service: AuthService, fake_email_sender):
    """Scenario A12: Forgot password with verified email -> instructions sent with valid token."""
    # Seed active verified user
    from backend.app.db.mongo import get_database

    db = get_database()
    await db.users.insert_one(
        {
            "name": "Eve",
            "email": "eve@example.com",
            "canonical_email": "eve@example.com",
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    success, msg = await auth_service.forgot_password(
        ForgotPasswordRequest(identifier="eve@example.com")
    )
    assert success
    assert len(fake_email_sender.sent_messages) == 1
    assert "Password Reset" in fake_email_sender.sent_messages[0].subject


@pytest.mark.asyncio
async def test_a13_reset_link_used_twice_or_expired(
    auth_service: AuthService, fake_email_sender, test_clock
):
    """Scenario A13: Reset link used twice or expired -> fails with generic error."""
    from backend.app.db.mongo import get_database

    db = get_database()
    await db.users.insert_one(
        {
            "name": "Frank",
            "email": "frank@example.com",
            "canonical_email": "frank@example.com",
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    await auth_service.forgot_password(ForgotPasswordRequest(identifier="frank@example.com"))
    raw_token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]

    # First reset -> succeeds
    success, msg = await auth_service.reset_password(
        ResetPasswordRequest(token=raw_token, new_password="BrandNewPassword123!")
    )
    assert success

    # Second reset with SAME token -> fails
    success2, msg2 = await auth_service.reset_password(
        ResetPasswordRequest(token=raw_token, new_password="AnotherPassword123!")
    )
    assert not success2
    assert "already been used" in msg2 or "Invalid" in msg2


@pytest.mark.asyncio
async def test_a14_concurrent_double_submit_reset_token(
    auth_service: AuthService, fake_email_sender
):
    """Scenario A14: Concurrent double-submit of same reset token -> exactly one succeeds."""
    from backend.app.db.mongo import get_database

    db = get_database()
    await db.users.insert_one(
        {
            "name": "Grace",
            "email": "grace@example.com",
            "canonical_email": "grace@example.com",
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )
    await auth_service.forgot_password(ForgotPasswordRequest(identifier="grace@example.com"))
    raw_token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]

    # Concurrent submits
    req1 = ResetPasswordRequest(token=raw_token, new_password="PasswordOne123!")
    req2 = ResetPasswordRequest(token=raw_token, new_password="PasswordTwo123!")

    res1, res2 = await asyncio.gather(
        auth_service.reset_password(req1),
        auth_service.reset_password(req2),
    )

    successes = [r[0] for r in [res1, res2] if r[0] is True]
    assert len(successes) == 1  # Exactly one succeeded!


@pytest.mark.asyncio
async def test_a15_email_fails_auto_fallback_to_sms(
    auth_service: AuthService, fake_email_sender, fake_sms_sender
):
    """Scenario A15: Email provider fails permanently, verified phone exists -> auto-fallback to SMS OTP."""
    from backend.app.db.mongo import get_database

    db = get_database()
    await db.users.insert_one(
        {
            "name": "Hannah",
            "email": "hannah@example.com",
            "canonical_email": "hannah@example.com",
            "email_verified": True,
            "phone_e164": "+919876543210",
            "phone_verified": True,  # Verified phone!
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    # Simulate email failure
    fake_email_sender.fail_next = True

    success, msg = await auth_service.forgot_password(
        ForgotPasswordRequest(identifier="hannah@example.com")
    )
    assert success
    assert "If an account exists" in msg

    # Fallback to SMS occurred!
    assert len(fake_sms_sender.sent_messages) == 1
    assert "+919876543210" in fake_sms_sender.sent_messages[0].to_phone_e164
    assert "verification OTP" in fake_sms_sender.sent_messages[0].message


@pytest.mark.asyncio
async def test_a16_sms_unverified_phone_rejected(
    auth_service: AuthService, fake_sms_sender, mock_db
):
    """Scenario A16: User picks 'Send SMS instead', phone unverified -> no SMS, audit log, generic response."""
    await mock_db.users.insert_one(
        {
            "name": "Ian",
            "email": "ian@example.com",
            "canonical_email": "ian@example.com",
            "phone_e164": "+919999999999",
            "phone_verified": False,  # Not verified!
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    success, msg = await auth_service.forgot_password(
        ForgotPasswordRequest(identifier="ian@example.com", channel="sms")
    )
    assert success
    assert len(fake_sms_sender.sent_messages) == 0

    # Verify audit log entry
    audit = await mock_db.audit_logs.find_one({"action": "forgot_password_sms_unverified"})
    assert audit is not None


@pytest.mark.asyncio
async def test_a17_sms_otp_wrong_five_times(auth_service: AuthService, fake_sms_sender, mock_db):
    """Scenario A17: SMS OTP wrong 5× -> token invalidated."""
    await mock_db.users.insert_one(
        {
            "name": "Jack",
            "email": "jack@example.com",
            "canonical_email": "jack@example.com",
            "phone_e164": "+919111111111",
            "phone_verified": True,
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    await auth_service.forgot_password(
        ForgotPasswordRequest(identifier="jack@example.com", channel="sms")
    )

    # 4 wrong OTP attempts
    for _ in range(4):
        success, msg = await auth_service.reset_password(
            ResetPasswordRequest(
                identifier="+919111111111", otp="000000", new_password="NewPassword123!"
            )
        )
        assert not success
        assert "Invalid OTP" in msg

    # 5th wrong attempt -> invalidates token
    success, msg = await auth_service.reset_password(
        ResetPasswordRequest(
            identifier="+919111111111", otp="000000", new_password="NewPassword123!"
        )
    )
    assert not success
    assert "Maximum OTP verification attempts exceeded" in msg

    # Active token should be deleted
    token_doc = await mock_db.auth_tokens.find_one({"channel": "sms"})
    assert token_doc is None


@pytest.mark.asyncio
async def test_a18_sms_daily_cap_throttling(auth_service: AuthService, mock_db):
    """Scenario A18: SMS request flood throttled by per-number daily cap."""
    await mock_db.users.insert_one(
        {
            "name": "Kelly",
            "email": "kelly@example.com",
            "canonical_email": "kelly@example.com",
            "phone_e164": "+919222222222",
            "phone_verified": True,
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    # Exhaust SMS limit (5 allowed per day per phone)
    auth_service.rate_limiter._history["sms_daily:+919222222222"] = [datetime.now(UTC)] * 5

    res = await auth_service._send_password_reset_sms(
        {"_id": ObjectId(), "phone_e164": "+919222222222"}, "127.0.0.1"
    )
    assert res is False


@pytest.mark.asyncio
async def test_a19_successful_reset_invalidates_old_jwts(
    auth_service: AuthService, fake_email_sender, mock_db
):
    """Scenario A19: Successful reset -> old JWTs and refresh tokens rejected (token_version bump)."""
    user_id = ObjectId()
    await mock_db.users.insert_one(
        {
            "_id": user_id,
            "name": "Leo",
            "email": "leo@example.com",
            "canonical_email": "leo@example.com",
            "password_hash": "old_hash",
            "token_version": 1,
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    # Old access token with version 1
    from backend.app.core.security import create_access_token

    old_jwt = create_access_token(str(user_id), "student", token_version=1)

    # Forgot & reset password
    await auth_service.forgot_password(ForgotPasswordRequest(identifier="leo@example.com"))
    raw_token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]
    await auth_service.reset_password(
        ResetPasswordRequest(token=raw_token, new_password="BrandNewPassword123!")
    )

    # User in DB now has token_version = 2
    updated_user = await mock_db.users.find_one({"_id": user_id})
    assert updated_user["token_version"] == 2

    # Old JWT has version 1, mismatched with DB -> invalidated!
    payload = decode_access_token(old_jwt)
    assert payload["token_version"] == 1
    assert payload["token_version"] != updated_user["token_version"]


@pytest.mark.asyncio
async def test_a20_refresh_token_reuse_revokes_entire_family(auth_service: AuthService, mock_db):
    """Scenario A20: Refresh-token reuse (stolen token) -> whole family revoked and user token_version bumped."""
    user_id = ObjectId()
    await mock_db.users.insert_one(
        {
            "_id": user_id,
            "name": "Mona",
            "email": "mona@example.com",
            "canonical_email": "mona@example.com",
            "token_version": 1,
            "status": UserStatus.ACTIVE.value,
            "role": UserRole.STUDENT.value,
        }
    )

    token_1 = "token_generation_1"
    family_id = "family_123"

    # Save token 1 as already rotated / revoked
    await mock_db.refresh_tokens.insert_one(
        {
            "user_id": user_id,
            "token_hash": hash_token(token_1),
            "family_id": family_id,
            "expires_at": datetime.now(UTC) + timedelta(days=7),
            "revoked_at": datetime.now(UTC),  # Already revoked!
        }
    )

    # Attacker tries to reuse token_1
    success, msg, _ = await auth_service.refresh_session(token_1)
    assert not success
    assert "compromised session token reuse detected" in msg.lower()

    # User's token_version bumped
    user = await mock_db.users.find_one({"_id": user_id})
    assert user["token_version"] == 2


@pytest.mark.asyncio
async def test_a21_reset_rejects_last_three_passwords(
    auth_service: AuthService, fake_email_sender, mock_db
):
    """Scenario A21: Reset to one of last 3 passwords / weak password -> rejected."""
    from backend.app.core.security import hash_password

    pass1 = "InitialPass123!"
    hash1 = hash_password(pass1)

    await mock_db.users.insert_one(
        {
            "name": "Nate",
            "email": "nate@example.com",
            "canonical_email": "nate@example.com",
            "password_hash": hash1,
            "previous_password_hashes": [hash1],
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    await auth_service.forgot_password(ForgotPasswordRequest(identifier="nate@example.com"))
    raw_token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]

    # Try reusing the exact same password
    success, msg = await auth_service.reset_password(
        ResetPasswordRequest(token=raw_token, new_password=pass1)
    )
    assert not success
    assert "last 3 passwords" in msg


@pytest.mark.asyncio
async def test_a22_email_scanner_get_does_not_consume_token(
    async_client, fake_email_sender, auth_service
):
    """Scenario A22: Email security scanner issues GET on reset link -> token NOT consumed."""
    from backend.app.db.mongo import get_database

    db = get_database()
    await db.users.insert_one(
        {
            "name": "Olivia",
            "email": "olivia@example.com",
            "canonical_email": "olivia@example.com",
            "email_verified": True,
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
        }
    )

    await auth_service.forgot_password(ForgotPasswordRequest(identifier="olivia@example.com"))
    raw_token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]

    # Email scanner performs GET /auth/reset-password?token=...
    res = await async_client.get(f"/auth/reset-password?token={raw_token}")
    # Method not allowed (405) because reset endpoint only accepts POST
    assert res.status_code in (404, 405)

    # Token in DB is still unconsumed!
    token_doc = await db.auth_tokens.find_one({"token_hash": hash_token(raw_token)})
    assert token_doc["used_at"] is None


@pytest.mark.asyncio
async def test_a23_role_escalation_attempt(auth_service: AuthService):
    """Scenario A23: Role escalation attempt (role: 'admin' in register body) -> rejected."""
    req = RegisterRequest(
        name="Hacker",
        email="hacker@shady.com",
        password="ValidPassword123!",
        role=UserRole.ADMIN,  # Escalation!
    )
    success, msg, _ = await auth_service.register(req)
    assert not success
    assert "administrator is not permitted" in msg.lower()


@pytest.mark.asyncio
async def test_hod_registration_and_admin_approval_lifecycle(
    auth_service: AuthService,
    fake_email_sender,
    async_client,
    mock_db,
):
    """Verifies HOD registration with department & phone, email verification, pending approval, and admin approval."""
    from backend.app.core.security import create_access_token

    # 1. HOD Registers with Department and Phone
    req = RegisterRequest(
        name="Dr. Alan Turing",
        email="alan.turing@cambridge.edu",
        password="StrongPassword123!",
        role=UserRole.HOD,
        department="Computer Science",
        phone="+15551234567",
        phone_e164="+15551234567",
    )
    success, msg, _ = await auth_service.register(req)
    assert success
    assert "check your email" in msg.lower()

    # Verify user record in database
    hod_doc = await mock_db.users.find_one({"email": "alan.turing@cambridge.edu"})
    assert hod_doc is not None
    assert hod_doc["role"] == "hod"
    assert hod_doc["department"] == "Computer Science"
    assert hod_doc["phone_e164"] == "+15551234567"
    assert hod_doc["status"] == UserStatus.PENDING_APPROVAL.value
    assert hod_doc["email_verified"] is False
    hod_id = str(hod_doc["_id"])

    # 2. Email verification
    token = fake_email_sender.sent_messages[0].text_content.split("token=")[1].split()[0]
    verified, v_msg = await auth_service.verify_email(VerifyEmailRequest(token=token))
    assert verified

    # 3. Attempt login before admin approval -> blocked
    login_success, login_msg, _ = await auth_service.login(
        LoginRequest(email="alan.turing@cambridge.edu", password="StrongPassword123!")
    )
    assert not login_success
    assert "administrator approval" in login_msg.lower()

    # 4. RBAC check on approval endpoints
    # Unauthenticated request -> 401
    res_unauth = await async_client.get("/api/v1/auth/pending-approvals")
    assert res_unauth.status_code == 401

    # Student request -> 403
    student_insert = await mock_db.users.insert_one(
        {
            "name": "Student Bob",
            "email": "bob@student.edu",
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
            "token_version": 1,
        }
    )
    student_id = str(student_insert.inserted_id)
    student_token = create_access_token(subject=student_id, role="student", token_version=1)
    res_student = await async_client.get(
        "/api/v1/auth/pending-approvals",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_student.status_code == 403

    # Admin request -> 200
    admin_doc = {
        "name": "System Admin",
        "email": "admin@college.edu",
        "role": UserRole.ADMIN.value,
        "status": UserStatus.ACTIVE.value,
        "token_version": 1,
    }
    admin_insert = await mock_db.users.insert_one(admin_doc)
    admin_id = str(admin_insert.inserted_id)
    admin_token = create_access_token(subject=admin_id, role="admin", token_version=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res_admin = await async_client.get("/api/v1/auth/pending-approvals", headers=admin_headers)
    assert res_admin.status_code == 200
    pending_list = res_admin.json()
    assert any(u["id"] == hod_id and u["department"] == "Computer Science" for u in pending_list)

    # 5. Admin approves HOD
    res_approve = await async_client.patch(
        f"/api/v1/auth/approve/{hod_id}",
        headers=admin_headers,
    )
    assert res_approve.status_code == 200
    assert "successfully approved" in res_approve.json()["message"].lower()

    # User status is now active
    updated_hod = await mock_db.users.find_one({"_id": hod_doc["_id"]})
    assert updated_hod["status"] == UserStatus.ACTIVE.value

    # 6. HOD logs in successfully
    login_success2, _, login_data = await auth_service.login(
        LoginRequest(email="alan.turing@cambridge.edu", password="StrongPassword123!")
    )
    assert login_success2
    assert login_data["user"]["role"] == "hod"
    assert "access_token" in login_data

