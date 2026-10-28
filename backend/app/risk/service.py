import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from backend.app.core.clock import Clock, default_clock
from backend.app.db.mongo import get_database
from backend.app.models.counselling import CounsellingStatus
from backend.app.models.risk import RiskLevel, RiskResultInDB
from backend.app.risk.config import (
    ENGINE_VERSION,
    RiskThresholds,
    RiskWeights,
    default_thresholds,
    default_weights,
)
from backend.app.risk.risk_engine import compute_inputs_hash, compute_student_risk

logger = logging.getLogger("student-dropout-system.risk.service")


class RiskService:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or default_clock

    async def recompute_student_risk(
        self,
        student_id: str | ObjectId,
        semester: int | None = None,
        weights: RiskWeights = default_weights,
        thresholds: RiskThresholds = default_thresholds,
        engine_version: str = ENGINE_VERSION,
    ) -> dict[str, Any] | None:
        """
        Recomputes risk for a student:
        - Retrieves target semester and previous semester performance metrics.
        - Checks idempotency using inputs_hash (Scenario R14).
        - Applies hysteresis based on previous risk level (Scenario R8).
        - Updates risk_results collection atomically (sets previous is_current=False).
        - Automatically creates pending counselling case for High-risk students.
        """
        db = get_database()
        now = self.clock.now()

        student_oid = ObjectId(student_id) if isinstance(student_id, str) else student_id
        student = await db.students.find_one({"_id": student_oid})
        if not student:
            logger.warning("Cannot compute risk: student %s not found.", student_id)
            return None

        # 1. Fetch performance records for the student
        perf_query: dict[str, Any] = {"student_id": student_oid}
        perf_docs = await db.performance.find(perf_query).sort("semester", 1).to_list(length=100)

        if not perf_docs:
            logger.info("No performance data found for student %s.", student_id)
            inputs = {
                "attendance": None,
                "classes_held": None,
                "marks": None,
                "prev_marks": None,
                "backlogs": None,
                "assignments": None,
                "engagement": None,
            }
            target_perf = None
            prev_marks = None
        else:
            if semester is not None:
                # Target requested semester
                matching = [p for p in perf_docs if p.get("semester") == semester]
                target_perf = matching[0] if matching else perf_docs[-1]
            else:
                target_perf = perf_docs[-1]

            target_sem = target_perf.get("semester", 1)
            # Find previous semester performance (for trend drop calculation)
            prev_candidates = [p for p in perf_docs if p.get("semester") == target_sem - 1]
            prev_marks = prev_candidates[0].get("marks") if prev_candidates else None

            inputs = {
                "attendance": target_perf.get("attendance"),
                "classes_held": target_perf.get("classes_held"),
                "marks": target_perf.get("marks"),
                "prev_marks": prev_marks,
                "backlogs": target_perf.get("backlogs"),
                "assignments": target_perf.get("assignments"),
                "engagement": target_perf.get("engagement"),
            }

        # 2. Fetch previous current risk for hysteresis and idempotency
        previous_risk = await db.risk_results.find_one(
            {"student_id": student_oid, "is_current": True}
        )
        previous_level = previous_risk.get("level") if previous_risk else None

        # 3. Check Idempotency (Scenario R14)
        current_hash = compute_inputs_hash(inputs, engine_version=engine_version)
        if (
            previous_risk
            and previous_risk.get("inputs_hash") == current_hash
            and previous_risk.get("engine_version") == engine_version
        ):
            logger.debug(
                "Idempotent risk recomputation: inputs unchanged for student %s.",
                student_id,
            )
            return previous_risk

        # 4. Compute risk using pure engine
        risk_calc = compute_student_risk(
            inputs=inputs,
            previous_level=previous_level,
            weights=weights,
            thresholds=thresholds,
            engine_version=engine_version,
        )

        # 5. Persist new risk result atomically
        new_risk_doc = {
            "student_id": student_oid,
            "performance_id": target_perf.get("_id") if target_perf else None,
            "score": risk_calc["score"],
            "level": risk_calc["level"],
            "confidence": risk_calc["confidence"],
            "watchlist": risk_calc["watchlist"],
            "factors": risk_calc["factors"],
            "overrides_applied": risk_calc["overrides_applied"],
            "engine_version": engine_version,
            "inputs_hash": current_hash,
            "computed_at": now,
            "is_current": True,
        }

        # Flip previous is_current to False
        await db.risk_results.update_many(
            {"student_id": student_oid, "is_current": True},
            {"$set": {"is_current": False}},
        )

        res = await db.risk_results.insert_one(new_risk_doc)
        new_risk_doc["_id"] = res.inserted_id

        # Invalidate analytics cache (short 30s TTL cache invalidated by risk changes)
        from backend.app.services.analytics_service import analytics_service
        analytics_service.invalidate_cache()

        # 6. Real-time SSE dispatch & notification on level change (Scenarios S1 and S6)
        if previous_level != risk_calc["level"]:
            from backend.app.realtime.broker import event_broker
            from backend.app.realtime.events import AppEvent
            from backend.app.services.notification_service import notification_service

            # Broadcast SSE event
            await event_broker.publish(
                AppEvent(
                    event_type="risk.changed",
                    student_id=str(student_oid),
                    target_department=student.get("department"),
                    data={
                        "student_id": str(student_oid),
                        "erp_id": student.get("erp_id"),
                        "old_level": previous_level,
                        "new_level": risk_calc["level"],
                        "score": risk_calc["score"],
                    },
                )
            )

            # In-app notification for assigned teachers
            for t_id in student.get("assigned_teacher_ids", []):
                await notification_service.create_notification(
                    user_id=t_id,
                    notification_type="risk.changed",
                    payload={
                        "student_id": str(student_oid),
                        "erp_id": student.get("erp_id"),
                        "old_level": previous_level,
                        "new_level": risk_calc["level"],
                        "score": risk_calc["score"],
                    },
                    send_email=(risk_calc["level"] == RiskLevel.HIGH.value),
                )

        # 7. Automatic Counselling handling if High Risk (Scenarios S1 and S14)
        if risk_calc["level"] == RiskLevel.HIGH.value:
            from backend.app.counselling.service import counselling_service

            await counselling_service.handle_high_risk_transition(
                student=student,
                risk_result=new_risk_doc,
            )

        return new_risk_doc


risk_service = RiskService()
