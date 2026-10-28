from datetime import UTC, datetime
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.deps import require_role
from backend.app.core.security import hash_password
from backend.app.db.mongo import get_database
from backend.app.models.user import UserRole, UserStatus
from backend.app.schemas.hierarchy import (
    CreateHODRequest,
    HODResponse,
    UpdateHODRequest,
)

router = APIRouter(prefix="/admin", tags=["Admin Management"])


@router.get("/stats")
async def get_admin_system_stats(
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    """Overall university-wide statistics for Super Admin dashboard."""
    db = get_database()
    total_hods = await db.users.count_documents({"role": UserRole.HOD.value})
    total_teachers = await db.users.count_documents({"role": UserRole.TEACHER.value})
    total_students = await db.students.count_documents({})
    total_subjects = await db.subjects.count_documents({})

    # Risk tiers
    high_risk = await db.risk_results.count_documents({"level": "High", "is_current": True})
    med_risk = await db.risk_results.count_documents({"level": "Medium", "is_current": True})
    low_risk = await db.risk_results.count_documents({"level": "Low", "is_current": True})

    # Students with backlogs
    backlog_students = await db.performance.distinct("student_id", {"backlogs": {"$gt": 0}})

    departments = await db.users.distinct("department", {"department": {"$ne": None}})

    return {
        "total_hods": total_hods,
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_subjects": total_subjects,
        "high_risk_students": high_risk,
        "medium_risk_students": med_risk,
        "low_risk_students": low_risk,
        "students_with_backlogs": len(backlog_students),
        "departments": departments,
    }


@router.get("/hods", response_model=list[HODResponse])
async def list_hods(
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    """Retrieve all HOD accounts with teacher and student counts."""
    db = get_database()
    cursor = db.users.find({"role": UserRole.HOD.value}).sort("name", 1)
    hods = await cursor.to_list(100)

    results = []
    for h in hods:
        dept = h.get("department", "")
        t_count = await db.users.count_documents({"role": UserRole.TEACHER.value, "department": dept})
        s_count = await db.students.count_documents({"department": dept})

        results.append(
            HODResponse(
                id=str(h["_id"]),
                name=h["name"],
                email=h["email"],
                phone=h.get("phone_e164"),
                employee_id=h.get("employee_id"),
                department=dept or "General",
                designation=h.get("designation", "Head of Department"),
                role="hod",
                status=h.get("status", "active"),
                teachers_count=t_count,
                students_count=s_count,
                created_at=h.get("created_at", datetime.now(UTC)),
            )
        )
    return results


@router.post("/hods", response_model=HODResponse, status_code=status.HTTP_201_CREATED)
async def create_hod(
    req: CreateHODRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new Head of Department (HOD) account (Admin only)."""
    db = get_database()
    email_clean = req.email.strip().lower()

    existing = await db.users.find_one({"email": email_clean})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{email_clean}' already exists.",
        )

    now = datetime.now(UTC)
    user_doc = {
        "name": req.name.strip(),
        "email": email_clean,
        "canonical_email": email_clean,
        "password_hash": hash_password(req.password),
        "role": UserRole.HOD.value,
        "department": req.department.strip(),
        "employee_id": req.employee_id.strip() if req.employee_id else None,
        "designation": req.designation.strip() if req.designation else "Head of Department",
        "phone_e164": req.phone.strip() if req.phone else None,
        "status": UserStatus.ACTIVE.value,
        "email_verified": True,
        "phone_verified": True,
        "token_version": 1,
        "created_by": ObjectId(current_user["_id"]),
        "created_at": now,
        "updated_at": now,
    }

    res = await db.users.insert_one(user_doc)
    user_doc["_id"] = res.inserted_id

    return HODResponse(
        id=str(user_doc["_id"]),
        name=user_doc["name"],
        email=user_doc["email"],
        phone=user_doc.get("phone_e164"),
        employee_id=user_doc.get("employee_id"),
        department=user_doc["department"],
        designation=user_doc.get("designation"),
        role="hod",
        status=user_doc["status"],
        teachers_count=0,
        students_count=0,
        created_at=user_doc["created_at"],
    )


@router.patch("/hods/{hod_id}", response_model=HODResponse)
async def update_hod(
    hod_id: str,
    req: UpdateHODRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    """Edit HOD details (Admin only)."""
    if not ObjectId.is_valid(hod_id):
        raise HTTPException(status_code=400, detail="Invalid HOD ID.")

    db = get_database()
    h_oid = ObjectId(hod_id)
    hod = await db.users.find_one({"_id": h_oid, "role": UserRole.HOD.value})
    if not hod:
        raise HTTPException(status_code=404, detail="HOD not found.")

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

    await db.users.update_one({"_id": h_oid}, {"$set": update_fields})
    updated = await db.users.find_one({"_id": h_oid})

    dept = updated.get("department", "")
    t_count = await db.users.count_documents({"role": UserRole.TEACHER.value, "department": dept})
    s_count = await db.students.count_documents({"department": dept})

    return HODResponse(
        id=str(updated["_id"]),
        name=updated["name"],
        email=updated["email"],
        phone=updated.get("phone_e164"),
        employee_id=updated.get("employee_id"),
        department=dept,
        designation=updated.get("designation"),
        role="hod",
        status=updated.get("status", "active"),
        teachers_count=t_count,
        students_count=s_count,
        created_at=updated.get("created_at", datetime.now(UTC)),
    )


@router.patch("/hods/{hod_id}/status")
async def toggle_hod_status(
    hod_id: str,
    status_val: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    """Activate or deactivate HOD account (Admin only)."""
    if not ObjectId.is_valid(hod_id):
        raise HTTPException(status_code=400, detail="Invalid HOD ID.")

    db = get_database()
    h_oid = ObjectId(hod_id)
    res = await db.users.update_one(
        {"_id": h_oid, "role": UserRole.HOD.value},
        {"$set": {"status": status_val, "updated_at": datetime.now(UTC)}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="HOD account not found.")

    return {"success": True, "hod_id": hod_id, "new_status": status_val}
