from datetime import UTC, datetime
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.deps import get_current_user, require_role
from backend.app.db.mongo import get_database
from backend.app.models.user import UserRole
from backend.app.schemas.subject import (
    AssignTeacherToSubjectRequest,
    BulkAssignSubjectsToTeacherRequest,
    SubjectCreateRequest,
    SubjectResponse,
    SubjectUpdateRequest,
)

router = APIRouter(tags=["Subjects & Courses"])


def _format_subject_response(doc: dict[str, Any]) -> SubjectResponse:
    return SubjectResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        code=doc["code"],
        department=doc["department"],
        year=str(doc.get("year", "1st Year")),
        semester=int(doc["semester"]),
        credits=int(doc.get("credits", 3)),
        academic_year=doc.get("academic_year", "2024-25"),
        assigned_teacher_id=str(doc["assigned_teacher_id"]) if doc.get("assigned_teacher_id") else None,
        assigned_teacher_name=doc.get("assigned_teacher_name"),
        hod_id=str(doc["hod_id"]) if doc.get("hod_id") else None,
        created_at=doc.get("created_at", datetime.now(UTC)),
        updated_at=doc.get("updated_at", datetime.now(UTC)),
    )


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    department: str | None = Query(default=None),
    semester: int | None = Query(default=None),
    teacher_id: str | None = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List all subjects with optional filters."""
    db = get_database()
    query: dict[str, Any] = {}

    if department:
        query["department"] = department
    elif current_user.get("role") == UserRole.HOD.value and current_user.get("department"):
        query["department"] = current_user.get("department")

    if semester is not None:
        query["semester"] = semester

    if teacher_id:
        if ObjectId.is_valid(teacher_id):
            query["assigned_teacher_id"] = ObjectId(teacher_id)

    cursor = db.subjects.find(query).sort([("semester", 1), ("code", 1)])
    docs = await cursor.to_list(200)
    return [_format_subject_response(d) for d in docs]


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    req: SubjectCreateRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Create a new subject curriculum record (HOD and Admin only)."""
    db = get_database()
    clean_code = req.code.strip().upper()

    existing = await db.subjects.find_one({"code": clean_code, "department": req.department.strip()})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Subject with code '{clean_code}' already exists in {req.department}.",
        )

    teacher_oid = None
    teacher_name = None
    if req.assigned_teacher_id and ObjectId.is_valid(req.assigned_teacher_id):
        t = await db.users.find_one({"_id": ObjectId(req.assigned_teacher_id)})
        if t:
            teacher_oid = t["_id"]
            teacher_name = t["name"]

    now = datetime.now(UTC)
    doc = {
        "name": req.name.strip(),
        "code": clean_code,
        "department": req.department.strip(),
        "year": req.year.strip(),
        "semester": req.semester,
        "credits": req.credits,
        "academic_year": req.academic_year.strip(),
        "assigned_teacher_id": teacher_oid,
        "assigned_teacher_name": teacher_name,
        "hod_id": ObjectId(current_user["_id"]) if current_user.get("role") == UserRole.HOD.value else None,
        "created_at": now,
        "updated_at": now,
    }

    res = await db.subjects.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _format_subject_response(doc)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve details for a single subject."""
    if not ObjectId.is_valid(subject_id):
        raise HTTPException(status_code=400, detail="Invalid subject ID.")

    db = get_database()
    doc = await db.subjects.find_one({"_id": ObjectId(subject_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Subject not found.")

    return _format_subject_response(doc)


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    req: SubjectUpdateRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Update subject information."""
    if not ObjectId.is_valid(subject_id):
        raise HTTPException(status_code=400, detail="Invalid subject ID.")

    db = get_database()
    s_oid = ObjectId(subject_id)
    subject = await db.subjects.find_one({"_id": s_oid})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    update_fields: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if req.name is not None:
        update_fields["name"] = req.name.strip()
    if req.code is not None:
        update_fields["code"] = req.code.strip().upper()
    if req.department is not None:
        update_fields["department"] = req.department.strip()
    if req.year is not None:
        update_fields["year"] = req.year.strip()
    if req.semester is not None:
        update_fields["semester"] = req.semester
    if req.credits is not None:
        update_fields["credits"] = req.credits
    if req.academic_year is not None:
        update_fields["academic_year"] = req.academic_year.strip()

    if req.assigned_teacher_id is not None:
        if req.assigned_teacher_id == "":
            update_fields["assigned_teacher_id"] = None
            update_fields["assigned_teacher_name"] = None
        elif ObjectId.is_valid(req.assigned_teacher_id):
            teacher = await db.users.find_one({"_id": ObjectId(req.assigned_teacher_id)})
            if teacher:
                update_fields["assigned_teacher_id"] = teacher["_id"]
                update_fields["assigned_teacher_name"] = teacher["name"]

    await db.subjects.update_one({"_id": s_oid}, {"$set": update_fields})
    updated = await db.subjects.find_one({"_id": s_oid})
    return _format_subject_response(updated)


@router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Delete a subject record."""
    if not ObjectId.is_valid(subject_id):
        raise HTTPException(status_code=400, detail="Invalid subject ID.")

    db = get_database()
    res = await db.subjects.delete_one({"_id": ObjectId(subject_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subject not found.")

    return {"success": True, "message": "Subject deleted."}


@router.post("/subjects/{subject_id}/assign-teacher", response_model=SubjectResponse)
async def assign_teacher_to_subject(
    subject_id: str,
    req: AssignTeacherToSubjectRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Assign or reassign a teacher to a specific subject (HOD / Admin)."""
    if not ObjectId.is_valid(subject_id) or not ObjectId.is_valid(req.teacher_id):
        raise HTTPException(status_code=400, detail="Invalid subject or teacher ID.")

    db = get_database()
    s_oid = ObjectId(subject_id)
    t_oid = ObjectId(req.teacher_id)

    teacher = await db.users.find_one({"_id": t_oid, "role": UserRole.TEACHER.value})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    res = await db.subjects.update_one(
        {"_id": s_oid},
        {
            "$set": {
                "assigned_teacher_id": t_oid,
                "assigned_teacher_name": teacher["name"],
                "updated_at": datetime.now(UTC),
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Subject not found.")

    updated = await db.subjects.find_one({"_id": s_oid})
    return _format_subject_response(updated)


@router.post("/teachers/{teacher_id}/assign-subjects")
async def bulk_assign_subjects_to_teacher(
    teacher_id: str,
    req: BulkAssignSubjectsToTeacherRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.HOD, UserRole.ADMIN)),
):
    """Assign multiple subjects to a teacher simultaneously (HOD / Admin)."""
    if not ObjectId.is_valid(teacher_id):
        raise HTTPException(status_code=400, detail="Invalid teacher ID.")

    db = get_database()
    t_oid = ObjectId(teacher_id)
    teacher = await db.users.find_one({"_id": t_oid, "role": UserRole.TEACHER.value})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    valid_s_oids = [ObjectId(sid) for sid in req.subject_ids if ObjectId.is_valid(sid)]
    if not valid_s_oids:
        raise HTTPException(status_code=400, detail="No valid subject IDs provided.")

    res = await db.subjects.update_many(
        {"_id": {"$in": valid_s_oids}},
        {
            "$set": {
                "assigned_teacher_id": t_oid,
                "assigned_teacher_name": teacher["name"],
                "updated_at": datetime.now(UTC),
            }
        },
    )

    total_assigned = await db.subjects.count_documents({"assigned_teacher_id": t_oid})
    return {
        "success": True,
        "modified_count": res.modified_count,
        "total_assigned_subjects": total_assigned,
        "teacher_name": teacher["name"],
    }


@router.get("/teachers/me/subjects", response_model=list[SubjectResponse])
async def get_my_assigned_subjects(
    current_user: dict[str, Any] = Depends(require_role(UserRole.TEACHER)),
):
    """Retrieve subjects assigned to the currently authenticated teacher."""
    db = get_database()
    t_oid = ObjectId(current_user["_id"])
    cursor = db.subjects.find({"assigned_teacher_id": t_oid}).sort([("semester", 1), ("name", 1)])
    docs = await cursor.to_list(100)
    return [_format_subject_response(d) for d in docs]
