"""
Phase 11: Security, Privacy & Hardening Test Suite
Verifies:
1. OWASP Security Headers (CSP, HSTS, X-Content-Type-Options, Frame-Ancestors)
2. NoSQL Injection Defense (key rejection for '$' and '.')
3. Request Body Size Limits (DoS protection)
4. Sliding Window Rate Limiting (HTTP 429 & Retry-After)
5. FERPA / India DPDP Access Audit Logging for High-Risk Students
6. Student Data Portability Export (FERPA / DPDP Article 11)
7. Right to Erasure / Soft PII Anonymization
"""

from datetime import UTC, datetime
from bson import ObjectId
import pytest
from httpx import AsyncClient

from backend.app.core.config import settings
from backend.app.core.middleware import rate_limiter
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.student import StudentStatus
from backend.app.models.user import UserRole, UserStatus
from backend.app.services.email_validation import compute_canonical_email


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset the in-memory rate limiter before each test."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.mark.asyncio
async def test_security_headers_present_on_all_responses(async_client: AsyncClient):
    """Verifies OWASP-recommended security headers are returned on API endpoints."""
    res = await async_client.get("/health")
    assert res.status_code == 200
    headers = res.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in headers.get("content-security-policy", "")
    assert headers.get("x-xss-protection") == "0"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in headers.get("permissions-policy", "")


@pytest.mark.asyncio
async def test_nosql_injection_query_parameter_rejection(async_client: AsyncClient):
    """Verifies that query parameters containing '$' or '.' are rejected with 400 Bad Request."""
    # Attempt injection via $gt
    res = await async_client.get("/api/v1/students?$gt=0")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "PROHIBITED_INPUT_KEY"

    # Attempt injection via dotted key
    res_dot = await async_client.get("/api/v1/students?user.role=admin")
    assert res_dot.status_code == 400
    assert res_dot.json()["error"]["code"] == "PROHIBITED_INPUT_KEY"


@pytest.mark.asyncio
async def test_nosql_injection_json_payload_rejection(async_client: AsyncClient):
    """Verifies that JSON payload keys containing '$' or '.' are rejected with 400 Bad Request."""
    # Attempt operator injection in body
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@university.edu", "$ne": "something"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "PROHIBITED_INPUT_KEY"

    # Nested operator injection
    res_nested = await async_client.post(
        "/api/v1/auth/login",
        json={"email": {"$gt": ""}, "password": "pass"},
    )
    assert res_nested.status_code == 400
    assert res_nested.json()["error"]["code"] == "PROHIBITED_INPUT_KEY"


@pytest.mark.asyncio
async def test_request_size_limit_rejection(async_client: AsyncClient):
    """Verifies that requests exceeding maximum payload size limits are rejected with 413 Payload Too Large."""
    # Attempt oversized payload on regular endpoint
    oversized = 3 * 1024 * 1024  # 3MB > 2MB limit
    res = await async_client.post(
        "/api/v1/students",
        headers={"Content-Length": str(oversized), "Content-Type": "application/json"},
        content=b"x" * 10,
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_rate_limiting_sliding_window_enforcement(async_client: AsyncClient):
    """Verifies that exceeding the rate limit triggers HTTP 429 Too Many Requests."""
    # Set tight limit for testing
    original_auth_limit = settings.RATE_LIMIT_AUTH_PER_MINUTE
    settings.RATE_LIMIT_AUTH_PER_MINUTE = 3
    try:
        # 3 requests within limit
        for _ in range(3):
            res = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@test.com", "password": "wrong"},
            )
            assert res.status_code in (401, 422)
            assert "X-RateLimit-Remaining" in res.headers

        # 4th request must be throttled
        throttled_res = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "wrong"},
        )
        assert throttled_res.status_code == 429
        assert throttled_res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in throttled_res.headers
    finally:
        settings.RATE_LIMIT_AUTH_PER_MINUTE = original_auth_limit


@pytest.mark.asyncio
async def test_ferpa_high_risk_student_read_audit_logging(async_client: AsyncClient, mock_db):
    """
    Verifies FERPA / DPDP audit requirement:
    Every read of a High-risk student's detail must generate an audit log entry.
    """
    now = datetime.now(UTC)
    admin_id = ObjectId()
    student_oid = ObjectId()
    admin_email = "admin@university.edu"

    await mock_db.users.insert_one({
        "_id": admin_id,
        "email": admin_email,
        "canonical_email": compute_canonical_email(admin_email),
        "password_hash": hash_password("AdminPass@123"),
        "name": "Super Admin",
        "role": UserRole.ADMIN.value,
        "status": UserStatus.ACTIVE.value,
        "email_verified": True,
        "phone_verified": True,
        "token_version": 1,
        "created_at": now,
        "updated_at": now,
    })

    await mock_db.students.insert_one({
        "_id": student_oid,
        "erp_id": "CS-HIGH-01",
        "name": "Aarav Gupta",
        "department": "Computer Science",
        "semester": 2,
        "batch": "2024-28",
        "assigned_teacher_ids": [],
        "status": StudentStatus.ACTIVE.value,
        "created_at": now,
        "updated_at": now,
    })

    # Initially insert a High risk result
    await mock_db.risk_results.insert_one({
        "student_id": student_oid,
        "score": 85.0,
        "level": "High",
        "confidence": 0.95,
        "watchlist": True,
        "factors": [],
        "overrides_applied": ["attendance_below_50"],
        "engine_version": "1.0.0",
        "inputs_hash": "hash123",
        "computed_at": now,
        "is_current": True,
    })

    admin_token = create_access_token(str(admin_id), UserRole.ADMIN.value, token_version=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Fetch student detail
    get_res = await async_client.get(f"/api/v1/students/{student_oid}", headers=admin_headers)
    assert get_res.status_code == 200

    # Verify audit log was created
    audit_entry = await mock_db.audit_logs.find_one({
        "action": "high_risk_student_detail_accessed",
        "target_id": str(student_oid),
    })
    assert audit_entry is not None
    assert audit_entry["actor_id"] == admin_id


@pytest.mark.asyncio
async def test_student_data_portability_export(async_client: AsyncClient, mock_db):
    """
    Verifies FERPA / India DPDP Article 11 Data Portability export:
    Aggregates demographics, performance, risk results, counselling, and audit logs into a clean package.
    """
    now = datetime.now(UTC)
    admin_id = ObjectId()
    student_oid = ObjectId()
    admin_email = "admin@privacy.edu"

    await mock_db.users.insert_one({
        "_id": admin_id,
        "email": admin_email,
        "canonical_email": compute_canonical_email(admin_email),
        "password_hash": hash_password("AdminPass@123"),
        "name": "Admin Privacy Officer",
        "role": UserRole.ADMIN.value,
        "status": UserStatus.ACTIVE.value,
        "email_verified": True,
        "phone_verified": True,
        "token_version": 1,
        "created_at": now,
        "updated_at": now,
    })

    await mock_db.students.insert_one({
        "_id": student_oid,
        "erp_id": "CS-PORTABLE-01",
        "name": "Meera Patel",
        "department": "Computer Science",
        "semester": 3,
        "batch": "2023-27",
        "assigned_teacher_ids": [],
        "status": StudentStatus.ACTIVE.value,
        "created_at": now,
        "updated_at": now,
    })

    admin_token = create_access_token(str(admin_id), UserRole.ADMIN.value, token_version=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    export_res = await async_client.get(f"/api/v1/students/{student_oid}/export-data", headers=admin_headers)
    assert export_res.status_code == 200
    export_data = export_res.json()

    assert "FERPA / India DPDP" in export_data["compliance_notice"]
    assert export_data["student"]["erp_id"] == "CS-PORTABLE-01"
    assert "performances" in export_data
    assert "risk_history" in export_data
    assert "audit_trail" in export_data

    # Audit log check
    audit_entry = await mock_db.audit_logs.find_one({
        "action": "student_data_portability_exported",
        "target_id": str(student_oid),
    })
    assert audit_entry is not None


@pytest.mark.asyncio
async def test_right_to_erasure_and_soft_anonymization(async_client: AsyncClient, mock_db):
    """
    Verifies Right to Erasure (Admin only):
    Soft-deletes student, anonymizes PII (name, email), while preserving de-identified records for historical analytics.
    """
    now = datetime.now(UTC)
    admin_id = ObjectId()
    teacher_id = ObjectId()
    student_oid = ObjectId()

    await mock_db.users.insert_many([
        {
            "_id": admin_id,
            "email": "admin@erase.edu",
            "canonical_email": compute_canonical_email("admin@erase.edu"),
            "password_hash": hash_password("AdminPass@123"),
            "role": UserRole.ADMIN.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": teacher_id,
            "email": "teacher@erase.edu",
            "canonical_email": compute_canonical_email("teacher@erase.edu"),
            "password_hash": hash_password("TeacherPass@123"),
            "role": UserRole.TEACHER.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
    ])

    await mock_db.students.insert_one({
        "_id": student_oid,
        "erp_id": "CS-ERASE-01",
        "name": "Personal Name",
        "institutional_email": "personal@university.edu",
        "department": "Computer Science",
        "semester": 1,
        "batch": "2024-28",
        "assigned_teacher_ids": [teacher_id],
        "status": StudentStatus.ACTIVE.value,
        "created_at": now,
        "updated_at": now,
    })

    teacher_token = create_access_token(str(teacher_id), UserRole.TEACHER.value, token_version=1)
    admin_token = create_access_token(str(admin_id), UserRole.ADMIN.value, token_version=1)

    # 1. Non-admin cannot delete
    unauth_res = await async_client.delete(
        f"/api/v1/students/{student_oid}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert unauth_res.status_code == 403

    # 2. Admin successfully executes anonymization
    del_res = await async_client.delete(
        f"/api/v1/students/{student_oid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "anonymized_and_deleted"

    # Verify student is anonymized in DB
    updated = await mock_db.students.find_one({"_id": student_oid})
    assert "Anonymized Student" in updated["name"]
    assert "gdpr-erased.local" in updated["institutional_email"]
    assert updated["status"] == StudentStatus.DROPPED.value

    # Verify audit log
    audit_entry = await mock_db.audit_logs.find_one({
        "action": "student_data_anonymized_and_deleted",
        "target_id": str(student_oid),
    })
    assert audit_entry is not None
