from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status

from backend.app.core.deps import get_current_user, require_role
from backend.app.models.user import UserRole
from backend.app.schemas.analytics import (
    AnalyticsDistributionResponse,
    AnalyticsOverviewResponse,
    AttendanceVsRiskResponse,
    DepartmentAnalyticsItem,
    MarksVsRiskResponse,
    SemesterAnalyticsItem,
    StudentTrendResponse,
)
from backend.app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    department: str | None = Query(default=None, description="Optional department filter (Admin only)"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    High-level institutional KPI overview.
    - Single aggregation pipeline ($facet)
    - Excludes inactive/dropped students
    - Scoped by user role (Teacher: assigned, HOD: department, Admin: all)
    - 30-second TTL caching
    """
    return await analytics_service.get_overview(user=current_user, department_filter=department)


@router.get("/distribution", response_model=AnalyticsDistributionResponse)
async def get_analytics_distribution(
    department: str | None = Query(default=None, description="Optional department filter"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Risk tier distribution broken down by department and semester."""
    return await analytics_service.get_distribution(user=current_user, department_filter=department)


@router.get("/attendance-vs-risk", response_model=AttendanceVsRiskResponse)
async def get_attendance_vs_risk(
    department: str | None = Query(default=None, description="Optional department filter"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Correlation analysis and scatter data between student attendance and risk score."""
    return await analytics_service.get_attendance_vs_risk(user=current_user, department_filter=department)


@router.get("/marks-vs-risk", response_model=MarksVsRiskResponse)
async def get_marks_vs_risk(
    department: str | None = Query(default=None, description="Optional department filter"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Correlation analysis and scatter data between student marks and risk score."""
    return await analytics_service.get_marks_vs_risk(user=current_user, department_filter=department)


@router.get("/by-department", response_model=list[DepartmentAnalyticsItem])
async def get_by_department(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Department-level analytics table with student counts and risk buckets."""
    return await analytics_service.get_by_department(user=current_user)


@router.get("/by-semester", response_model=list[SemesterAnalyticsItem])
async def get_by_semester(
    department: str | None = Query(default=None, description="Optional department filter"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Semester-level analytics table with student counts and risk buckets."""
    return await analytics_service.get_by_semester(user=current_user, department_filter=department)


@router.get("/trend", response_model=StudentTrendResponse)
async def get_student_trend(
    student_id: str = Query(..., description="Student ID to inspect historical trajectory"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Historical progression of a student's risk and academic metrics across semesters."""
    return await analytics_service.get_student_trend(student_id=student_id, user=current_user)


@router.get("/export/high-risk")
async def export_high_risk_csv(
    department: str | None = Query(default=None, description="Optional department filter"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Exports high-risk student roster as CSV.
    Neutralizes spreadsheet formula injection (=, +, -, @) per Scenario S15.
    """
    csv_content = await analytics_service.export_high_risk_csv(user=current_user, department_filter=department)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=high_risk_students.csv",
        },
    )


@router.post("/cache/invalidate", status_code=status.HTTP_200_OK)
async def invalidate_analytics_cache(
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN, UserRole.HOD)),
):
    """Manually clear in-memory analytics KPI cache."""
    analytics_service.invalidate_cache()
    return {"message": "Analytics cache invalidated successfully."}
