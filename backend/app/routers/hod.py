from datetime import UTC, datetime
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.deps import require_role
from backend.app.core.security import hash_password
from backend.app.db.mongo import get_database
from backend.app.models.user import UserRole, UserStatus
from backend.app.schemas.hierarchy import (
    CreateTeacherRequest,
    TeacherResponse,
    UpdateTeacherRequest,
)

router = APIRouter(prefix="/hod", tags=["HOD Management"])


@router.get("/stats")
async def get_hod_department_stats(
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Department-specific statistics for HOD dashboard."""
    db = get_database()
    dept = current_user.get("department")

    teacher_query = {"role": UserRole.TEACHER.value}
    student_query = {}
    subject_query = {}
    risk_query = {"is_current": True}

    if dept:
        teacher_query["department"] = dept
        student_query["department"] = dept
        subject_query["department"] = dept

        # Student IDs in department for risk matching
        dept_student_ids = await db.students.distinct("_id", {"department": dept})
        risk_query["student_id"] = {"$in": dept_student_ids}

    total_teachers = await db.users.count_documents(teacher_query)
    total_students = await db.students.count_documents(student_query)
    total_subjects = await db.subjects.count_documents(subject_query)

    high_risk = await db.risk_results.count_documents({"level": "High", **risk_query})
    med_risk = await db.risk_results.count_documents({"level": "Medium", **risk_query})
    low_risk = await db.risk_results.count_documents({"level": "Low", **risk_query})

    # Backlog count in department
    if dept:
        dept_student_oids = await db.students.distinct("_id", {"department": dept})
        backlog_students = await db.performance.distinct("student_id", {
            "student_id": {"$in": dept_student_oids},
            "backlogs": {"$gt": 0},
        })
    else:
        backlog_students = await db.performance.distinct("student_id", {"backlogs": {"$gt": 0}})

    return {
        "department": dept or "All Departments",
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_subjects": total_subjects,
        "high_risk_students": high_risk,
        "medium_risk_students": med_risk,
        "low_risk_students": low_risk,
        "students_with_backlogs": len(backlog_students),
    }


@router.get("/teachers", response_model=list[TeacherResponse])
async def list_department_teachers(
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Retrieve teachers in the HOD's department with assigned subjects and student count."""
    db = get_database()
    dept = current_user.get("department")
    query: dict[str, Any] = {"role": UserRole.TEACHER.value}
    if dept and current_user.get("role") == UserRole.HOD.value:
        query["department"] = dept

    cursor = db.users.find(query).sort("name", 1)
    teachers = await cursor.to_list(100)

    results = []
    for t in teachers:
        t_id = t["_id"]
        # Assigned subjects count
        sub_count = await db.subjects.count_documents({"assigned_teacher_id": t_id})
        # Assigned students count
        stu_count = await db.students.count_documents({"assigned_teacher_ids": t_id})

        results.append(
            TeacherResponse(
                id=str(t_id),
                name=t["name"],
                email=t["email"],
                phone=t.get("phone_e164"),
                employee_id=t.get("employee_id"),
                department=t.get("department") or dept or "General",
                designation=t.get("designation", "Assistant Professor"),
                role="teacher",
                status=t.get("status", "active"),
                hod_id=str(t["hod_id"]) if t.get("hod_id") else None,
                assigned_subjects_count=sub_count,
                assigned_students_count=stu_count,
                created_at=t.get("created_at", datetime.now(UTC)),
            )
        )
    return results


@router.post("/teachers", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    req: CreateTeacherRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Create a new Teacher account associated with the HOD (HOD/Admin only)."""
    db = get_database()
    email_clean = req.email.strip().lower()

    existing = await db.users.find_one({"email": email_clean})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{email_clean}' already exists.",
        )

    dept = req.department.strip() or current_user.get("department", "General")
    now = datetime.now(UTC)

    teacher_doc = {
        "name": req.name.strip(),
        "email": email_clean,
        "canonical_email": email_clean,
        "password_hash": hash_password(req.password),
        "role": UserRole.TEACHER.value,
        "department": dept,
        "employee_id": req.employee_id.strip() if req.employee_id else None,
        "designation": req.designation.strip() if req.designation else "Assistant Professor",
        "phone_e164": req.phone.strip() if req.phone else None,
        "hod_id": ObjectId(current_user["_id"]) if current_user.get("role") == UserRole.HOD.value else None,
        "status": UserStatus.ACTIVE.value,
        "email_verified": True,
        "phone_verified": True,
        "token_version": 1,
        "created_by": ObjectId(current_user["_id"]),
        "created_at": now,
        "updated_at": now,
    }

    res = await db.users.insert_one(teacher_doc)
    teacher_doc["_id"] = res.inserted_id

    return TeacherResponse(
        id=str(teacher_doc["_id"]),
        name=teacher_doc["name"],
        email=teacher_doc["email"],
        phone=teacher_doc.get("phone_e164"),
        employee_id=teacher_doc.get("employee_id"),
        department=teacher_doc["department"],
        designation=teacher_doc.get("designation"),
        role="teacher",
        status=teacher_doc["status"],
        hod_id=str(teacher_doc["hod_id"]) if teacher_doc.get("hod_id") else None,
        assigned_subjects_count=0,
        assigned_students_count=0,
        created_at=teacher_doc["created_at"],
    )


@router.patch("/teachers/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(
    teacher_id: str,
    req: UpdateTeacherRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Edit Teacher profile details."""
    if not ObjectId.is_valid(teacher_id):
        raise HTTPException(status_code=400, detail="Invalid teacher ID.")

    db = get_database()
    t_oid = ObjectId(teacher_id)
    teacher = await db.users.find_one({"_id": t_oid, "role": UserRole.TEACHER.value})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    update_fields: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if req.name is not None:
        update_fields["name"] = req.name.strip()
    if req.department is not None:
        update_fields["department"] = req.department.strip()
    if req.designation is not None:
        update_fields["designation"] = req.designation.strip()
    if req.employee_id is not None:
        update_fields["employee_id"] = req.employee_id.strip()
    if req.phone is not None:
        update_fields["phone_e164"] = req.phone.strip()
    if req.status is not None:
        update_fields["status"] = req.status.strip()

    await db.users.update_one({"_id": t_oid}, {"$set": update_fields})
    updated = await db.users.find_one({"_id": t_oid})

    sub_count = await db.subjects.count_documents({"assigned_teacher_id": t_oid})
    stu_count = await db.students.count_documents({"assigned_teacher_ids": t_oid})

    return TeacherResponse(
        id=str(updated["_id"]),
        name=updated["name"],
        email=updated["email"],
        phone=updated.get("phone_e164"),
        employee_id=updated.get("employee_id"),
        department=updated.get("department", "General"),
        designation=updated.get("designation"),
        role="teacher",
        status=updated.get("status", "active"),
        hod_id=str(updated["hod_id"]) if updated.get("hod_id") else None,
        assigned_subjects_count=sub_count,
        assigned_students_count=stu_count,
        created_at=updated.get("created_at", datetime.now(UTC)),
    )


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(
    teacher_id: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Deactivate or remove a teacher account."""
    if not ObjectId.is_valid(teacher_id):
        raise HTTPException(status_code=400, detail="Invalid teacher ID.")

    db = get_database()
    t_oid = ObjectId(teacher_id)
    res = await db.users.update_one(
        {"_id": t_oid, "role": UserRole.TEACHER.value},
        {"$set": {"status": UserStatus.DISABLED.value, "updated_at": datetime.now(UTC)}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    return {"success": True, "message": "Teacher account deactivated."}
