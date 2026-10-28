from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from backend.app.core.clock import Clock, default_clock
from backend.app.db.mongo import get_database
from backend.app.models.user import UserRole
from backend.app.schemas.performance import PerformanceResponse, PerformanceUpsertRequest
from backend.app.services.audit_service import AuditService, audit_service
from backend.app.risk.service import risk_service


class PerformanceService:
    def __init__(
        self,
        clock: Clock | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.clock = clock or default_clock
        self.audit = audit or audit_service

    async def upsert_performance(
        self,
        student_id: str,
        semester: int,
        req: PerformanceUpsertRequest,
        if_match_header: str | None,
        current_user: dict[str, Any],
        client_ip: str | None = None,
    ) -> PerformanceResponse:
        """
        Records or updates semester performance for a student.
        Enforces:
        - Object-level authorization (Teacher must be assigned to student; HOD/Admin allowed).
        - Optimistic concurrency control via If-Match version header (Scenario S2).
        - Retroactive marks audit trail.
        """
        if not ObjectId.is_valid(student_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        db = get_database()
        student_oid = ObjectId(student_id)
        student = await db.students.find_one({"_id": student_oid})
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        user_role = current_user.get("role")
        user_id = current_user.get("_id")
        user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id

        # 1. Scoping / Object-level permissions
        if user_role == UserRole.TEACHER.value:
            assigned_teachers = [str(t) for t in student.get("assigned_teacher_ids", [])]
            if str(user_oid) not in assigned_teachers:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FORBIDDEN",
                        "message": "Teacher is not assigned to this student.",
                    },
                )
        elif user_role not in (UserRole.ADMIN.value, UserRole.HOD.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": "Insufficient permissions to edit performance records.",
                },
            )

        now = self.clock.now()

        # 2. Check for existing record
        existing = await db.performance.find_one(
            {
                "student_id": student_oid,
                "semester": semester,
                "academic_year": req.academic_year,
            }
        )

        if existing:
            # Concurrency check (Scenario S2)
            current_version = existing.get("version", 1)

            if not if_match_header:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "CONCURRENT_MODIFICATION",
                        "message": "If-Match header with version is required for existing performance records.",
                        "current_version": current_version,
                    },
                )

            # Strip possible surrounding quotes from If-Match: e.g. '"1"' -> '1'
            clean_if_match = if_match_header.strip().strip('"')
            try:
                expected_version = int(clean_if_match)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_IF_MATCH", "message": "If-Match must be an integer version."},
                )

            if expected_version != current_version:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "CONCURRENT_MODIFICATION",
                        "message": "Performance record has been modified by another user.",
                        "current_version": current_version,
                        "current_record": self._format_performance_dict(existing),
                    },
                )

            # Atomic conditional update
            update_payload = {
                "attendance": req.attendance,
                "classes_held": req.classes_held,
                "marks": req.marks,
                "backlogs": req.backlogs,
                "assignments": req.assignments,
                "engagement": req.engagement,
                "version": current_version + 1,
                "updated_by": user_oid,
                "updated_at": now,
            }

            updated = await db.performance.find_one_and_update(
                {"_id": existing["_id"], "version": current_version},
                {"$set": update_payload},
                return_document=True,
            )

            if not updated:
                # Concurrent race condition: another update succeeded in between
                fresh = await db.performance.find_one({"_id": existing["_id"]})
                fresh_ver = fresh.get("version", current_version) if fresh else current_version
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "CONCURRENT_MODIFICATION",
                        "message": "Performance record has been modified by another user.",
                        "current_version": fresh_ver,
                        "current_record": self._format_performance_dict(fresh) if fresh else None,
                    },
                )

            # Audit log with before and after
            before_dict = self._format_performance_dict(existing)
            after_dict = self._format_performance_dict(updated)
            await self.audit.log_action(
                action="update_performance",
                target_type="performance",
                target_id=str(existing["_id"]),
                actor_id=user_oid,
                before=before_dict,
                after=after_dict,
                ip=client_ip,
            )

            # Trigger risk recomputation (Phase 5)
            await risk_service.recompute_student_risk(student_id=student_oid, semester=semester)

            return self._format_performance_response(updated)

        else:
            # 3. Create new record
            new_doc = {
                "student_id": student_oid,
                "semester": semester,
                "academic_year": req.academic_year,
                "attendance": req.attendance,
                "classes_held": req.classes_held,
                "marks": req.marks,
                "backlogs": req.backlogs,
                "assignments": req.assignments,
                "engagement": req.engagement,
                "version": 1,
                "updated_by": user_oid,
                "updated_at": now,
            }

            result = await db.performance.insert_one(new_doc)
            new_doc["_id"] = result.inserted_id

            await self.audit.log_action(
                action="create_performance",
                target_type="performance",
                target_id=str(result.inserted_id),
                actor_id=user_oid,
                after=self._format_performance_dict(new_doc),
                ip=client_ip,
            )

            # Trigger risk recomputation (Phase 5)
            await risk_service.recompute_student_risk(student_id=student_oid, semester=semester)

            return self._format_performance_response(new_doc)

    async def get_student_performance(
        self,
        student_id: str,
        semester: int,
        current_user: dict[str, Any],
    ) -> PerformanceResponse:
        """Retrieves performance record for a student in a specific semester."""
        if not ObjectId.is_valid(student_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        db = get_database()
        student_oid = ObjectId(student_id)
        student = await db.students.find_one({"_id": student_oid})
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        user_role = current_user.get("role")
        user_id = current_user.get("_id")
        user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id

        if user_role == UserRole.TEACHER.value:
            assigned_teachers = [str(t) for t in student.get("assigned_teacher_ids", [])]
            if str(user_oid) not in assigned_teachers:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "FORBIDDEN", "message": "Teacher is not assigned to this student."},
                )
        elif user_role == UserRole.STUDENT.value:
            if student.get("user_id") is None or str(student.get("user_id")) != str(user_oid):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "FORBIDDEN", "message": "Access denied."},
                )

        perf = await db.performance.find_one({"student_id": student_oid, "semester": semester})
        if not perf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PERFORMANCE_NOT_FOUND", "message": "Performance record not found."},
            )

        return self._format_performance_response(perf)

    def _format_performance_dict(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "student_id": str(doc["student_id"]),
            "semester": doc["semester"],
            "academic_year": doc.get("academic_year"),
            "attendance": doc.get("attendance"),
            "classes_held": doc.get("classes_held"),
            "marks": doc.get("marks"),
            "backlogs": doc.get("backlogs"),
            "assignments": doc.get("assignments"),
            "engagement": doc.get("engagement"),
            "version": doc.get("version", 1),
            "updated_by": str(doc["updated_by"]) if doc.get("updated_by") else None,
            "updated_at": str(doc.get("updated_at")),
        }

    def _format_performance_response(self, doc: dict[str, Any]) -> PerformanceResponse:
        return PerformanceResponse(
            id=str(doc["_id"]),
            student_id=str(doc["student_id"]),
            semester=doc["semester"],
            academic_year=doc["academic_year"],
            attendance=doc.get("attendance"),
            classes_held=doc.get("classes_held"),
            marks=doc.get("marks"),
            backlogs=doc.get("backlogs"),
            assignments=doc.get("assignments"),
            engagement=doc.get("engagement"),
            version=doc.get("version", 1),
            updated_by=str(doc["updated_by"]) if doc.get("updated_by") else None,
            updated_at=doc.get("updated_at", datetime.now()),
        )


performance_service = PerformanceService()
