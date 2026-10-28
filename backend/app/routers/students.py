from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from backend.app.core.deps import get_current_user, require_role
from backend.app.models.user import UserRole
from backend.app.schemas.hierarchy import (
    BacklogDetailItem,
    SemesterTrendItem,
    StudentPerformanceDashboardResponse,
    SubjectPerformanceItem,
)
from backend.app.schemas.import_job import ImportJobResponse
from backend.app.schemas.performance import PerformanceResponse, PerformanceUpsertRequest
from backend.app.schemas.risk import RiskResultResponse
from backend.app.schemas.student import (
    AssignStudentsRequest,
    FacultyResponse,
    StudentCreateRequest,
    StudentListResponse,
    StudentResponse,
    StudentUpdateRequest,
)
from backend.app.services.import_service import import_service
from backend.app.services.performance_service import performance_service
from backend.app.services.student_service import student_service
from backend.app.risk.service import risk_service
from backend.app.risk.explain import generate_risk_explanation
from backend.app.db.mongo import get_database
from bson import ObjectId

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", response_model=StudentListResponse)
async def list_students(
    cursor: str | None = Query(default=None, description="Cursor for pagination"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    department: str | None = Query(default=None, description="Filter by department"),
    semester: int | None = Query(default=None, ge=1, le=12, description="Filter by semester"),
    status: str | None = Query(default=None, description="Filter by status (active, dropped, etc.)"),
    level: str | None = Query(default=None, description="Filter by risk level"),
    counselling_status: str | None = Query(default=None, description="Filter by counselling status"),
    search: str | None = Query(default=None, description="Search by student name or ERP ID"),
    teacher_id: str | None = Query(default=None, description="Filter by assigned teacher ID (Admin/HOD only)"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    List students with cursor-based pagination and filters.
    Object-level scoped:
    - Admin & HOD: all students (or filtered by department/teacher/query)
    - Teacher: only assigned students
    - Student: self only
    """
    return await student_service.list_students(
        current_user=current_user,
        cursor=cursor,
        limit=limit,
        department=department,
        semester=semester,
        status_filter=status,
        level=level,
        counselling_status=counselling_status,
        search=search,
        teacher_id=teacher_id,
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    req: StudentCreateRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD)),
):
    """Create a new student roster entry (Admin and HOD only)."""
    client_ip = request.client.host if request.client else None
    return await student_service.create_student(
        req=req,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/generate-enrollment-id")
async def generate_enrollment_id(
    department: str | None = Query(default=None, description="Optional department name to derive prefix"),
    batch: str | None = Query(default=None, description="Optional batch cohort to extract admission year"),
    admission_year: str | None = Query(default=None, description="Optional admission year"),
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD, UserRole.TEACHER)),
):
    """
    Generates the next unique Enrollment / ERP ID based on department and cohort.
    Accessible to authenticated staff (Admin, HOD, Teacher).
    """
    next_id = await student_service.generate_enrollment_id(
        department=department,
        batch=batch,
        admission_year=admission_year,
    )
    return {"enrollment_id": next_id, "erp_id": next_id}


@router.get("/faculty", response_model=list[FacultyResponse])
async def list_faculty(
    department: str | None = Query(default=None, description="Optional filter by department"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieve active faculty / teacher accounts for mentorship assignment.
    Includes current assigned student count.
    Accessible to all authenticated staff members.
    """
    db = get_database()
    query: dict[str, Any] = {"role": UserRole.TEACHER.value, "status": "active"}
    if department:
        query["department"] = department
    cursor = db.users.find(query).sort("name", 1)
    faculty_list = await cursor.to_list(100)
    
    results = []
    for u in faculty_list:
        assigned_count = await db.students.count_documents({"assigned_teacher_ids": u["_id"]})
        results.append(
            FacultyResponse(
                id=str(u["_id"]),
                name=u["name"],
                email=u["email"],
                department=u.get("department"),
                role=u["role"],
                assigned_student_count=assigned_count,
            )
        )
    return results


@router.post("/faculty/{teacher_id}/assign-students")
async def assign_students_to_faculty(
    teacher_id: str,
    req: AssignStudentsRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD, UserRole.TEACHER)),
):
    """Assign multiple students to a teacher/faculty mentor (Admin/HOD, or Teacher self-assignment)."""
    from fastapi import HTTPException
    if not ObjectId.is_valid(teacher_id):
        raise HTTPException(status_code=400, detail="Invalid teacher ID.")

    if current_user.get("role") == UserRole.TEACHER.value and str(current_user.get("_id")) != teacher_id:
        raise HTTPException(status_code=403, detail="Teachers can only assign students to their own cohort.")

    teacher_oid = ObjectId(teacher_id)
    student_oids = [ObjectId(sid) for sid in req.student_ids if ObjectId.is_valid(sid)]
    if not student_oids:
        raise HTTPException(status_code=400, detail="No valid student IDs provided.")

    db = get_database()
    res = await db.students.update_many(
        {"_id": {"$in": student_oids}},
        {"$addToSet": {"assigned_teacher_ids": teacher_oid}}
    )
    total_assigned = await db.students.count_documents({"assigned_teacher_ids": teacher_oid})
    return {
        "success": True,
        "modified_count": res.modified_count,
        "total_assigned": total_assigned,
    }


@router.delete("/faculty/{teacher_id}/unassign-student/{student_id}")
async def unassign_student_from_faculty(
    teacher_id: str,
    student_id: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD, UserRole.TEACHER)),
):
    """Unassign/remove a student from a teacher/faculty mentor (Admin/HOD, or Teacher self-unassignment)."""
    from fastapi import HTTPException
    if not ObjectId.is_valid(teacher_id) or not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid teacher or student ID.")

    if current_user.get("role") == UserRole.TEACHER.value and str(current_user.get("_id")) != teacher_id:
        raise HTTPException(status_code=403, detail="Teachers can only unassign students from their own cohort.")

    teacher_oid = ObjectId(teacher_id)
    student_oid = ObjectId(student_id)

    db = get_database()
    res = await db.students.update_one(
        {"_id": student_oid},
        {"$pull": {"assigned_teacher_ids": teacher_oid}}
    )
    total_assigned = await db.students.count_documents({"assigned_teacher_ids": teacher_oid})
    return {
        "success": True,
        "modified_count": res.modified_count,
        "total_assigned": total_assigned,
    }


async def _build_student_performance_dashboard(
    student_doc: dict[str, Any],
) -> StudentPerformanceDashboardResponse:
    """Builds the comprehensive, personalized My Performance dashboard response."""
    db = get_database()
    st_oid = student_doc["_id"]
    st_sem = int(student_doc.get("semester", 1))

    # 1. Fetch all subject marks for this student
    marks_cursor = db.subject_marks.find({"student_id": st_oid}).sort([("semester", 1), ("subject_code", 1)])
    all_marks = await marks_cursor.to_list(200)

    # Current semester marks
    current_sem_marks = [m for m in all_marks if int(m.get("semester", 1)) == st_sem]
    if not current_sem_marks and all_marks:
        latest_sem = max(int(m.get("semester", 1)) for m in all_marks)
        current_sem_marks = [m for m in all_marks if int(m.get("semester", 1)) == latest_sem]

    target_marks = current_sem_marks if current_sem_marks else all_marks
    total_subjects = len(target_marks)
    passed_subjects = sum(1 for m in target_marks if not m.get("is_backlog", False))
    failed_subjects = sum(1 for m in target_marks if m.get("is_backlog", False))
    active_backlogs = sum(1 for m in all_marks if m.get("is_backlog", False))

    if target_marks:
        avg_marks = round(sum(float(m.get("total_marks", 0.0)) for m in target_marks) / len(target_marks), 1)
        avg_att = round(sum(float(m.get("attendance", 100.0)) for m in target_marks) / len(target_marks), 1)
    else:
        avg_marks = 0.0
        avg_att = 100.0

    cgpa = round(avg_marks / 10.0, 2)

    # 2. Risk result
    risk_doc = await db.risk_results.find_one({"student_id": st_oid, "is_current": True})
    risk_level = risk_doc.get("level", "Low") if risk_doc else "Low"
    risk_score = risk_doc.get("score") if risk_doc else None
    raw_factors = risk_doc.get("factors", []) if risk_doc else []

    # 3. Subject-wise performance items
    subject_items = []
    attendance_warnings = []
    for m in target_marks:
        score = float(m.get("total_marks", 0.0))
        att = float(m.get("attendance", 100.0))
        is_back = bool(m.get("is_backlog", False))
        sub_name = m.get("subject_name", "Subject")

        if is_back:
            status_desc = "Backlog"
        elif score >= 75.0:
            status_desc = "Strong"
        elif score >= 50.0:
            status_desc = "Average"
        else:
            status_desc = "Weak"

        has_att_warn = att < 75.0
        if has_att_warn:
            attendance_warnings.append(
                f"Your attendance in {sub_name} is {att}%. Improve attendance to reduce academic risk."
            )

        subject_items.append(
            SubjectPerformanceItem(
                subject_id=str(m.get("subject_id")),
                subject_name=sub_name,
                subject_code=m.get("subject_code", "SUB"),
                semester=int(m.get("semester", st_sem)),
                marks=score,
                grade=m.get("grade", "F"),
                attendance=att,
                is_backlog=is_back,
                status=status_desc,
                attendance_warning=has_att_warn,
            )
        )

    if avg_att < 75.0 and not any("Overall" in w for w in attendance_warnings):
        attendance_warnings.insert(
            0,
            f"Overall attendance ({avg_att}%) is below mandatory 75% university policy.",
        )

    # 4. Historical Trend
    perf_cursor = db.performance.find({"student_id": st_oid}).sort("semester", 1)
    perfs = await perf_cursor.to_list(50)
    historical_trend = []
    for p in perfs:
        historical_trend.append(
            SemesterTrendItem(
                semester=int(p.get("semester", 1)),
                academic_year=p.get("academic_year", "2024-25"),
                marks=float(p.get("marks", 0.0)),
                attendance=float(p.get("attendance", 100.0)),
                backlogs=int(p.get("backlogs", 0)),
            )
        )

    # Trend direction
    if len(historical_trend) >= 2:
        diff = historical_trend[-1].marks - historical_trend[-2].marks
        if diff >= 2.0:
            trend_direction = "Improving"
        elif diff <= -2.0:
            trend_direction = "Declining"
        else:
            trend_direction = "Stable"
    else:
        trend_direction = "Stable"

    # 5. Backlogs details
    backlog_items = []
    backlog_docs = [m for m in all_marks if m.get("is_backlog", False)]
    for b in backlog_docs:
        b_marks = float(b.get("total_marks", 0.0))
        priority = "HIGH" if b_marks < 35.0 or len(backlog_docs) >= 2 else "MEDIUM"
        backlog_items.append(
            BacklogDetailItem(
                subject_id=str(b.get("subject_id")),
                subject_name=b.get("subject_name", "Subject"),
                subject_code=b.get("subject_code", "SUB"),
                previous_marks=b_marks,
                status="Backlog",
                priority=priority,
                action_advice="Practice previous-year question papers & dedicate 1.5 daily hours to core topics.",
            )
        )

    # 6. Actionable recommendations
    recommendations = []
    weak_or_back = [s for s in subject_items if s.status in ("Backlog", "Weak")]
    for w in weak_or_back[:2]:
        recommendations.append(f"Give 1.5 to 2 hours daily study time to {w.subject_name} ({w.marks}/100).")
    for att_w in subject_items:
        if att_w.attendance_warning:
            recommendations.append(f"Attend next 10 consecutive lectures in {att_w.subject_name} to raise attendance above 75%.")
    if active_backlogs > 0:
        recommendations.append("Solve previous 3 years' university question papers for backlog clearance.")
    recommendations.append("Complete and submit upcoming assignments before deadlines for internal assessment boost.")
    recommendations.append("Schedule a 1-on-1 mentorship session with your faculty mentor to clarify concept bottlenecks.")

    return StudentPerformanceDashboardResponse(
        student_id=str(student_doc["_id"]),
        student_name=student_doc.get("name", "Student"),
        erp_id=student_doc.get("erp_id", "N/A"),
        department=student_doc.get("department", "Engineering"),
        semester=st_sem,
        batch=student_doc.get("batch", "2024"),
        course=student_doc.get("course", "B.Tech"),
        average_marks=avg_marks,
        cgpa=cgpa,
        overall_attendance=avg_att,
        total_subjects=total_subjects,
        passed_subjects=passed_subjects,
        failed_subjects=failed_subjects,
        active_backlogs=active_backlogs,
        current_risk_level=risk_level,
        risk_score=risk_score,
        subjects=subject_items,
        historical_trend=historical_trend,
        trend_direction=trend_direction,
        attendance_warnings=attendance_warnings,
        backlogs_list=backlog_items,
        risk_factors=raw_factors,
        recommendations=recommendations,
    )


@router.get("/me/performance-dashboard", response_model=StudentPerformanceDashboardResponse)
async def get_my_performance_dashboard(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Dedicated My Performance Dashboard endpoint for the logged-in Student (Sections 1-9).
    Strict backend authorization:
    - Looks up the student profile linked to current_user['_id'].
    - Enforces that a student can ONLY view their own database records.
    """
    if current_user.get("role") != UserRole.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff should use /students/{student_id}/performance-dashboard.",
        )

    db = get_database()
    user_oid = ObjectId(current_user["_id"])
    student_doc = await db.students.find_one({"user_id": user_oid})
    if not student_doc:
        # Fallback: lookup by email, canonical_email, aliases, or name
        user_email = (current_user.get("email") or "").lower()
        canonical = (current_user.get("canonical_email") or "").lower()
        aliases = [a.lower() for a in current_user.get("aliases", []) if a]
        email_candidates = list({e for e in [user_email, canonical, *aliases] if e})

        query_or: list[dict[str, Any]] = [{"institutional_email": {"$in": email_candidates}}]
        user_name = current_user.get("name", "").strip()
        if user_name:
            query_or.append({"name": {"$regex": f"^{re.escape(user_name)}$", "$options": "i"}})

        student_doc = await db.students.find_one({"$or": query_or})
        if student_doc:
            await db.students.update_one(
                {"_id": student_doc["_id"]},
                {"$set": {"user_id": user_oid, "institutional_email": user_email or student_doc.get("institutional_email")}}
            )

    if not student_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile record not found.",
        )

    return await _build_student_performance_dashboard(student_doc)


@router.get("/{student_id}/performance-dashboard", response_model=StudentPerformanceDashboardResponse)
async def get_student_performance_dashboard(
    student_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieve performance dashboard for a student by ID.
    Strict object-level access:
    - Students can ONLY access their own record (403 otherwise).
    - Teachers can only access students assigned to them.
    - HOD and Admin can access students within their scope.
    """
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid student ID format.")

    db = get_database()
    st_oid = ObjectId(student_id)
    student_doc = await db.students.find_one({"_id": st_oid})
    if not student_doc:
        raise HTTPException(status_code=404, detail="Student not found.")

    user_role = current_user.get("role")
    user_id = str(current_user.get("_id"))

    if user_role == UserRole.STUDENT.value:
        owner_user_id = str(student_doc.get("user_id")) if student_doc.get("user_id") else None
        if owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students are not permitted to access other students' performance.",
            )
    elif user_role == UserRole.TEACHER.value:
        assigned_teachers = [str(t) for t in student_doc.get("assigned_teacher_ids", [])]
        if user_id not in assigned_teachers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers may only access performance for assigned mentorship students.",
            )

    return await _build_student_performance_dashboard(student_doc)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Get student details.
    Object-level scoped:
    - Admin & HOD: allowed
    - Teacher: assigned students only (403 if unassigned)
    - Student: self only (403 and audited if accessing another student)
    """
    client_ip = request.client.host if request.client else None
    return await student_service.get_student(
        student_id=student_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    req: StudentUpdateRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD)),
):
    """Update student metadata (Admin and HOD only). Audits department transfers & status changes."""
    client_ip = request.client.host if request.client else None
    return await student_service.update_student(
        student_id=student_id,
        req=req,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.put("/{student_id}/performance/{semester}", response_model=PerformanceResponse)
async def upsert_student_performance(
    student_id: str,
    semester: int,
    req: PerformanceUpsertRequest,
    request: Request,
    if_match: str | None = Header(default=None, alias="If-Match"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Record or update student semester performance with optimistic concurrency check.
    Requires If-Match header matching current version on updates.
    Returns 409 Conflict if record was modified concurrently.
    """
    client_ip = request.client.host if request.client else None
    return await performance_service.upsert_performance(
        student_id=student_id,
        semester=semester,
        req=req,
        if_match_header=if_match,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("/{student_id}/performance/{semester}", response_model=PerformanceResponse)
async def get_student_performance(
    student_id: str,
    semester: int,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve performance record for a student in a semester."""
    return await performance_service.get_student_performance(
        student_id=student_id,
        semester=semester,
        current_user=current_user,
    )


@router.post("/import", response_model=ImportJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_students(
    request: Request,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD)),
):
    """
    Bulk import students and performance data from CSV or XLSX.
    Runs asynchronously and returns import job status.
    """
    client_ip = request.client.host if request.client else None
    file_bytes = await file.read()
    filename = file.filename or "import.csv"

    job_id = await import_service.create_import_job(file=file, current_user=current_user)

    # Execute processing
    # In test/synchronous mode or background mode:
    # We can process directly or schedule via background_tasks.
    # To return immediate 202 with job progress available via /imports/{id}:
    background_tasks.add_task(
        import_service.process_file,
        job_id=job_id,
        file_bytes=file_bytes,
        filename=filename,
        current_user=current_user,
        client_ip=client_ip,
    )

    return await import_service.get_import_job(job_id=job_id, current_user=current_user)


@router.get("/{student_id}/risk", response_model=RiskResultResponse)
async def get_student_risk(
    student_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves the current risk score, factors, overrides, and explanation for a student.
    Enforces object-level scoping (Admin/HOD: any; Teacher: assigned only; Student: self only).
    """
    client_ip = request.client.host if request.client else None
    # Verifies object-level authorization and existence
    await student_service.get_student(student_id=student_id, current_user=current_user, client_ip=client_ip)

    db = get_database()
    student_oid = ObjectId(student_id)
    risk_doc = await db.risk_results.find_one({"student_id": student_oid, "is_current": True})
    if not risk_doc:
        risk_doc = await risk_service.recompute_student_risk(student_id=student_oid)

    if not risk_doc:
        risk_doc = {
            "_id": ObjectId(),
            "student_id": student_oid,
            "performance_id": None,
            "score": None,
            "level": "Insufficient Data",
            "confidence": 0.0,
            "watchlist": False,
            "factors": [],
            "overrides_applied": [],
            "engine_version": "1.0.0",
            "inputs_hash": "",
            "computed_at": datetime.now(),
            "is_current": True,
        }

    explanation_pkg = generate_risk_explanation(
        score=risk_doc.get("score"),
        level=risk_doc.get("level"),
        confidence=risk_doc.get("confidence", 0.0),
        factors=risk_doc.get("factors", []),
        overrides_applied=risk_doc.get("overrides_applied", []),
        watchlist=risk_doc.get("watchlist", False),
    )

    return RiskResultResponse(
        id=str(risk_doc["_id"]),
        student_id=str(risk_doc["student_id"]),
        performance_id=str(risk_doc["performance_id"]) if risk_doc.get("performance_id") else None,
        score=risk_doc.get("score"),
        level=risk_doc.get("level"),
        confidence=risk_doc.get("confidence", 0.0),
        watchlist=risk_doc.get("watchlist", False),
        factors=risk_doc.get("factors", []),
        overrides_applied=risk_doc.get("overrides_applied", []),
        engine_version=risk_doc.get("engine_version", "1.0.0"),
        inputs_hash=risk_doc.get("inputs_hash", ""),
        computed_at=risk_doc.get("computed_at", datetime.now()),
        is_current=risk_doc.get("is_current", True),
        explanation_summary=explanation_pkg.get("summary"),
        decision_support_advisory="Risk assessments are advisory decision support and do not constitute automated decisions.",
    )


@router.get("/{student_id}/export-data")
async def export_student_data(
    student_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    FERPA / India DPDP Article 11 Data Portability Export.
    Exports all stored student demographics, academic performances, risk history, counselling records, and audit events.
    Allowed for Admin, HOD, assigned Teacher, or self-student.
    """
    client_ip = request.client.host if request.client else None
    return await student_service.export_student_data(
        student_id=student_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.delete("/{student_id}")
async def delete_and_anonymize_student(
    student_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    """
    Right to Erasure / Soft Anonymization (Admin only).
    Anonymizes student identifiers and marks status as dropped while retaining de-identified cohort analytics.
    """
    client_ip = request.client.host if request.client else None
    return await student_service.anonymize_and_delete_student(
        student_id=student_id,
        current_user=current_user,
        client_ip=client_ip,
    )


