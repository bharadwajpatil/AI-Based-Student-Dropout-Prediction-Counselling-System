import csv
import io
import logging
import math
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from backend.app.core.clock import Clock, SystemClock
from backend.app.db.mongo import get_database
from backend.app.models.counselling import CounsellingStatus
from backend.app.models.risk import RiskLevel
from backend.app.models.student import StudentStatus
from backend.app.models.user import UserRole

logger = logging.getLogger("student-dropout-system.analytics.service")


def compute_pearson_correlation(x_vals: list[float], y_vals: list[float]) -> float | None:
    """Computes sample Pearson correlation coefficient r, handling zero variance safely."""
    if len(x_vals) < 2 or len(x_vals) != len(y_vals):
        return None
    n = len(x_vals)
    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
    den_x = sum((x - mean_x) ** 2 for x in x_vals)
    den_y = sum((y - mean_y) ** 2 for y in y_vals)
    den = math.sqrt(den_x * den_y)
    if den == 0:
        return 0.0
    return round(num / den, 4)


def sanitize_csv_cell(value: Any) -> str:
    """Neutralizes CSV / formula injection (Scenario S15) by prefixing leading formula triggers."""
    if value is None:
        return ""
    val_str = str(value).strip()
    if val_str and val_str[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    return val_str


class AnalyticsService:
    """
    Analytics and KPI aggregation service.
    Features single-pass $facet aggregation pipelines, object-level role scoping,
    short-term TTL caching with event invalidation, and formula-safe CSV export.
    """

    def __init__(self, clock: Clock | None = None, cache_ttl_seconds: int = 30) -> None:
        self.clock = clock or SystemClock()
        self.cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[datetime, Any]] = {}

    def _get_db(self):
        return get_database()

    def invalidate_cache(self) -> None:
        """Clears cached analytics results when risk or performance changes."""
        self._cache.clear()
        logger.debug("Analytics cache invalidated.")

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            timestamp, data = self._cache[key]
            if (self.clock.now() - timestamp).total_seconds() < self.cache_ttl:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        self._cache[key] = (self.clock.now(), data)

    def _extract_user_info(self, user: Any) -> tuple[str, str, str | None]:
        if isinstance(user, dict):
            u_id = str(user.get("_id"))
            role = user.get("role")
            if hasattr(role, "value"):
                role = role.value
            dept = user.get("department")
            return u_id, str(role), dept
        else:
            role = user.role.value if hasattr(user.role, "value") else str(user.role)
            return str(user.id), role, getattr(user, "department", None)

    def _build_student_scope(self, user: Any, department_filter: str | None = None) -> dict[str, Any]:
        """
        Enforces RBAC scoping on student queries:
        - Students are blocked from institutional analytics.
        - Teachers only see assigned students.
        - HOD only sees own department students.
        - Admin sees all students.
        Excludes dropped/graduated students from active KPIs (Scenario S11).
        """
        user_id, role, user_dept = self._extract_user_info(user)

        if role == UserRole.STUDENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students are not authorized to view institutional analytics dashboards.",
            )

        # Base filter: active students only (Scenario S11)
        query: dict[str, Any] = {"status": StudentStatus.ACTIVE.value}

        if role == UserRole.TEACHER.value:
            query["assigned_teacher_ids"] = ObjectId(user_id)
            if department_filter:
                query["department"] = department_filter
        elif role == UserRole.HOD.value:
            # HOD is scoped to their department
            if user_dept:
                query["department"] = user_dept
            elif department_filter:
                query["department"] = department_filter
        elif role == UserRole.ADMIN.value:
            if department_filter:
                query["department"] = department_filter

        return query

    async def get_overview(self, user: Any, department_filter: str | None = None) -> dict[str, Any]:
        """
        Computes high-level KPI overview using a single-pass aggregation pipeline ($facet).
        Returns total students, risk counts, pending counselling cases, and metric averages.
        """
        user_id, role, _ = self._extract_user_info(user)
        cache_key = f"overview:{role}:{user_id}:{department_filter}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        db = self._get_db()
        match_query = self._build_student_scope(user, department_filter)

        # Single aggregation pipeline using $facet and compatible $lookup
        pipeline = [
            {"$match": match_query},
            {
                "$lookup": {
                    "from": "risk_results",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_risk",
                }
            },
            {
                "$lookup": {
                    "from": "counselling",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_counselling",
                }
            },
            {
                "$lookup": {
                    "from": "performance",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_perf",
                }
            },
            {
                "$project": {
                    "department": 1,
                    "semester": 1,
                    "current_risk": {
                        "$filter": {
                            "input": "$all_risk",
                            "as": "r",
                            "cond": {"$eq": ["$$r.is_current", True]},
                        }
                    },
                    "pending_counselling": {
                        "$filter": {
                            "input": "$all_counselling",
                            "as": "c",
                            "cond": {"$eq": ["$$c.status", CounsellingStatus.PENDING.value]},
                        }
                    },
                    "all_perf": 1,
                }
            },
            {
                "$project": {
                    "department": 1,
                    "semester": 1,
                    "risk": {"$arrayElemAt": ["$current_risk", 0]},
                    "has_pending_counselling": {"$gt": [{"$size": "$pending_counselling"}, 0]},
                    "perf": {
                        "$arrayElemAt": [
                            {
                                "$filter": {
                                    "input": "$all_perf",
                                    "as": "p",
                                    "cond": {"$eq": ["$$p.semester", "$semester"]},
                                }
                            },
                            0,
                        ]
                    },
                }
            },
            {
                "$facet": {
                    "total_students": [{"$count": "count"}],
                    "risk_levels": [
                        {"$group": {"_id": "$risk.level", "count": {"$sum": 1}}}
                    ],
                    "counselling_pending": [
                        {"$match": {"has_pending_counselling": True}},
                        {"$count": "count"},
                    ],
                    "watchlist": [
                        {"$match": {"risk.watchlist": True}},
                        {"$count": "count"},
                    ],
                    "averages": [
                        {
                            "$group": {
                                "_id": None,
                                "avg_attendance": {"$avg": "$perf.attendance"},
                                "avg_marks": {"$avg": "$perf.marks"},
                            }
                        }
                    ],
                }
            },
        ]

        facet_results = await db.students.aggregate(pipeline).to_list(1)
        res = facet_results[0] if facet_results else {}

        total_students = res.get("total_students", [{}])[0].get("count", 0) if res.get("total_students") else 0

        # Parse risk distribution buckets
        level_counts = {
            RiskLevel.HIGH.value: 0,
            RiskLevel.MEDIUM.value: 0,
            RiskLevel.LOW.value: 0,
            RiskLevel.INSUFFICIENT_DATA.value: 0,
        }
        for item in res.get("risk_levels", []):
            lvl = item.get("_id")
            count = item.get("count", 0)
            if lvl in level_counts:
                level_counts[lvl] = count
            else:
                # Unassigned or null risk belongs in Insufficient Data, never Low
                level_counts[RiskLevel.INSUFFICIENT_DATA.value] += count

        counselling_pending = res.get("counselling_pending", [{}])[0].get("count", 0) if res.get("counselling_pending") else 0
        watchlist = res.get("watchlist", [{}])[0].get("count", 0) if res.get("watchlist") else 0

        avg_data = res.get("averages", [{}])[0] if res.get("averages") else {}
        avg_att = avg_data.get("avg_attendance")
        avg_marks = avg_data.get("avg_marks")

        output = {
            "total_students": total_students,
            "high_risk_count": level_counts[RiskLevel.HIGH.value],
            "medium_risk_count": level_counts[RiskLevel.MEDIUM.value],
            "low_risk_count": level_counts[RiskLevel.LOW.value],
            "insufficient_data_count": level_counts[RiskLevel.INSUFFICIENT_DATA.value],
            "counselling_pending_count": counselling_pending,
            "watchlist_count": watchlist,
            "average_attendance": round(avg_att, 1) if avg_att is not None else None,
            "average_marks": round(avg_marks, 1) if avg_marks is not None else None,
            "last_updated": self.clock.now(),
        }

        self._set_cached(cache_key, output)
        return output

    async def get_distribution(self, user: Any, department_filter: str | None = None) -> dict[str, Any]:
        """Returns risk distribution breakdown by department and by semester."""
        user_id, role, _ = self._extract_user_info(user)
        cache_key = f"dist:{role}:{user_id}:{department_filter}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        db = self._get_db()
        match_query = self._build_student_scope(user, department_filter)

        pipeline = [
            {"$match": match_query},
            {
                "$lookup": {
                    "from": "risk_results",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_risk",
                }
            },
            {
                "$project": {
                    "department": 1,
                    "semester": 1,
                    "current_risk": {
                        "$filter": {
                            "input": "$all_risk",
                            "as": "r",
                            "cond": {"$eq": ["$$r.is_current", True]},
                        }
                    },
                }
            },
            {
                "$project": {
                    "department": 1,
                    "semester": 1,
                    "level": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$current_risk.level", 0]},
                            RiskLevel.INSUFFICIENT_DATA.value,
                        ]
                    },
                }
            },
            {
                "$facet": {
                    "by_department": [
                        {
                            "$group": {
                                "_id": {"dept": "$department", "level": "$level"},
                                "count": {"$sum": 1},
                            }
                        }
                    ],
                    "by_semester": [
                        {
                            "$group": {
                                "_id": {"sem": "$semester", "level": "$level"},
                                "count": {"$sum": 1},
                            }
                        }
                    ],
                }
            },
        ]

        facet_results = await db.students.aggregate(pipeline).to_list(1)
        res = facet_results[0] if facet_results else {}

        # Format by_department
        dept_map: dict[str, dict[str, int]] = {}
        for row in res.get("by_department", []):
            dept = row["_id"]["dept"] or "Unknown"
            lvl = row["_id"]["level"] or RiskLevel.INSUFFICIENT_DATA.value
            count = row["count"]
            if dept not in dept_map:
                dept_map[dept] = {"high": 0, "medium": 0, "low": 0, "insufficient_data": 0, "total": 0}
            dept_map[dept]["total"] += count
            if lvl == RiskLevel.HIGH.value:
                dept_map[dept]["high"] += count
            elif lvl == RiskLevel.MEDIUM.value:
                dept_map[dept]["medium"] += count
            elif lvl == RiskLevel.LOW.value:
                dept_map[dept]["low"] += count
            else:
                dept_map[dept]["insufficient_data"] += count

        dept_list = [
            {"department": k, **v}
            for k, v in sorted(dept_map.items())
        ]

        # Format by_semester
        sem_map: dict[int, dict[str, int]] = {}
        for row in res.get("by_semester", []):
            sem = row["_id"]["sem"] or 1
            lvl = row["_id"]["level"] or RiskLevel.INSUFFICIENT_DATA.value
            count = row["count"]
            if sem not in sem_map:
                sem_map[sem] = {"high": 0, "medium": 0, "low": 0, "insufficient_data": 0, "total": 0}
            sem_map[sem]["total"] += count
            if lvl == RiskLevel.HIGH.value:
                sem_map[sem]["high"] += count
            elif lvl == RiskLevel.MEDIUM.value:
                sem_map[sem]["medium"] += count
            elif lvl == RiskLevel.LOW.value:
                sem_map[sem]["low"] += count
            else:
                sem_map[sem]["insufficient_data"] += count

        sem_list = [
            {"semester": k, **v}
            for k, v in sorted(sem_map.items())
        ]

        output = {
            "by_department": dept_list,
            "by_semester": sem_list,
        }
        self._set_cached(cache_key, output)
        return output

    async def get_attendance_vs_risk(self, user: Any, department_filter: str | None = None) -> dict[str, Any]:
        """Calculates attendance vs risk score correlation and scatter data."""
        db = self._get_db()
        match_query = self._build_student_scope(user, department_filter)

        pipeline = [
            {"$match": match_query},
            {
                "$lookup": {
                    "from": "risk_results",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_risk",
                }
            },
            {
                "$lookup": {
                    "from": "performance",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_perf",
                }
            },
            {
                "$project": {
                    "erp_id": 1,
                    "department": 1,
                    "semester": 1,
                    "current_risk": {
                        "$filter": {
                            "input": "$all_risk",
                            "as": "r",
                            "cond": {"$eq": ["$$r.is_current", True]},
                        }
                    },
                    "all_perf": 1,
                }
            },
            {
                "$project": {
                    "erp_id": 1,
                    "department": 1,
                    "semester": 1,
                    "risk": {"$arrayElemAt": ["$current_risk", 0]},
                    "perf": {
                        "$arrayElemAt": [
                            {
                                "$filter": {
                                    "input": "$all_perf",
                                    "as": "p",
                                    "cond": {"$eq": ["$$p.semester", "$semester"]},
                                }
                            },
                            0,
                        ]
                    },
                }
            },
            {
                "$match": {
                    "risk.score": {"$ne": None},
                    "perf.attendance": {"$ne": None},
                }
            },
        ]

        cursor = db.students.aggregate(pipeline)
        points = []
        att_vals = []
        risk_vals = []

        async for row in cursor:
            sid = str(row["_id"])
            att = float(row["perf"]["attendance"])
            score = float(row["risk"]["score"])
            lvl = str(row["risk"]["level"])

            points.append({
                "student_id": sid,
                "erp_id": row.get("erp_id", ""),
                "department": row.get("department", ""),
                "semester": row.get("semester", 1),
                "attendance": att,
                "risk_score": score,
                "risk_level": lvl,
            })
            att_vals.append(att)
            risk_vals.append(score)

        correlation = compute_pearson_correlation(att_vals, risk_vals)
        return {"points": points, "correlation": correlation}

    async def get_marks_vs_risk(self, user: Any, department_filter: str | None = None) -> dict[str, Any]:
        """Calculates academic marks vs risk score correlation and scatter data."""
        db = self._get_db()
        match_query = self._build_student_scope(user, department_filter)

        pipeline = [
            {"$match": match_query},
            {
                "$lookup": {
                    "from": "risk_results",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_risk",
                }
            },
            {
                "$lookup": {
                    "from": "performance",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_perf",
                }
            },
            {
                "$project": {
                    "erp_id": 1,
                    "department": 1,
                    "semester": 1,
                    "current_risk": {
                        "$filter": {
                            "input": "$all_risk",
                            "as": "r",
                            "cond": {"$eq": ["$$r.is_current", True]},
                        }
                    },
                    "all_perf": 1,
                }
            },
            {
                "$project": {
                    "erp_id": 1,
                    "department": 1,
                    "semester": 1,
                    "risk": {"$arrayElemAt": ["$current_risk", 0]},
                    "perf": {
                        "$arrayElemAt": [
                            {
                                "$filter": {
                                    "input": "$all_perf",
                                    "as": "p",
                                    "cond": {"$eq": ["$$p.semester", "$semester"]},
                                }
                            },
                            0,
                        ]
                    },
                }
            },
            {
                "$match": {
                    "risk.score": {"$ne": None},
                    "perf.marks": {"$ne": None},
                }
            },
        ]

        cursor = db.students.aggregate(pipeline)
        points = []
        marks_vals = []
        risk_vals = []

        async for row in cursor:
            sid = str(row["_id"])
            marks = float(row["perf"]["marks"])
            score = float(row["risk"]["score"])
            lvl = str(row["risk"]["level"])

            points.append({
                "student_id": sid,
                "erp_id": row.get("erp_id", ""),
                "department": row.get("department", ""),
                "semester": row.get("semester", 1),
                "marks": marks,
                "risk_score": score,
                "risk_level": lvl,
            })
            marks_vals.append(marks)
            risk_vals.append(score)

        correlation = compute_pearson_correlation(marks_vals, risk_vals)
        return {"points": points, "correlation": correlation}

    async def get_by_department(self, user: Any) -> list[dict[str, Any]]:
        """Department breakdown with averages and risk counts."""
        dist = await self.get_distribution(user)
        dept_data = dist["by_department"]
        result = []
        for d in dept_data:
            result.append({
                "department": d["department"],
                "total_students": d["total"],
                "high_risk_count": d["high"],
                "medium_risk_count": d["medium"],
                "low_risk_count": d["low"],
                "insufficient_data_count": d["insufficient_data"],
                "average_attendance": None,
                "average_marks": None,
                "average_risk_score": None,
            })
        return result

    async def get_by_semester(self, user: Any, department_filter: str | None = None) -> list[dict[str, Any]]:
        """Semester breakdown with risk counts."""
        dist = await self.get_distribution(user, department_filter)
        sem_data = dist["by_semester"]
        result = []
        for s in sem_data:
            result.append({
                "semester": s["semester"],
                "total_students": s["total"],
                "high_risk_count": s["high"],
                "medium_risk_count": s["medium"],
                "low_risk_count": s["low"],
                "insufficient_data_count": s["insufficient_data"],
                "average_attendance": None,
                "average_marks": None,
                "average_risk_score": None,
            })
        return result

    async def get_student_trend(self, student_id: str, user: Any) -> dict[str, Any]:
        """Chronological risk and performance trajectory across semesters for a student."""
        db = self._get_db()
        try:
            s_oid = ObjectId(student_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student ID format.")

        student = await db.students.find_one({"_id": s_oid})
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

        # RBAC verification
        user_id, role, user_dept = self._extract_user_info(user)
        if role == UserRole.TEACHER.value:
            assigned = [str(t) for t in student.get("assigned_teacher_ids", [])]
            if user_id not in assigned:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to student trend.")
        elif role == UserRole.HOD.value:
            if user_dept and student.get("department") != user_dept:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized department access.")
        elif role == UserRole.STUDENT.value:
            if str(student.get("user_id")) != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own trend.")

        # Fetch all performance documents for student sorted by semester ascending
        perf_cursor = db.performance.find({"student_id": s_oid}).sort("semester", 1)
        perfs = [p async for p in perf_cursor]

        # Fetch risk results for student
        risk_cursor = db.risk_results.find({"student_id": s_oid}).sort("computed_at", 1)
        risks = [r async for r in risk_cursor]

        trajectory = []
        for p in perfs:
            sem = p["semester"]
            # Find closest risk result for this performance or semester
            matching_risk = None
            for r in risks:
                if str(r.get("performance_id")) == str(p["_id"]):
                    matching_risk = r
                    break
            if not matching_risk and risks:
                matching_risk = risks[-1]

            trajectory.append({
                "semester": sem,
                "academic_year": p.get("academic_year", ""),
                "attendance": p.get("attendance"),
                "marks": p.get("marks"),
                "backlogs": p.get("backlogs", 0),
                "risk_score": matching_risk.get("score") if matching_risk else None,
                "risk_level": matching_risk.get("level") if matching_risk else None,
                "computed_at": matching_risk.get("computed_at") if matching_risk else None,
            })

        return {
            "student_id": str(student["_id"]),
            "erp_id": student.get("erp_id", ""),
            "name": student.get("name", ""),
            "department": student.get("department", ""),
            "current_semester": student.get("semester", 1),
            "trajectory": trajectory,
        }

    async def export_high_risk_csv(self, user: Any, department_filter: str | None = None) -> str:
        """
        Generates CSV report of high-risk students with formula injection defense (Scenario S15).
        """
        db = self._get_db()
        match_query = self._build_student_scope(user, department_filter)

        pipeline = [
            {"$match": match_query},
            {
                "$lookup": {
                    "from": "risk_results",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_risk",
                }
            },
            {
                "$lookup": {
                    "from": "counselling",
                    "localField": "_id",
                    "foreignField": "student_id",
                    "as": "all_counselling",
                }
            },
            {
                "$project": {
                    "erp_id": 1,
                    "name": 1,
                    "department": 1,
                    "semester": 1,
                    "batch": 1,
                    "assigned_teacher_ids": 1,
                    "risk": {
                        "$arrayElemAt": [
                            {
                                "$filter": {
                                    "input": "$all_risk",
                                    "as": "r",
                                    "cond": {"$eq": ["$$r.is_current", True]},
                                }
                            },
                            0,
                        ]
                    },
                    "counselling": {"$arrayElemAt": ["$all_counselling", 0]},
                }
            },
            {
                "$match": {
                    "risk.level": RiskLevel.HIGH.value,
                }
            },
            {"$sort": {"risk.score": -1}},
        ]

        cursor = db.students.aggregate(pipeline)
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "ERP ID",
            "Student Name",
            "Department",
            "Semester",
            "Batch",
            "Risk Score",
            "Risk Level",
            "Primary Risk Factors",
            "Counselling Status",
        ])

        async for row in cursor:
            factors = row.get("risk", {}).get("factors", [])
            factor_summary = "; ".join(f"{f.get('name')}: {f.get('risk')}%" for f in factors[:3])
            counselling_status = row.get("counselling", {}).get("status", "none")

            writer.writerow([
                sanitize_csv_cell(row.get("erp_id")),
                sanitize_csv_cell(row.get("name")),
                sanitize_csv_cell(row.get("department")),
                sanitize_csv_cell(row.get("semester")),
                sanitize_csv_cell(row.get("batch")),
                sanitize_csv_cell(row.get("risk", {}).get("score")),
                sanitize_csv_cell(row.get("risk", {}).get("level")),
                sanitize_csv_cell(factor_summary),
                sanitize_csv_cell(counselling_status),
            ])

        return output.getvalue()


analytics_service = AnalyticsService()
