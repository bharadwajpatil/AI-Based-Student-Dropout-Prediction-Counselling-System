from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from backend.app.counselling.schemas import (
    CounsellingListResponse,
    CounsellingNoteCreate,
    CounsellingNoteResponse,
    CounsellingResponse,
    CounsellingUpdate,
)
from backend.app.schemas.hierarchy import (
    AIChatRequest,
    AIChatResponse,
    StudyPlanResponse,
)
from backend.app.core.deps import get_current_user
from backend.app.counselling.service import counselling_service
from backend.app.models.counselling import AISource, CounsellingStatus
from backend.app.models.user import UserRole

router = APIRouter(prefix="/counselling", tags=["Counselling"])


class GenerateCounsellingRequest(BaseModel):
    force_regenerate: bool = False
    teacher_notes: str | None = Field(default=None, max_length=5000)


def _serialize_counselling_doc(doc: dict[str, Any]) -> CounsellingResponse:
    """Helper to convert MongoDB counselling document into CounsellingResponse."""
    raw_timeline = doc.get("notes_timeline", [])
    timeline_responses = []
    for note in raw_timeline:
        timeline_responses.append(
            CounsellingNoteResponse(
                id=str(note.get("id")),
                author_id=str(note.get("author_id")),
                author_name=str(note.get("author_name", "Unknown")),
                author_role=str(note.get("author_role", "teacher")),
                content=str(note.get("content", "")),
                created_at=note.get("created_at"),
            )
        )

    ai_source_val = doc.get("ai_source", "template")
    try:
        ai_source = AISource(ai_source_val)
    except ValueError:
        ai_source = AISource.TEMPLATE

    status_val = doc.get("status", "pending")
    try:
        c_status = CounsellingStatus(status_val)
    except ValueError:
        c_status = CounsellingStatus.PENDING

    return CounsellingResponse(
        id=str(doc["_id"]),
        student_id=str(doc["student_id"]),
        teacher_id=str(doc["teacher_id"]) if doc.get("teacher_id") else None,
        risk_result_id=str(doc["risk_result_id"]),
        risk_level=str(doc.get("risk_level", "Medium")),
        status=c_status,
        summary=str(doc.get("summary", doc.get("ai_recommendation", ""))),
        actions=list(doc.get("actions", [])),
        follow_up_in_days=int(doc.get("follow_up_in_days", 7)),
        follow_up_date=doc.get("follow_up_date"),
        escalate_to_hod=bool(doc.get("escalate_to_hod", False)),
        refer_to_counsellor=bool(doc.get("refer_to_counsellor", False)),
        ai_source=ai_source,
        ai_recommendation=str(doc.get("ai_recommendation", "")),
        is_outdated=bool(doc.get("is_outdated", False)),
        risk_computed_at=doc.get("risk_computed_at"),
        notes_timeline=timeline_responses,
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.get("", response_model=CounsellingListResponse)
async def list_counselling_cases(
    status: str | None = Query(default=None, description="Filter by case status (pending, in_progress, follow_up, resolved)"),
    student_id: str | None = Query(default=None, description="Filter by student ID"),
    teacher_id: str | None = Query(default=None, description="Filter by teacher ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    List counselling cases.
    - Teachers only see cases for students assigned to them.
    - HOD and Admin see all cases.
    - Students only see their own cases.
    """
    items, total = await counselling_service.list_counselling(
        user=current_user,
        status_filter=status,
        student_id=student_id,
        teacher_id=teacher_id,
        skip=skip,
        limit=limit,
    )
    serialized = [_serialize_counselling_doc(d) for d in items]
    return CounsellingListResponse(items=serialized, total=total, skip=skip, limit=limit)


@router.get("/{id}", response_model=CounsellingResponse)
async def get_counselling_by_id(
    id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get detailed counselling case including full notes timeline.
    Enforces object-level access control.
    """
    doc = await counselling_service.get_counselling_by_id(counselling_id=id, user=current_user)
    return _serialize_counselling_doc(doc)


@router.get("/student/{student_id}", response_model=CounsellingResponse)
async def get_counselling_by_student_id(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get the active counselling case for a specific student.
    """
    doc = await counselling_service.get_counselling_by_student_id(student_id=student_id, user=current_user)
    return _serialize_counselling_doc(doc)


@router.post("/student/{student_id}/generate", response_model=CounsellingResponse, status_code=status.HTTP_200_OK)
async def generate_counselling_for_student(
    student_id: str,
    body: GenerateCounsellingRequest = GenerateCounsellingRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate or retrieve counselling recommendation for a student.
    - Uses cached recommendation if risk factors are unchanged (inputs_hash match).
    - Can force regeneration by setting force_regenerate=True.
    - Automatically falls back to template on Gemini timeout / quota / error.
    """
    doc = await counselling_service.generate_recommendation_for_student(
        student_id=student_id,
        user=current_user,
        force_regenerate=body.force_regenerate,
        teacher_notes=body.teacher_notes,
    )
    return _serialize_counselling_doc(doc)


@router.post("/{id}/notes", response_model=CounsellingResponse, status_code=status.HTTP_201_CREATED)
async def add_counselling_note(
    id: str,
    note_in: CounsellingNoteCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Append a note to the counselling case timeline.
    Enforces append-only atomic concurrency ($push) to avoid lost updates.
    Automatically flags crisis/self-harm signals to HOD.
    """
    doc = await counselling_service.add_timeline_note(
        counselling_id=id,
        user=current_user,
        note_in=note_in,
    )
    return _serialize_counselling_doc(doc)


@router.patch("/{id}", response_model=CounsellingResponse)
async def update_counselling_case(
    id: str,
    update_in: CounsellingUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update counselling case status, follow-up date, or escalation flags.
    """
    doc = await counselling_service.update_counselling_case(
        counselling_id=id,
        user=current_user,
        update_in=update_in,
    )
    return _serialize_counselling_doc(doc)


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_academic_counsellor(
    req: AIChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Interactive Academic AI Counsellor Chatbot (Sections 15 & 16).
    Uses the student's actual MongoDB academic records (marks, attendance, backlogs, risk).
    Accessible to Students, Teachers, HOD, and Admin.
    """
    from bson import ObjectId
    from backend.app.counselling.chatbot_service import chatbot_service
    from backend.app.db.mongo import get_database

    db = get_database()
    target_student_id = req.student_id

    # If student is logged in, use their linked student document
    if current_user.get("role") == UserRole.STUDENT.value:
        student_doc = await db.students.find_one({"user_id": ObjectId(current_user["_id"])})
        if student_doc:
            target_student_id = str(student_doc["_id"])
        else:
            raise HTTPException(status_code=404, detail="Student profile record not found.")
    elif not target_student_id:
        # Default to first student if staff did not provide
        sample = await db.students.find_one({})
        if sample:
            target_student_id = str(sample["_id"])
        else:
            raise HTTPException(status_code=400, detail="Student ID required for counselling consultation.")

    history_payload = [{"role": m.role, "content": m.content} for m in req.conversation_history]
    return await chatbot_service.chat(
        student_id=target_student_id,
        message=req.message,
        conversation_history=history_payload,
    )


@router.post("/student/{student_id}/study-plan", response_model=StudyPlanResponse)
async def generate_study_plan_for_student(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Generates a personalized 7-Day Study Plan and Backlog Improvement Plans (Sections 17 & 18).
    Persists plan in MongoDB study_plans collection.
    """
    from bson import ObjectId
    from fastapi import HTTPException, status
    from backend.app.counselling.chatbot_service import chatbot_service
    from backend.app.db.mongo import get_database

    db = get_database()
    try:
        st_oid = ObjectId(student_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student ID format.")

    student_doc = await db.students.find_one({"_id": st_oid})
    if not student_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    user_role = current_user.get("role")
    if user_role == UserRole.STUDENT.value:
        if str(student_doc.get("user_id")) != str(current_user.get("_id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only generate their own study plan.")
    elif user_role == UserRole.TEACHER.value:
        assigned = [str(t) for t in student_doc.get("assigned_teacher_ids", [])]
        if str(current_user.get("_id")) not in assigned:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teachers can only generate study plans for their assigned students.")

    return await chatbot_service.generate_or_get_study_plan(student_id=student_id)


@router.get("/student/{student_id}/study-plan", response_model=StudyPlanResponse)
async def get_study_plan_for_student(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve the current persistent personalized study plan for a student."""
    from bson import ObjectId
    from fastapi import HTTPException, status
    from backend.app.counselling.chatbot_service import chatbot_service
    from backend.app.db.mongo import get_database

    db = get_database()
    try:
        st_oid = ObjectId(student_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student ID format.")

    student_doc = await db.students.find_one({"_id": st_oid})
    if not student_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    user_role = current_user.get("role")
    if user_role == UserRole.STUDENT.value:
        if str(student_doc.get("user_id")) != str(current_user.get("_id")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only access their own study plan.")
    elif user_role == UserRole.TEACHER.value:
        assigned = [str(t) for t in student_doc.get("assigned_teacher_ids", [])]
        if str(current_user.get("_id")) not in assigned:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teachers can only access study plans for their assigned students.")

    return await chatbot_service.generate_or_get_study_plan(student_id=student_id)

