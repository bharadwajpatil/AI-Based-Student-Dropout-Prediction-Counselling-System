from datetime import UTC, datetime
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.deps import get_current_user, require_role
from backend.app.counselling.service import counselling_service
from backend.app.db.mongo import get_database
from backend.app.models.marks import calculate_grade
from backend.app.models.user import UserRole
from backend.app.risk.risk_engine import compute_student_risk
from backend.app.schemas.marks import (
    MarksEntryRequest,
    StudentBacklogSummary,
    SubjectMarksResponse,
)
from backend.app.schemas.student import StudentCreateRequest, StudentResponse
from backend.app.services.student_service import student_service

router = APIRouter(tags=["Marks, Attendance & Backlogs"])


def _format_marks_response(doc: dict[str, Any]) -> SubjectMarksResponse:
    return SubjectMarksResponse(
        id=str(doc["_id"]),
        student_id=str(doc["student_id"]),
        subject_id=str(doc["subject_id"]),
        subject_name=doc["subject_name"],
        subject_code=doc["subject_code"],
        semester=int(doc["semester"]),
        academic_year=doc.get("academic_year", "2024-25"),
        internal_marks=doc.get("internal_marks"),
        external_marks=doc.get("external_marks"),
        practical_marks=doc.get("practical_marks"),
        assignment_marks=doc.get("assignment_marks"),
        total_marks=float(doc["total_marks"]),
        grade=doc.get("grade", "F"),
        attendance=float(doc.get("attendance", 100.0)),
        is_backlog=bool(doc.get("is_backlog", False)),
        entered_by=str(doc["entered_by"]) if doc.get("entered_by") else None,
        updated_at=doc.get("updated_at", datetime.now(UTC)),
    )


async def _recalculate_student_performance_and_risk(
    student_oid: ObjectId,
    semester: int,
    academic_year: str,
    user_oid: ObjectId,
) -> None:
    """
    Recalculates semester aggregate attendance, marks, backlogs and runs the risk engine.
    Ensures that marks entered per subject directly update the dropout risk model.
    """
    db = get_database()
    marks_cursor = db.subject_marks.find({"student_id": student_oid, "semester": semester})
    marks_list = await marks_cursor.to_list(100)

    if not marks_list:
        return

    # Averages
    total_marks_sum = sum(m.get("total_marks", 0.0) for m in marks_list)
    avg_marks = round(total_marks_sum / len(marks_list), 1)

    att_sum = sum(m.get("attendance", 100.0) for m in marks_list)
    avg_att = round(att_sum / len(marks_list), 1)

    backlogs_count = sum(1 for m in marks_list if m.get("is_backlog", False))

    now = datetime.now(UTC)

    # Upsert into performance collection
    perf_doc = await db.performance.find_one_and_update(
        {"student_id": student_oid, "semester": semester},
        {
            "$set": {
                "academic_year": academic_year,
                "attendance": avg_att,
                "classes_held": 100,
                "marks": avg_marks,
                "backlogs": backlogs_count,
                "updated_by": user_oid,
                "updated_at": now,
            },
            "$setOnInsert": {
                "version": 1,
            },
        },
        upsert=True,
        return_document=True,
    )

    # Previous semester marks for trend detection
    prev_perf = await db.performance.find_one({
        "student_id": student_oid,
        "semester": semester - 1,
    })
    prev_marks = prev_perf.get("marks") if prev_perf else None

    # Fetch previous risk level for hysteresis
    prev_risk = await db.risk_results.find_one({"student_id": student_oid, "is_current": True})
    prev_level = prev_risk.get("level") if prev_risk else None

    risk_inputs = {
        "attendance": avg_att,
        "classes_held": 100,
        "marks": avg_marks,
        "prev_marks": prev_marks,
        "backlogs": backlogs_count,
        "assignments": 85.0,
        "engagement": 80.0,
    }

    risk_output = compute_student_risk(inputs=risk_inputs, previous_level=prev_level)

    # Mark existing as not current
    await db.risk_results.update_many(
        {"student_id": student_oid, "is_current": True},
        {"$set": {"is_current": False}},
    )

    new_risk_doc = {
        "student_id": student_oid,
        "performance_id": perf_doc["_id"] if perf_doc else None,
        "score": risk_output["score"],
        "level": risk_output["level"],
        "confidence": risk_output["confidence"],
        "watchlist": risk_output["watchlist"],
        "factors": risk_output["factors"],
        "overrides_applied": risk_output["overrides_applied"],
        "engine_version": risk_output["engine_version"],
        "inputs_hash": risk_output["inputs_hash"],
        "computed_at": now,
        "is_current": True,
    }

    res = await db.risk_results.insert_one(new_risk_doc)
    new_risk_doc["_id"] = res.inserted_id

    # If high risk, trigger counselling workflow
    if risk_output["level"] == "High":
        student_doc = await db.students.find_one({"_id": student_oid})
        if student_doc:
            await counselling_service.handle_high_risk_transition(student_doc, new_risk_doc)


@router.post("/marks/student/{student_id}/subject/{subject_id}", response_model=SubjectMarksResponse)
async def enter_student_subject_marks(
    student_id: str,
    subject_id: str,
    req: MarksEntryRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.HOD, UserRole.ADMIN)),
):
    """
    Enter or update subject marks & attendance for a student.
    Detects pass/fail, flags backlogs, updates semester performance, and recalculates risk score.
    """
    if not ObjectId.is_valid(student_id) or not ObjectId.is_valid(subject_id):
        raise HTTPException(status_code=400, detail="Invalid student or subject ID.")

    db = get_database()
    st_oid = ObjectId(student_id)
    sub_oid = ObjectId(subject_id)

    student = await db.students.find_one({"_id": st_oid})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    subject = await db.subjects.find_one({"_id": sub_oid})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    # Calculate grade & backlog status
    grade = calculate_grade(req.total_marks)
    is_backlog = (req.total_marks < 40.0) or (grade == "F")

    now = datetime.now(UTC)
    user_oid = ObjectId(current_user["_id"])

    marks_data = {
        "student_id": st_oid,
        "subject_id": sub_oid,
        "subject_name": subject["name"],
        "subject_code": subject["code"],
        "semester": req.semester,
        "academic_year": req.academic_year,
        "internal_marks": req.internal_marks,
        "external_marks": req.external_marks,
        "practical_marks": req.practical_marks,
        "assignment_marks": req.assignment_marks,
        "total_marks": req.total_marks,
        "grade": grade,
        "attendance": req.attendance,
        "is_backlog": is_backlog,
        "entered_by": user_oid,
        "updated_at": now,
    }

    doc = await db.subject_marks.find_one_and_update(
        {"student_id": st_oid, "subject_id": sub_oid, "semester": req.semester},
        {"$set": marks_data, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=True,
    )

    # Recalculate semester performance & risk model
    await _recalculate_student_performance_and_risk(
        student_oid=st_oid,
        semester=req.semester,
        academic_year=req.academic_year,
        user_oid=user_oid,
    )

    return _format_marks_response(doc)


@router.get("/marks/student/{student_id}", response_model=list[SubjectMarksResponse])
async def get_student_marks(
    student_id: str,
    semester: int | None = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve all subject marks for a given student."""
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid student ID.")

    db = get_database()
    st_oid = ObjectId(student_id)

    # Security check: student role can only see their own marks
    if current_user.get("role") == UserRole.STUDENT.value:
        student_doc = await db.students.find_one({"user_id": ObjectId(current_user["_id"])})
        if not student_doc or str(student_doc["_id"]) != student_id:
            raise HTTPException(status_code=403, detail="Students can only access their own marks.")

    query: dict[str, Any] = {"student_id": st_oid}
    if semester is not None:
        query["semester"] = semester

    cursor = db.subject_marks.find(query).sort([("semester", -1), ("subject_code", 1)])
    docs = await cursor.to_list(100)
    return [_format_marks_response(d) for d in docs]


@router.get("/marks/student/{student_id}/backlogs", response_model=StudentBacklogSummary)
async def get_student_backlogs(
    student_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Get active backlogs and failed subjects for a student."""
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid student ID.")

    db = get_database()
    st_oid = ObjectId(student_id)
    student = await db.students.find_one({"_id": st_oid})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if current_user.get("role") == UserRole.STUDENT.value:
        if str(student.get("user_id")) != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Students can only access their own backlog report.")

    all_marks = await db.subject_marks.find({"student_id": st_oid}).to_list(200)
    total_subjects = len(all_marks)
    backlogs = [m for m in all_marks if m.get("is_backlog", False)]
    passed_subjects = total_subjects - len(backlogs)

    return StudentBacklogSummary(
        student_id=str(student["_id"]),
        student_name=student["name"],
        total_subjects=total_subjects,
        passed_subjects=max(0, passed_subjects),
        backlog_count=len(backlogs),
        backlog_subjects=[_format_marks_response(b) for b in backlogs],
    )


@router.get("/marks/subject/{subject_id}/students")
async def get_subject_students_with_marks(
    subject_id: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.HOD, UserRole.ADMIN)),
):
    """
    Get all students enrolled in the subject's department/semester with their current marks.
    Enables teachers to view class performance and enter marks quickly.
    """
    if not ObjectId.is_valid(subject_id):
        raise HTTPException(status_code=400, detail="Invalid subject ID.")

    db = get_database()
    sub_oid = ObjectId(subject_id)
    subject = await db.subjects.find_one({"_id": sub_oid})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    # Students matching department and semester
    students_cursor = db.students.find({
        "department": subject["department"],
        "semester": subject["semester"],
    }).sort("name", 1)
    students = await students_cursor.to_list(200)

    results = []
    for s in students:
        s_oid = s["_id"]
        marks_doc = await db.subject_marks.find_one({
            "student_id": s_oid,
            "subject_id": sub_oid,
            "semester": subject["semester"],
        })

        results.append({
            "student_id": str(s_oid),
            "name": s["name"],
            "erp_id": s["erp_id"],
            "semester": s["semester"],
            "batch": s["batch"],
            "marks": _format_marks_response(marks_doc) if marks_doc else None,
        })

    return {
        "subject": {
            "id": str(subject["_id"]),
            "name": subject["name"],
            "code": subject["code"],
            "department": subject["department"],
            "semester": subject["semester"],
        },
        "students": results,
    }


@router.post("/teachers/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def teacher_add_student(
    req: StudentCreateRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.TEACHER, UserRole.HOD, UserRole.ADMIN)),
):
    """
    Allows a Teacher to enroll a new student directly under their mentorship (Section 9).
    Automatically assigns the student to the teacher and creates login account if password provided.
    """
    return await student_service.create_student(
        req=req,
        current_user=current_user,
        client_ip=None,
    )
