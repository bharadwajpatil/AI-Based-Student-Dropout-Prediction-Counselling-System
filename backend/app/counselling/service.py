import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from backend.app.core.clock import Clock, SystemClock
from backend.app.core.config import settings
from backend.app.counselling.client import GeminiClient, GeminiError
from backend.app.counselling.fallback import generate_template_recommendation
from backend.app.counselling.guardrails import detect_crisis
from backend.app.counselling.prompt import build_counselling_user_prompt
from backend.app.counselling.schemas import (
    AICounsellingRecommendation,
    CounsellingNoteCreate,
    CounsellingResponse,
    CounsellingUpdate,
)
from backend.app.db.mongo import get_database
from backend.app.models.counselling import AISource, CounsellingStatus
from backend.app.models.user import UserInDB, UserRole

logger = logging.getLogger("student-dropout-system.counselling.service")


class CounsellingService:
    """
    Manages AI-driven counselling recommendation generation, caching,
    timeline notes append, workflow status transitions, and role-based access.
    """

    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.clock = clock or SystemClock()
        self.gemini_client = gemini_client or GeminiClient(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )

    def _get_db(self):
        return get_database()

    @staticmethod
    def _extract_user_info(user: Any) -> tuple[str, str, str]:
        """Extracts (user_id, role, name) whether user is dict or UserInDB."""
        if isinstance(user, dict):
            u_id = str(user.get("_id"))
            role = user.get("role")
            if hasattr(role, "value"):
                role = role.value
            name = str(user.get("name", "User"))
            return u_id, str(role), name
        else:
            role = user.role.value if hasattr(user.role, "value") else str(user.role)
            return str(user.id), role, str(user.name)

    async def _verify_access(self, student_doc: dict[str, Any], user: Any, is_write: bool = False) -> None:
        """Enforces object-level RBAC for student counselling records."""
        user_id, role, _ = self._extract_user_info(user)

        if role in (UserRole.HOD.value, UserRole.ADMIN.value):
            return

        if role == UserRole.TEACHER.value:
            assigned = [str(t) for t in student_doc.get("assigned_teacher_ids", [])]
            if user_id not in assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to view or manage counselling for this student.",
                )
            return

        if role == UserRole.STUDENT.value:
            if is_write:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Students cannot modify counselling cases or records.",
                )
            # Student can only read their own record
            if str(student_doc.get("user_id")) != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own counselling records.",
                )
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized role.",
        )


    async def generate_recommendation_for_student(
        self,
        student_id: str,
        user: Any,
        force_regenerate: bool = False,
        teacher_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Generates or retrieves cached counselling recommendation for a student.
        Falls back smoothly to template on any AI failure.
        """
        db = self._get_db()
        try:
            student_oid = ObjectId(student_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student ID format.")

        student = await db.students.find_one({"_id": student_oid})
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

        await self._verify_access(student, user, is_write=True)

        current_risk = await db.risk_results.find_one({"student_id": student_oid, "is_current": True})
        if not current_risk:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No current risk evaluation found for student. Cannot generate counselling.",
            )

        # Check existing counselling case
        existing_counselling = await db.counselling.find_one({"student_id": student_oid})

        # Caching check: if inputs_hash matches and not force_regenerate, return existing
        current_hash = current_risk.get("inputs_hash")
        if (
            existing_counselling
            and not force_regenerate
            and existing_counselling.get("inputs_hash") == current_hash
            and existing_counselling.get("summary")
        ):
            logger.info("Serving cached counselling recommendation for student %s (hash match)", student_id)
            return existing_counselling

        # Build prompt with PII minimization
        prompt = build_counselling_user_prompt(
            student_id=student_id,
            department=student.get("department", "General"),
            semester=student.get("semester", 1),
            risk_level=current_risk.get("level", "Medium"),
            risk_score=current_risk.get("score", 50.0),
            factors=current_risk.get("factors", []),
            teacher_notes=teacher_notes,
        )

        rec: AICounsellingRecommendation
        ai_source: AISource

        try:
            rec = await self.gemini_client.generate_counselling(prompt)
            ai_source = AISource.GEMINI
        except GeminiError as exc:
            logger.warning(
                "Gemini AI generation failed (%s: %s). Falling back to template recommendation.",
                type(exc).__name__,
                exc,
            )
            rec = generate_template_recommendation(
                risk_level=current_risk.get("level", "Medium"),
                score=current_risk.get("score", 50.0),
                factors=current_risk.get("factors", []),
                teacher_notes=teacher_notes,
            )
            ai_source = AISource.TEMPLATE
        except Exception as unhandled_exc:
            logger.exception("Unexpected error during AI generation; using template fallback.")
            rec = generate_template_recommendation(
                risk_level=current_risk.get("level", "Medium"),
                score=current_risk.get("score", 50.0),
                factors=current_risk.get("factors", []),
                teacher_notes=teacher_notes,
            )
            ai_source = AISource.TEMPLATE

        # Guardrails check for teacher notes crisis signals
        if detect_crisis(teacher_notes):
            rec = rec.model_copy(update={"escalate_to_hod": True, "refer_to_counsellor": True})

        now = self.clock.now()
        assigned_teachers = student.get("assigned_teacher_ids", [])
        primary_teacher = assigned_teachers[0] if assigned_teachers else None

        counselling_data = {
            "student_id": student_oid,
            "teacher_id": primary_teacher,
            "risk_result_id": current_risk["_id"],
            "risk_level": current_risk["level"],
            "summary": rec.summary,
            "actions": rec.actions,
            "follow_up_in_days": rec.follow_up_in_days,
            "escalate_to_hod": rec.escalate_to_hod,
            "refer_to_counsellor": rec.refer_to_counsellor,
            "ai_source": ai_source.value,
            "ai_recommendation": rec.summary,
            "inputs_hash": current_hash,
            "updated_at": now,
        }

        if existing_counselling:
            await db.counselling.update_one(
                {"_id": existing_counselling["_id"]},
                {"$set": counselling_data},
            )
            updated_doc = await db.counselling.find_one({"_id": existing_counselling["_id"]})
            return updated_doc
        else:
            counselling_data["status"] = CounsellingStatus.PENDING.value
            counselling_data["notes"] = ""
            counselling_data["notes_timeline"] = []
            counselling_data["follow_up_date"] = None
            counselling_data["created_at"] = now
            res = await db.counselling.insert_one(counselling_data)
            counselling_data["_id"] = res.inserted_id
            return counselling_data

    async def get_counselling_by_id(self, counselling_id: str, user: Any) -> dict[str, Any]:
        """Retrieves single counselling record with access control and outdated check."""
        db = self._get_db()
        try:
            c_oid = ObjectId(counselling_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid counselling ID format.")

        counselling = await db.counselling.find_one({"_id": c_oid})
        if not counselling:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counselling record not found.")

        student = await db.students.find_one({"_id": counselling["student_id"]})
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

        await self._verify_access(student, user, is_write=False)

        # Check if recommendation is outdated
        current_risk = await db.risk_results.find_one({"student_id": student["_id"], "is_current": True})
        is_outdated = False
        risk_computed_at = None
        if current_risk:
            risk_computed_at = current_risk.get("computed_at")
            if str(current_risk.get("_id")) != str(counselling.get("risk_result_id")):
                is_outdated = True

        counselling["is_outdated"] = is_outdated
        counselling["risk_computed_at"] = risk_computed_at
        return counselling

    async def get_counselling_by_student_id(self, student_id: str, user: Any) -> dict[str, Any]:
        """Retrieves the active or latest counselling record for a student."""
        db = self._get_db()
        try:
            s_oid = ObjectId(student_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student ID format.")

        student = await db.students.find_one({"_id": s_oid})
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

        await self._verify_access(student, user, is_write=False)

        counselling = await db.counselling.find_one({"student_id": s_oid})
        if not counselling:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No counselling record found for student.")

        current_risk = await db.risk_results.find_one({"student_id": s_oid, "is_current": True})
        is_outdated = False
        risk_computed_at = None
        if current_risk:
            risk_computed_at = current_risk.get("computed_at")
            if str(current_risk.get("_id")) != str(counselling.get("risk_result_id")):
                is_outdated = True

        counselling["is_outdated"] = is_outdated
        counselling["risk_computed_at"] = risk_computed_at
        return counselling

    async def list_counselling(
        self,
        user: Any,
        status_filter: str | None = None,
        student_id: str | None = None,
        teacher_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:

        """Lists counselling records with pagination and strict RBAC scoping."""
        db = self._get_db()
        query: dict[str, Any] = {}

        if status_filter:
            query["status"] = status_filter

        if student_id:
            try:
                query["student_id"] = ObjectId(student_id)
            except Exception:
                return [], 0

        if teacher_id:
            try:
                query["teacher_id"] = ObjectId(teacher_id)
            except Exception:
                return [], 0

        user_id, role, name = self._extract_user_info(user)

        # Teacher scoping: only assigned students
        if role == UserRole.TEACHER.value:
            assigned_cursor = db.students.find(
                {"assigned_teacher_ids": ObjectId(user_id)},
                {"_id": 1},
            )
            assigned_ids = [s["_id"] async for s in assigned_cursor]
            if "student_id" in query:
                if query["student_id"] not in assigned_ids:
                    return [], 0
            else:
                query["student_id"] = {"$in": assigned_ids}
        elif role == UserRole.STUDENT.value:
            # Student can only view their own
            student_doc = await db.students.find_one({"user_id": ObjectId(user_id)}, {"_id": 1})
            if not student_doc:
                return [], 0
            query["student_id"] = student_doc["_id"]

        total = await db.counselling.count_documents(query)
        cursor = db.counselling.find(query).skip(skip).limit(limit)
        items = [doc async for doc in cursor]

        return items, total

    async def add_timeline_note(
        self,
        counselling_id: str,
        user: Any,
        note_in: CounsellingNoteCreate,
    ) -> dict[str, Any]:
        """Appends a new note entry to the case timeline with concurrent safety."""
        db = self._get_db()
        try:
            c_oid = ObjectId(counselling_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid counselling ID format.")

        counselling = await db.counselling.find_one({"_id": c_oid})
        if not counselling:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counselling record not found.")

        student = await db.students.find_one({"_id": counselling["student_id"]})
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

        # Students cannot write notes
        await self._verify_access(student, user, is_write=True)

        user_id, role, name = self._extract_user_info(user)
        now = self.clock.now()
        new_note = {
            "id": str(uuid.uuid4()),
            "author_id": ObjectId(user_id),
            "author_name": name,
            "author_role": role,
            "content": note_in.content,
            "created_at": now,
        }


        update_ops: dict[str, Any] = {
            "$push": {"notes_timeline": new_note},
            "$set": {"updated_at": now},
        }

        # Check for crisis signals in the new note
        if detect_crisis(note_in.content):
            logger.warning("Crisis signals detected in faculty note for counselling case %s", counselling_id)
            update_ops["$set"]["escalate_to_hod"] = True
            update_ops["$set"]["refer_to_counsellor"] = True

        await db.counselling.update_one({"_id": c_oid}, update_ops)
        updated = await db.counselling.find_one({"_id": c_oid})
        return updated

    async def update_counselling_case(
        self,
        counselling_id: str,
        user: Any,
        update_in: CounsellingUpdate,
    ) -> dict[str, Any]:
        """Updates counselling workflow status, escalation flags, or follow-up date."""
        db = self._get_db()
        try:
            c_oid = ObjectId(counselling_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid counselling ID format.")

        counselling = await db.counselling.find_one({"_id": c_oid})
        if not counselling:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counselling record not found.")

        student = await db.students.find_one({"_id": counselling["student_id"]})
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

        await self._verify_access(student, user, is_write=True)

        set_fields: dict[str, Any] = {"updated_at": self.clock.now()}

        if update_in.status is not None:
            set_fields["status"] = update_in.status.value
        if update_in.follow_up_date is not None:
            set_fields["follow_up_date"] = update_in.follow_up_date
        if update_in.escalate_to_hod is not None:
            set_fields["escalate_to_hod"] = update_in.escalate_to_hod
        if update_in.refer_to_counsellor is not None:
            set_fields["refer_to_counsellor"] = update_in.refer_to_counsellor

        await db.counselling.update_one({"_id": c_oid}, {"$set": set_fields})
        updated = await db.counselling.find_one({"_id": c_oid})
        return updated

    async def handle_high_risk_transition(
        self,
        student: dict[str, Any],
        risk_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handles automatic counselling workflow triggers when student transitions to High risk.
        Reopens resolved cases automatically (Scenario S14), or creates pending case (Scenario S1).
        """
        db = self._get_db()
        student_oid = student["_id"]
        now = self.clock.now()

        existing_counselling = await db.counselling.find_one({"student_id": student_oid})

        # Generate rule-based or AI recommendation for this high risk state
        rec = generate_template_recommendation(
            risk_level=risk_result["level"],
            score=risk_result["score"],
            factors=risk_result.get("factors", []),
        )

        assigned_teachers = student.get("assigned_teacher_ids", [])
        primary_teacher = assigned_teachers[0] if assigned_teachers else None

        if existing_counselling:
            # Scenario S14: Resolved case reopens as pending when risk rises
            if existing_counselling.get("status") == CounsellingStatus.RESOLVED.value:
                reopen_note = {
                    "id": str(uuid.uuid4()),
                    "author_id": ObjectId(student_oid),
                    "author_name": "System",
                    "author_role": "system",
                    "content": f"Case automatically reopened: Student risk evaluated at High ({risk_result['score']:.1f}/100).",
                    "created_at": now,
                }
                update_fields = {
                    "status": CounsellingStatus.PENDING.value,
                    "risk_result_id": risk_result["_id"],
                    "risk_level": risk_result["level"],
                    "summary": rec.summary,
                    "actions": rec.actions,
                    "follow_up_in_days": rec.follow_up_in_days,
                    "escalate_to_hod": rec.escalate_to_hod,
                    "inputs_hash": risk_result.get("inputs_hash"),
                    "updated_at": now,
                }
                await db.counselling.update_one(
                    {"_id": existing_counselling["_id"]},
                    {
                        "$set": update_fields,
                        "$push": {"notes_timeline": reopen_note},
                    },
                )
                logger.info("Automatically reopened resolved counselling case for student %s", student_oid)
            else:
                # Active case: refresh risk result id and inputs hash
                await db.counselling.update_one(
                    {"_id": existing_counselling["_id"]},
                    {
                        "$set": {
                            "risk_result_id": risk_result["_id"],
                            "risk_level": risk_result["level"],
                            "summary": rec.summary,
                            "actions": rec.actions,
                            "inputs_hash": risk_result.get("inputs_hash"),
                            "updated_at": now,
                        }
                    },
                )
            return await db.counselling.find_one({"_id": existing_counselling["_id"]})

        # No case exists: create new pending case
        new_case = {
            "student_id": student_oid,
            "teacher_id": primary_teacher,
            "risk_result_id": risk_result["_id"],
            "risk_level": risk_result["level"],
            "summary": rec.summary,
            "actions": rec.actions,
            "follow_up_in_days": rec.follow_up_in_days,
            "escalate_to_hod": rec.escalate_to_hod,
            "refer_to_counsellor": rec.refer_to_counsellor,
            "ai_source": AISource.TEMPLATE.value,
            "ai_recommendation": rec.summary,
            "notes": "",
            "notes_timeline": [],
            "status": CounsellingStatus.PENDING.value,
            "follow_up_date": None,
            "inputs_hash": risk_result.get("inputs_hash"),
            "created_at": now,
            "updated_at": now,
        }
        res = await db.counselling.insert_one(new_case)
        new_case["_id"] = res.inserted_id
        return new_case


counselling_service = CounsellingService()
