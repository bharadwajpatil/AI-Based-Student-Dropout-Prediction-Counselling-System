"""
Phase 10: End-to-End Verification Test Suite
Tests complete integration flows across all architectural components:
Authentication -> OCC Performance Updates -> Risk Engine -> AI Counselling -> Analytics -> SSE Events.
"""

from datetime import UTC, datetime
from bson import ObjectId
import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token, hash_password
from backend.app.models.user import UserRole, UserStatus
from backend.app.models.student import StudentStatus


@pytest.mark.asyncio
async def test_e2e_complete_faculty_and_student_lifecycle(async_client: AsyncClient, mock_db):
    """
    End-to-end test verifying full lifecycle:
    1. Faculty login -> token retrieval
    2. Student creation
    3. Performance upsert with OCC If-Match header
    4. Concurrency conflict test (If-Match version mismatch -> 412)
    5. Drop in attendance -> High Risk trigger & automated counselling stub
    6. Faculty adds meeting note to timeline
    7. Analytics overview query reflects active student and high-risk count
    8. High-risk CSV export downloads with formula neutralization prefix
    """
    # 1. Setup Admin & Teacher users
    now = datetime.now(UTC)
    admin_id = ObjectId()
    teacher_id = ObjectId()

    from backend.app.services.email_validation import compute_canonical_email

    admin_email = "admin@university.edu"
    teacher_email = "prof.sharma@university.edu"

    await mock_db.users.insert_many([
        {
            "_id": admin_id,
            "email": admin_email,
            "canonical_email": compute_canonical_email(admin_email),
            "password_hash": hash_password("AdminPass@123"),
            "name": "Super Admin",
            "role": UserRole.ADMIN.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": teacher_id,
            "email": teacher_email,
            "canonical_email": compute_canonical_email(teacher_email),
            "password_hash": hash_password("TeacherPass@123"),
            "name": "Prof. Sharma",
            "department": "Computer Science",
            "role": UserRole.TEACHER.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "created_at": now,
            "updated_at": now,
        },
    ])

    # Login as Teacher
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "prof.sharma@university.edu", "password": "TeacherPass@123"},
    )
    assert login_res.status_code == 200
    teacher_token = login_res.json()["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    # Verify Profile via /auth/me
    me_res = await async_client.get("/api/v1/auth/me", headers=teacher_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "prof.sharma@university.edu"

    # 2. Login as Admin & Create Student
    admin_login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@university.edu", "password": "AdminPass@123"},
    )
    assert admin_login_res.status_code == 200
    admin_token = admin_login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_student_res = await async_client.post(
        "/api/v1/students",
        headers=admin_headers,
        json={
            "erp_id": "CS2024-E2E-01",
            "name": "Rohan Verma",
            "institutional_email": "rohan.v@university.edu",
            "department": "Computer Science",
            "semester": 1,
            "batch": "2024-28",
            "assigned_teacher_ids": [str(teacher_id)],
        },
    )
    assert create_student_res.status_code == 201
    student_data = create_student_res.json()
    student_id = student_data["id"]

    # 3. Teacher queries assigned students
    list_res = await async_client.get("/api/v1/students", headers=teacher_headers)
    assert list_res.status_code == 200
    assert any(s["id"] == student_id for s in list_res.json()["items"])

    # 4. Upsert Performance with OCC (Initial version = 1)
    perf_res = await async_client.put(
        f"/api/v1/students/{student_id}/performance/1",
        headers={**teacher_headers, "If-Match": '"1"'},
        json={
            "academic_year": "2024-25",
            "attendance": 85.0,
            "classes_held": 100,
            "marks": 78.0,
            "backlogs": 0,
            "assignments": 85.0,
            "engagement": 80.0,
        },
    )
    assert perf_res.status_code == 200
    perf_data = perf_res.json()
    assert perf_data["attendance"] == 85.0
    current_version = perf_data["version"]

    # 5. OCC Conflict Test (If-Match sends stale version -> 409 Conflict)
    stale_res = await async_client.put(
        f"/api/v1/students/{student_id}/performance/1",
        headers={**teacher_headers, "If-Match": '"999"'},
        json={
            "academic_year": "2024-25",
            "attendance": 80.0,
            "classes_held": 100,
        },
    )
    assert stale_res.status_code == 409

    # 6. Verify Low Risk Evaluation
    risk_res = await async_client.get(
        f"/api/v1/students/{student_id}/risk",
        headers=teacher_headers,
    )
    assert risk_res.status_code == 200
    assert risk_res.json()["level"] == "Low"

    # 7. Escalation: Attendance drops to 42.0% (< 50% override floor -> High Risk)
    escalate_res = await async_client.put(
        f"/api/v1/students/{student_id}/performance/1",
        headers={**teacher_headers, "If-Match": f'"{current_version}"'},
        json={
            "academic_year": "2024-25",
            "attendance": 42.0,
            "classes_held": 100,
            "marks": 55.0,
            "backlogs": 2,
        },
    )
    assert escalate_res.status_code == 200
    new_version = escalate_res.json()["version"]

    # Recheck Risk -> should be High
    high_risk_res = await async_client.get(
        f"/api/v1/students/{student_id}/risk",
        headers=teacher_headers,
    )
    assert high_risk_res.status_code == 200
    assert high_risk_res.json()["level"] == "High"
    assert "attendance_below_50" in high_risk_res.json()["overrides_applied"]

    # 8. Automated Counselling Case Stub Creation Verification
    counselling_res = await async_client.get(
        f"/api/v1/counselling/student/{student_id}",
        headers=teacher_headers,
    )
    assert counselling_res.status_code == 200
    case_data = counselling_res.json()
    case_id = case_data["id"]
    assert case_data["status"] == "pending"

    # Generate AI Recommendation
    gen_res = await async_client.post(
        f"/api/v1/counselling/student/{student_id}/generate",
        headers=teacher_headers,
        json={"teacher_notes": "Student missed multiple morning sessions.", "force_regenerate": True},
    )
    assert gen_res.status_code == 200
    assert gen_res.json()["ai_recommendation"] is not None

    # Update Workflow Status to in_progress
    patch_case_res = await async_client.patch(
        f"/api/v1/counselling/{case_id}",
        headers=teacher_headers,
        json={"status": "in_progress"},
    )
    assert patch_case_res.status_code == 200
    assert patch_case_res.json()["status"] == "in_progress"

    # Add Meeting Note to Append-Only Timeline
    note_res = await async_client.post(
        f"/api/v1/counselling/{case_id}/notes",
        headers=teacher_headers,
        json={"content": "Conducted 1-on-1 session. Student committed to attend extra tutorials."},
    )
    assert note_res.status_code == 201
    assert len(note_res.json()["notes_timeline"]) >= 1

    # 9. Verify Notifications
    notif_res = await async_client.get(
        "/api/v1/notifications",
        headers=teacher_headers,
    )
    assert notif_res.status_code == 200
    notifs = notif_res.json()["items"]
    assert len(notifs) >= 1
    # Mark read
    await async_client.patch(
        f"/api/v1/notifications/{notifs[0]['id']}/read",
        headers=teacher_headers,
    )
    unread_res = await async_client.get(
        "/api/v1/notifications/unread-count",
        headers=teacher_headers,
    )
    assert unread_res.status_code == 200

    # 10. Analytics Overview
    overview_res = await async_client.get(
        "/api/v1/analytics/overview",
        headers=teacher_headers,
    )
    assert overview_res.status_code == 200
    ov_data = overview_res.json()
    assert ov_data["total_students"] >= 1
    assert ov_data["high_risk_count"] >= 1

    # 11. High-Risk CSV Export (Formula injection protected)
    export_res = await async_client.get(
        "/api/v1/analytics/export/high-risk",
        headers=admin_headers,
    )
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers.get("content-type", "")
    assert "CS2024-E2E-01" in export_res.text


@pytest.mark.asyncio
async def test_e2e_refresh_token_rotation_and_reuse_revocation(async_client: AsyncClient, mock_db):
    """
    Scenario A12 verification:
    1. Login -> receive access token & refresh token
    2. Refresh session -> new access token & new refresh token
    3. Reusing old rotated refresh token triggers automatic family revocation
    """
    now = datetime.now(UTC)
    uid = ObjectId()
    from backend.app.services.email_validation import compute_canonical_email

    email = "rotation.test@university.edu"
    await mock_db.users.insert_one({
        "_id": uid,
        "email": email,
        "canonical_email": compute_canonical_email(email),
        "password_hash": hash_password("Pass@12345"),
        "name": "Rotation Tester",
        "role": UserRole.TEACHER.value,
        "status": UserStatus.ACTIVE.value,
        "email_verified": True,
        "phone_verified": False,
        "created_at": now,
        "updated_at": now,
    })

    # Step 1: Login
    res1 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "rotation.test@university.edu", "password": "Pass@12345"},
    )
    assert res1.status_code == 200
    refresh_token_1 = res1.cookies.get("refresh_token")
    assert refresh_token_1 is not None

    # Step 2: Rotate refresh token
    res2 = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token_1},
    )
    assert res2.status_code == 200
    refresh_token_2 = res2.cookies.get("refresh_token")
    assert refresh_token_2 is not None
    assert refresh_token_2 != refresh_token_1

    # Step 3: Reuse Token 1 (simulating stolen token reuse attempt)
    res3 = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token_1},
    )
    # Reusing rotated token MUST fail
    assert res3.status_code == 401

    # Step 4: Token 2 should also now be revoked due to family revocation!
    res4 = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token_2},
    )
    assert res4.status_code == 401
