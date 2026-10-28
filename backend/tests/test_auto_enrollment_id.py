from datetime import UTC, datetime
import pytest
from backend.app.core.security import create_access_token
from backend.app.models.user import UserRole, UserStatus
from backend.app.services.student_service import student_service


async def create_test_admin(mock_db, email: str = "admin_auto@univ.edu") -> dict:
    user_doc = {
        "name": "Admin User",
        "email": email.lower(),
        "email_verified": True,
        "phone_e164": "+919876543210",
        "phone_verified": True,
        "password_hash": "dummyhash",
        "role": UserRole.ADMIN.value,
        "status": UserStatus.ACTIVE.value,
        "failed_login_count": 0,
        "locked_until": None,
        "token_version": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    res = await mock_db.users.insert_one(user_doc)
    user_id = str(res.inserted_id)
    token = create_access_token(
        subject=user_id, role=UserRole.ADMIN.value, token_version=1
    )
    return {
        "user_id": user_id,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.mark.asyncio
async def test_generate_enrollment_id_prefixes(mock_db):
    """Verifies prefix resolution for various department formats."""
    assert student_service._get_department_prefix("Computer Science") == "CS"
    assert student_service._get_department_prefix("Electrical Engineering") == "EE"
    assert student_service._get_department_prefix("Mechanical Engineering") == "ME"
    assert student_service._get_department_prefix("Civil Engineering") == "CE"
    assert student_service._get_department_prefix("Information Technology") == "IT"
    assert student_service._get_department_prefix("Artificial Intelligence") == "AI"
    assert student_service._get_department_prefix("Data Science") == "DS"


@pytest.mark.asyncio
async def test_auto_generate_enrollment_id_on_create(mock_db, async_client):
    """Scenario: Enrolling student with no erp_id automatically assigns unique sequence ID."""
    admin = await create_test_admin(mock_db)

    # 1. Fetch next enrollment ID preview endpoint
    res_preview = await async_client.get(
        "/api/v1/students/generate-enrollment-id?department=Computer Science&batch=2024-2028",
        headers=admin["headers"],
    )
    assert res_preview.status_code == 200
    preview_data = res_preview.json()
    assert "enrollment_id" in preview_data
    assert preview_data["enrollment_id"].startswith("CS2024-")

    # 2. Create student without providing erp_id
    res_create = await async_client.post(
        "/api/v1/students",
        headers=admin["headers"],
        json={
            "name": "Auto Enrolled Student 1",
            "department": "Computer Science",
            "semester": 1,
            "batch": "2024-2028",
        },
    )
    assert res_create.status_code == 201
    student1 = res_create.json()
    assert student1["erp_id"].startswith("CS2024-")
    assert student1["erp_id"] == preview_data["enrollment_id"]

    # 3. Create second student in same department -> sequence automatically increments
    res_create2 = await async_client.post(
        "/api/v1/students",
        headers=admin["headers"],
        json={
            "name": "Auto Enrolled Student 2",
            "department": "Computer Science",
            "semester": 1,
            "batch": "2024-2028",
        },
    )
    assert res_create2.status_code == 201
    student2 = res_create2.json()
    assert student2["erp_id"].startswith("CS2024-")
    assert student2["erp_id"] != student1["erp_id"]

    # 4. Create student with explicit manual erp_id -> still respected
    res_manual = await async_client.post(
        "/api/v1/students",
        headers=admin["headers"],
        json={
            "erp_id": "CUSTOM-MANUAL-99",
            "name": "Manual Student",
            "department": "Computer Science",
            "semester": 1,
            "batch": "2024-2028",
        },
    )
    assert res_manual.status_code == 201
    assert res_manual.json()["erp_id"] == "CUSTOM-MANUAL-99"

    # 5. Teacher enrolls student via teacher endpoint without providing erp_id
    teacher_doc = {
        "name": "Prof Test",
        "email": "teacher_auto@univ.edu",
        "email_verified": True,
        "phone_e164": "+919876543299",
        "phone_verified": True,
        "password_hash": "dummyhash",
        "role": UserRole.TEACHER.value,
        "department": "Mechanical Engineering",
        "status": UserStatus.ACTIVE.value,
        "failed_login_count": 0,
        "locked_until": None,
        "token_version": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    t_res = await mock_db.users.insert_one(teacher_doc)
    teacher_token = create_access_token(
        subject=str(t_res.inserted_id), role=UserRole.TEACHER.value, token_version=1
    )
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    res_teacher_enroll = await async_client.post(
        "/api/v1/teachers/students",
        headers=teacher_headers,
        json={
            "name": "Teacher Mentored Student",
            "department": "Mechanical Engineering",
            "semester": 3,
            "batch": "2023-2027",
        },
    )
    assert res_teacher_enroll.status_code == 201
    teacher_stu = res_teacher_enroll.json()
    assert teacher_stu["erp_id"].startswith("ME2023-")
