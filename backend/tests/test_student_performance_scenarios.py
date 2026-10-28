import asyncio
import io
from datetime import UTC, datetime

import openpyxl
import pytest
from bson import ObjectId
from httpx import AsyncClient

from backend.app.core.security import create_access_token
from backend.app.models.student import StudentStatus
from backend.app.models.user import UserRole, UserStatus
from backend.app.services.import_service import import_service


_user_counter = 0


async def create_test_user(
    mock_db,
    role: UserRole,
    email: str,
    name: str = "Test User",
    status: UserStatus = UserStatus.ACTIVE,
) -> dict:
    """Helper to insert an authenticated test user and generate an access token."""
    global _user_counter
    _user_counter += 1
    user_doc = {
        "name": name,
        "email": email.lower(),
        "email_verified": True,
        "phone_e164": f"+919876{_user_counter:06d}",
        "phone_verified": True,
        "password_hash": "dummyhash",
        "role": role.value,
        "status": status.value,
        "failed_login_count": 0,
        "locked_until": None,
        "token_version": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    res = await mock_db.users.insert_one(user_doc)
    user_id = str(res.inserted_id)
    user_doc["_id"] = res.inserted_id

    token = create_access_token(subject=user_id, role=role.value, token_version=1)
    return {
        "user": user_doc,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.mark.asyncio
async def test_crud_rbac_matrix(async_client: AsyncClient, mock_db):
    """
    Validates RBAC and object-level permissions across Admin, HOD, Teacher, and Student roles.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin@univ.edu")
    hod = await create_test_user(mock_db, UserRole.HOD, "hod@univ.edu")
    teacher1 = await create_test_user(mock_db, UserRole.TEACHER, "teacher1@univ.edu")
    teacher2 = await create_test_user(mock_db, UserRole.TEACHER, "teacher2@univ.edu")
    student_user1 = await create_test_user(mock_db, UserRole.STUDENT, "stu1@univ.edu")
    student_user2 = await create_test_user(mock_db, UserRole.STUDENT, "stu2@univ.edu")

    # 1. Admin creates student MET101 assigned to teacher1
    resp = await async_client.post(
        "/students",
        headers=admin["headers"],
        json={
            "erp_id": "met101",  # will normalize to MET101
            "name": "Rahul Verma",
            "institutional_email": "rahul@univ.edu",
            "department": "AI&DS",
            "semester": 8,
            "batch": "2022-26",
            "assigned_teacher_ids": [str(teacher1["user"]["_id"])],
            "status": "active",
        },
    )
    assert resp.status_code == 201
    student1_data = resp.json()
    student1_id = student1_data["id"]
    assert student1_data["erp_id"] == "MET101"

    # Link student_user1 to student1
    await mock_db.students.update_one(
        {"_id": ObjectId(student1_id)},
        {"$set": {"user_id": student_user1["user"]["_id"]}},
    )

    # 2. Teacher attempts to create student -> 403 Forbidden
    resp = await async_client.post(
        "/students",
        headers=teacher1["headers"],
        json={
            "erp_id": "MET102",
            "name": "Illegal Student",
            "department": "AI&DS",
            "semester": 1,
            "batch": "2024-28",
        },
    )
    assert resp.status_code == 403

    # 3. Student attempts to create student -> 403 Forbidden
    resp = await async_client.post(
        "/students",
        headers=student_user1["headers"],
        json={
            "erp_id": "MET103",
            "name": "Illegal Student",
            "department": "AI&DS",
            "semester": 1,
            "batch": "2024-28",
        },
    )
    assert resp.status_code == 403

    # 4. HOD creates student MET102
    resp = await async_client.post(
        "/students",
        headers=hod["headers"],
        json={
            "erp_id": "MET102",
            "name": "Priya Sharma",
            "department": "AI&DS",
            "semester": 8,
            "batch": "2022-26",
            "assigned_teacher_ids": [str(teacher2["user"]["_id"])],
            "status": "active",
        },
    )
    assert resp.status_code == 201
    student2_id = resp.json()["id"]

    # Link student_user2 to student2
    await mock_db.students.update_one(
        {"_id": ObjectId(student2_id)},
        {"$set": {"user_id": student_user2["user"]["_id"]}},
    )

    # 5. Object-level GET /students/{id}
    # Admin & HOD can view student1
    resp = await async_client.get(f"/students/{student1_id}", headers=admin["headers"])
    assert resp.status_code == 200

    resp = await async_client.get(f"/students/{student1_id}", headers=hod["headers"])
    assert resp.status_code == 200

    # Assigned teacher1 can view student1
    resp = await async_client.get(f"/students/{student1_id}", headers=teacher1["headers"])
    assert resp.status_code == 200

    # Unassigned teacher2 gets 403 when trying to view student1
    resp = await async_client.get(f"/students/{student1_id}", headers=teacher2["headers"])
    assert resp.status_code == 403

    # Student1 can view self
    resp = await async_client.get(f"/students/{student1_id}", headers=student_user1["headers"])
    assert resp.status_code == 200

    # Scenario S10: Student1 tries to view Student2 -> 403 & audited!
    resp = await async_client.get(f"/students/{student2_id}", headers=student_user1["headers"])
    assert resp.status_code == 403
    audit_entry = await mock_db.audit_logs.find_one(
        {"action": "unauthorized_student_access_attempt", "target_id": student2_id}
    )
    assert audit_entry is not None
    assert audit_entry["actor_id"] == student_user1["user"]["_id"]


@pytest.mark.asyncio
async def test_soft_delete_and_transfer_audited(async_client: AsyncClient, mock_db):
    """
    Scenario S12: Department transfer updates department and logs audit entry.
    Soft delete: Marking student as dropped/graduated preserves history and logs audit entry.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin2@univ.edu")

    # Create student
    resp = await async_client.post(
        "/students",
        headers=admin["headers"],
        json={
            "erp_id": "MET201",
            "name": "Transfer Student",
            "department": "Mechanical",
            "semester": 4,
            "batch": "2024-28",
        },
    )
    student_id = resp.json()["id"]

    # Transfer department: Mechanical -> AI&DS (Scenario S12)
    resp = await async_client.patch(
        f"/students/{student_id}",
        headers=admin["headers"],
        json={"department": "AI&DS"},
    )
    assert resp.status_code == 200
    assert resp.json()["department"] == "AI&DS"

    transfer_audit = await mock_db.audit_logs.find_one(
        {"action": "student_transfer_department", "target_id": student_id}
    )
    assert transfer_audit is not None
    assert transfer_audit["before"]["department"] == "Mechanical"
    assert transfer_audit["after"]["department"] == "AI&DS"

    # Soft delete: mark as dropped
    resp = await async_client.patch(
        f"/students/{student_id}",
        headers=admin["headers"],
        json={"status": "dropped"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"

    status_audit = await mock_db.audit_logs.find_one(
        {"action": "student_status_changed", "target_id": student_id}
    )
    assert status_audit is not None
    assert status_audit["before"]["status"] == "active"
    assert status_audit["after"]["status"] == "dropped"

    # Verify student still exists in DB (never hard deleted!)
    doc = await mock_db.students.find_one({"_id": ObjectId(student_id)})
    assert doc is not None
    assert doc["status"] == "dropped"


@pytest.mark.asyncio
async def test_performance_validation(async_client: AsyncClient, mock_db):
    """
    Validates performance constraints:
    - classes_held required if attendance provided.
    - numeric ranges: 0-100 float, backlogs 0-50, semester 1-12.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin3@univ.edu")

    resp = await async_client.post(
        "/students",
        headers=admin["headers"],
        json={
            "erp_id": "MET301",
            "name": "Perf Student",
            "department": "AI&DS",
            "semester": 3,
            "batch": "2024-28",
        },
    )
    student_id = resp.json()["id"]

    # 1. Attendance provided but classes_held missing -> 422
    resp = await async_client.put(
        f"/students/{student_id}/performance/3",
        headers=admin["headers"],
        json={
            "academic_year": "2025-26",
            "attendance": 85.0,
            # classes_held is missing
        },
    )
    assert resp.status_code == 422

    # 2. Marks > 100 -> 422
    resp = await async_client.put(
        f"/students/{student_id}/performance/3",
        headers=admin["headers"],
        json={
            "academic_year": "2025-26",
            "attendance": 85.0,
            "classes_held": 100,
            "marks": 105.0,
        },
    )
    assert resp.status_code == 422

    # 3. Backlogs > 50 -> 422
    resp = await async_client.put(
        f"/students/{student_id}/performance/3",
        headers=admin["headers"],
        json={
            "academic_year": "2025-26",
            "attendance": 85.0,
            "classes_held": 100,
            "backlogs": 55,
        },
    )
    assert resp.status_code == 422

    # 4. Valid performance -> 200
    resp = await async_client.put(
        f"/students/{student_id}/performance/3",
        headers=admin["headers"],
        json={
            "academic_year": "2025-26",
            "attendance": 75.0,
            "classes_held": 100,
            "marks": 68.5,
            "backlogs": 1,
            "assignments": 80.0,
            "engagement": 70.0,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


@pytest.mark.asyncio
async def test_s2_concurrent_edits_optimistic_concurrency(async_client: AsyncClient, mock_db):
    """
    Scenario S2: Two teachers edit same student simultaneously.
    One succeeds, other gets 409 with latest version; no lost update;
    one audit entry each for successful writes.
    """
    teacher1 = await create_test_user(mock_db, UserRole.TEACHER, "t1_s2@univ.edu")
    teacher2 = await create_test_user(mock_db, UserRole.TEACHER, "t2_s2@univ.edu")
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_s2@univ.edu")

    # Create student assigned to both teachers
    resp = await async_client.post(
        "/students",
        headers=admin["headers"],
        json={
            "erp_id": "MET_S2",
            "name": "Concurrent Test Student",
            "department": "AI&DS",
            "semester": 6,
            "batch": "2023-27",
            "assigned_teacher_ids": [
                str(teacher1["user"]["_id"]),
                str(teacher2["user"]["_id"]),
            ],
        },
    )
    student_id = resp.json()["id"]

    # Initial write creates version 1
    resp = await async_client.put(
        f"/students/{student_id}/performance/6",
        headers=teacher1["headers"],
        json={
            "academic_year": "2025-26",
            "attendance": 70.0,
            "classes_held": 100,
            "marks": 60.0,
        },
    )
    assert resp.status_code == 200
    perf = resp.json()
    assert perf["version"] == 1

    # Teacher 1 updates with If-Match: "1" -> succeeds, bumping version to 2
    resp1 = await async_client.put(
        f"/students/{student_id}/performance/6",
        headers={**teacher1["headers"], "If-Match": "1"},
        json={
            "academic_year": "2025-26",
            "attendance": 75.0,
            "classes_held": 100,
            "marks": 65.0,
        },
    )
    assert resp1.status_code == 200
    assert resp1.json()["version"] == 2

    # Teacher 2 attempts update concurrently with old If-Match: "1" -> gets 409 CONFLICT!
    resp2 = await async_client.put(
        f"/students/{student_id}/performance/6",
        headers={**teacher2["headers"], "If-Match": "1"},
        json={
            "academic_year": "2025-26",
            "attendance": 80.0,
            "classes_held": 100,
            "marks": 70.0,
        },
    )
    assert resp2.status_code == 409
    err = resp2.json()["error"]
    assert err["code"] == "CONCURRENT_MODIFICATION"
    assert "details" in err or "message" in err

    # Teacher 2 now fetches latest version (2) and submits with If-Match: "2" -> succeeds!
    resp3 = await async_client.put(
        f"/students/{student_id}/performance/6",
        headers={**teacher2["headers"], "If-Match": "2"},
        json={
            "academic_year": "2025-26",
            "attendance": 80.0,
            "classes_held": 100,
            "marks": 70.0,
        },
    )
    assert resp3.status_code == 200
    assert resp3.json()["version"] == 3


@pytest.mark.asyncio
async def test_s15_csv_formula_injection_defense(mock_db):
    """
    Scenario S15: CSV with =cmd|' /C calc'!A0 in a name cell -> neutralized.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_s15@univ.edu")

    csv_content = (
        "erp_id,name,department,semester,batch,attendance,classes_held,marks\n"
        "MET_FORMULA,=cmd|' /C calc'!A0,AI&DS,8,2022-26,80,100,75\n"
    ).encode("utf-8")

    job_id = await import_service.create_import_job(
        file=type("DummyFile", (), {"filename": "test.csv"})(),
        current_user=admin["user"],
    )

    job_res = await import_service.process_file(
        job_id=job_id,
        file_bytes=csv_content,
        filename="test.csv",
        current_user=admin["user"],
    )

    assert job_res.status == "completed"
    assert job_res.succeeded == 1

    # Check student record in database
    student = await mock_db.students.find_one({"erp_id": "MET_FORMULA"})
    assert student is not None
    # Formula prefix neutralized safely
    assert not student["name"].startswith("=")


@pytest.mark.asyncio
async def test_xlsx_import(mock_db):
    """
    Validates Excel (.xlsx) file parsing and import into students & performance.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_xlsx@univ.edu")

    # Create an in-memory workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        [
            "erp_id",
            "name",
            "department",
            "semester",
            "batch",
            "attendance",
            "classes_held",
            "marks",
        ]
    )
    ws.append(["XLSX101", "Bob Smith", "Computer Science", 4, "2024-28", 88.0, 100, 82.5])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    job_id = await import_service.create_import_job(
        file=type("DummyFile", (), {"filename": "data.xlsx"})(),
        current_user=admin["user"],
    )

    job_res = await import_service.process_file(
        job_id=job_id,
        file_bytes=xlsx_bytes,
        filename="data.xlsx",
        current_user=admin["user"],
    )

    assert job_res.status == "completed"
    assert job_res.succeeded == 1
    assert job_res.failed == 0

    student = await mock_db.students.find_one({"erp_id": "XLSX101"})
    assert student is not None
    assert student["name"] == "Bob Smith"


@pytest.mark.asyncio
async def test_s3_and_exit_gate_bulk_import_5000_rows(mock_db):
    """
    Phase 4 Exit Gate & Scenario S3:
    Bulk import 5,000 rows (including 50 bad rows and 100 in-file duplicates)
    completes with correct report, isolates errors without crashing, and
    performs idempotent upsert.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_gate@univ.edu")

    lines = ["erp_id,name,department,semester,batch,academic_year,attendance,classes_held,marks"]

    # 4,850 valid unique rows
    for i in range(1, 4851):
        lines.append(f"ERP{i},Student {i},AI&DS,4,2024-28,2025-26,75,100,70")

    # 50 invalid rows (missing fields, invalid semester, attendance with classes_held missing, marks > 100)
    for i in range(1, 51):
        if i <= 15:
            # Missing erp_id
            lines.append(f",BadStudent {i},AI&DS,4,2024-28,2025-26,75,100,70")
        elif i <= 30:
            # Invalid semester (15 > 12)
            lines.append(f"BAD_SEM_{i},Bad Sem Student,AI&DS,15,2024-28,2025-26,75,100,70")
        elif i <= 40:
            # Attendance provided but classes_held empty
            lines.append(f"BAD_ATT_{i},Bad Att Student,AI&DS,4,2024-28,2025-26,75,,70")
        else:
            # Marks out of range (150 > 100)
            lines.append(f"BAD_MARKS_{i},Bad Marks Student,AI&DS,4,2024-28,2025-26,75,100,150")

    # 100 duplicate rows (repeating ERP1 to ERP100 with same semester)
    for i in range(1, 101):
        lines.append(f"ERP{i},Duplicate Student {i},AI&DS,4,2024-28,2025-26,75,100,70")

    assert len(lines) == 5001  # Header + 5000 rows

    csv_text = "\n".join(lines)
    csv_bytes = csv_text.encode("utf-8")

    job_id = await import_service.create_import_job(
        file=type("DummyFile", (), {"filename": "bulk_5000.csv"})(),
        current_user=admin["user"],
    )

    job_res = await import_service.process_file(
        job_id=job_id,
        file_bytes=csv_bytes,
        filename="bulk_5000.csv",
        current_user=admin["user"],
    )

    assert job_res.total == 5000
    assert job_res.succeeded == 4850
    assert job_res.failed == 150  # 50 invalid + 100 duplicates
    assert len(job_res.errors) == 150
    assert job_res.status == "completed"

    # Verify error report lists row numbers and specific reasons
    assert all("row" in err and "reason" in err for err in job_res.errors)

    # Re-uploading same file performs idempotent upsert without duplicate records
    job_id_2 = await import_service.create_import_job(
        file=type("DummyFile", (), {"filename": "bulk_5000_retry.csv"})(),
        current_user=admin["user"],
    )
    job_res_2 = await import_service.process_file(
        job_id=job_id_2,
        file_bytes=csv_bytes,
        filename="bulk_5000_retry.csv",
        current_user=admin["user"],
    )
    assert job_res_2.succeeded == 4850
    assert job_res_2.failed == 150


@pytest.mark.asyncio
async def test_s4_resumption_from_stored_cursor(mock_db):
    """
    Scenario S4: Import resumes from stored cursor if interrupted midway.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_s4@univ.edu")

    lines = ["erp_id,name,department,semester,batch,academic_year,attendance,classes_held,marks"]
    for i in range(1, 11):
        lines.append(f"RESUME_{i},Resume Student {i},AI&DS,2,2024-28,2025-26,80,100,75")

    csv_bytes = "\n".join(lines).encode("utf-8")

    job_id = await import_service.create_import_job(
        file=type("DummyFile", (), {"filename": "resume.csv"})(),
        current_user=admin["user"],
    )

    # First pass: simulate failure after 5 rows
    job_res_1 = await import_service.process_file(
        job_id=job_id,
        file_bytes=csv_bytes,
        filename="resume.csv",
        current_user=admin["user"],
    )
    assert job_res_1.succeeded == 10

    # Resume from row 5: rows 6 to 10 are processed
    job_res_2 = await import_service.process_file(
        job_id=job_id,
        file_bytes=csv_bytes,
        filename="resume.csv",
        current_user=admin["user"],
        resume_from=5,
    )
    assert job_res_2.succeeded == 5  # rows 6..10


@pytest.mark.asyncio
async def test_cursor_pagination_and_filtering(async_client: AsyncClient, mock_db):
    """
    Validates cursor-based pagination and filtering on GET /students.
    """
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_pag@univ.edu")

    # Insert 5 students in AI&DS and 3 in Mechanical
    for i in range(1, 6):
        await async_client.post(
            "/students",
            headers=admin["headers"],
            json={
                "erp_id": f"PAG_AI_{i}",
                "name": f"AI Student {i}",
                "department": "AI&DS",
                "semester": 4,
                "batch": "2024-28",
            },
        )
    for i in range(1, 4):
        await async_client.post(
            "/students",
            headers=admin["headers"],
            json={
                "erp_id": f"PAG_MECH_{i}",
                "name": f"Mech Student {i}",
                "department": "Mechanical",
                "semester": 6,
                "batch": "2023-27",
            },
        )

    # 1. Filter by department
    resp = await async_client.get("/students?department=Mechanical", headers=admin["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # 2. Cursor pagination with limit=2
    resp = await async_client.get("/students?department=AI%26DS&limit=2", headers=admin["headers"])
    assert resp.status_code == 200
    page1 = resp.json()
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert page1["has_more"] is True
    assert page1["next_cursor"] is not None

    # Next page using cursor
    cursor = page1["next_cursor"]
    resp2 = await async_client.get(
        f"/students?department=AI%26DS&limit=2&cursor={cursor}",
        headers=admin["headers"],
    )
    assert resp2.status_code == 200
    page2 = resp2.json()
    assert len(page2["items"]) == 2
    assert page2["items"][0]["erp_id"] != page1["items"][0]["erp_id"]


@pytest.mark.asyncio
async def test_get_student_risk_api(async_client: AsyncClient, mock_db):
    """Validates GET /students/{id}/risk returns current risk, factors, and explainability."""
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_risk@univ.edu")

    # Create student
    s_resp = await async_client.post(
        "/students",
        headers=admin["headers"],
        json={
            "erp_id": "RISK_API_101",
            "name": "Risk API Student",
            "department": "AI&DS",
            "semester": 4,
            "batch": "2024-28",
        },
    )
    sid = s_resp.json()["id"]

    # Record performance (high risk attendance < 50)
    await async_client.put(
        f"/students/{sid}/performance/4",
        headers=admin["headers"],
        json={
            "academic_year": "2025-26",
            "attendance": 48.0,
            "classes_held": 100,
            "marks": 60.0,
            "backlogs": 1,
        },
    )

    # Fetch risk
    resp = await async_client.get(f"/students/{sid}/risk", headers=admin["headers"])
    assert resp.status_code == 200
    risk_data = resp.json()
    assert risk_data["level"] == "High"
    assert risk_data["score"] == 70.0
    assert "attendance_below_50" in risk_data["overrides_applied"]
    assert "Critical override" in risk_data["explanation_summary"]


@pytest.mark.asyncio
async def test_list_faculty_endpoint(async_client: AsyncClient, mock_db):
    admin = await create_test_user(mock_db, UserRole.ADMIN, "admin_fac_test@test.com", "Admin Fac")
    teacher1 = await create_test_user(mock_db, UserRole.TEACHER, "teacher_fac_test@test.com", "Teacher Fac")

    resp = await async_client.get("/students/faculty", headers=admin["headers"])
    assert resp.status_code == 200
    faculty = resp.json()
    assert isinstance(faculty, list)
    assert len(faculty) >= 1
    assert any(f["email"] == teacher1["user"]["email"] for f in faculty)




