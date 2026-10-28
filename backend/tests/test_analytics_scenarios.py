from datetime import UTC, datetime
from typing import Any

import pytest
from bson import ObjectId

from backend.app.core.clock import TestClock
from backend.app.core.security import create_access_token
from backend.app.models.counselling import CounsellingStatus
from backend.app.models.risk import RiskLevel
from backend.app.models.student import StudentStatus
from backend.app.models.user import UserRole
from backend.app.services.analytics_service import (
    AnalyticsService,
    compute_pearson_correlation,
    sanitize_csv_cell,
)


# -----------------------------------------------------------------------------
# 1. Math & Utility Unit Tests
# -----------------------------------------------------------------------------

def test_pearson_correlation_math():
    """Verifies Pearson r calculation with perfect positive, negative, and edge cases."""
    # Perfect positive correlation (r = 1.0)
    x1 = [10.0, 20.0, 30.0, 40.0]
    y1 = [20.0, 40.0, 60.0, 80.0]
    assert compute_pearson_correlation(x1, y1) == 1.0

    # Perfect negative correlation (r = -1.0)
    x2 = [10.0, 20.0, 30.0, 40.0]
    y2 = [80.0, 60.0, 40.0, 20.0]
    assert compute_pearson_correlation(x2, y2) == -1.0

    # Zero variance (all y values identical) -> safe 0.0, no ZeroDivisionError
    x3 = [10.0, 20.0, 30.0]
    y3 = [50.0, 50.0, 50.0]
    assert compute_pearson_correlation(x3, y3) == 0.0

    # Fewer than 2 points -> None
    assert compute_pearson_correlation([10.0], [20.0]) is None
    assert compute_pearson_correlation([], []) is None


def test_sanitize_csv_cell_formula_injection():
    """Scenario S15: Formula injection characters are neutralized with leading quote."""
    assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_cell("+123456789") == "'+123456789"
    assert sanitize_csv_cell("-10+20") == "'-10+20"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("Normal Student Name") == "Normal Student Name"
    assert sanitize_csv_cell(None) == ""


# -----------------------------------------------------------------------------
# 2. Overview Aggregation ($facet) & Edge Cases
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_overview_aggregation(mock_db):
    """Verifies single-pass $facet aggregation across students, risks, and counselling."""
    clock = TestClock()
    service = AnalyticsService(clock=clock)

    admin_user = {"_id": ObjectId(), "role": UserRole.ADMIN.value, "name": "Admin User"}

    # 1. Empty DB: returns zeros and None for averages without failing
    overview_empty = await service.get_overview(admin_user)
    assert overview_empty["total_students"] == 0
    assert overview_empty["high_risk_count"] == 0
    assert overview_empty["medium_risk_count"] == 0
    assert overview_empty["low_risk_count"] == 0
    assert overview_empty["insufficient_data_count"] == 0
    assert overview_empty["counselling_pending_count"] == 0
    assert overview_empty["average_attendance"] is None

    # 2. Populate Students with different risk levels
    # Student 1: High risk, counselling pending
    s1_res = await mock_db.students.insert_one({
        "erp_id": "STU101",
        "name": "High Risk Stu",
        "department": "CSE",
        "semester": 4,
        "status": StudentStatus.ACTIVE.value,
        "assigned_teacher_ids": [],
    })
    s1_id = s1_res.inserted_id

    await mock_db.risk_results.insert_one({
        "student_id": s1_id,
        "level": RiskLevel.HIGH.value,
        "score": 82.0,
        "watchlist": False,
        "is_current": True,
    })
    await mock_db.counselling.insert_one({
        "student_id": s1_id,
        "status": CounsellingStatus.PENDING.value,
    })
    await mock_db.performance.insert_one({
        "student_id": s1_id,
        "semester": 4,
        "attendance": 50.0,
        "marks": 40.0,
    })

    # Student 2: Medium risk, watchlist true
    s2_res = await mock_db.students.insert_one({
        "erp_id": "STU102",
        "name": "Medium Risk Stu",
        "department": "CSE",
        "semester": 4,
        "status": StudentStatus.ACTIVE.value,
        "assigned_teacher_ids": [],
    })
    s2_id = s2_res.inserted_id

    await mock_db.risk_results.insert_one({
        "student_id": s2_id,
        "level": RiskLevel.MEDIUM.value,
        "score": 55.0,
        "watchlist": True,
        "is_current": True,
    })
    await mock_db.performance.insert_one({
        "student_id": s2_id,
        "semester": 4,
        "attendance": 70.0,
        "marks": 60.0,
    })

    # Student 3: Low risk
    s3_res = await mock_db.students.insert_one({
        "erp_id": "STU103",
        "name": "Low Risk Stu",
        "department": "ECE",
        "semester": 2,
        "status": StudentStatus.ACTIVE.value,
        "assigned_teacher_ids": [],
    })
    s3_id = s3_res.inserted_id

    await mock_db.risk_results.insert_one({
        "student_id": s3_id,
        "level": RiskLevel.LOW.value,
        "score": 15.0,
        "watchlist": False,
        "is_current": True,
    })
    await mock_db.performance.insert_one({
        "student_id": s3_id,
        "semester": 2,
        "attendance": 90.0,
        "marks": 85.0,
    })

    # Student 4: Insufficient Data (never mixed into Low!)
    s4_res = await mock_db.students.insert_one({
        "erp_id": "STU104",
        "name": "No Data Stu",
        "department": "ECE",
        "semester": 1,
        "status": StudentStatus.ACTIVE.value,
        "assigned_teacher_ids": [],
    })
    # No risk result created yet for Student 4

    # Student 5: Dropped student (Scenario S11: excluded from active KPIs)
    await mock_db.students.insert_one({
        "erp_id": "STU105",
        "name": "Dropped Stu",
        "department": "CSE",
        "semester": 4,
        "status": StudentStatus.DROPPED.value,
        "assigned_teacher_ids": [],
    })

    # Execute overview aggregation
    service.invalidate_cache()
    overview = await service.get_overview(admin_user)

    assert overview["total_students"] == 4  # Dropped student excluded!
    assert overview["high_risk_count"] == 1
    assert overview["medium_risk_count"] == 1
    assert overview["low_risk_count"] == 1
    assert overview["insufficient_data_count"] == 1  # Student 4 isolated here!
    assert overview["counselling_pending_count"] == 1
    assert overview["watchlist_count"] == 1
    # Average attendance across students 1, 2, 3: (50 + 70 + 90) / 3 = 70.0
    assert overview["average_attendance"] == 70.0
    # Average marks across students 1, 2, 3: (40 + 60 + 85) / 3 = 61.7
    assert overview["average_marks"] == 61.7


# -----------------------------------------------------------------------------
# 3. RBAC Scoping for Overview & Dashboards
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_rbac_scoping(mock_db):
    """Verifies Teacher sees only assigned students, HOD sees only department, and Student gets 403."""
    clock = TestClock()
    service = AnalyticsService(clock=clock)

    teacher_id = ObjectId()
    hod_dept = "Civil"

    # Teacher 1 student (in CSE)
    t1_stu = await mock_db.students.insert_one({
        "erp_id": "T_STU_1",
        "name": "Teacher Stu",
        "department": "CSE",
        "semester": 3,
        "status": StudentStatus.ACTIVE.value,
        "assigned_teacher_ids": [teacher_id],
    })
    await mock_db.risk_results.insert_one({
        "student_id": t1_stu.inserted_id,
        "level": RiskLevel.HIGH.value,
        "score": 75.0,
        "is_current": True,
    })

    # HOD department student (in Civil)
    h_stu = await mock_db.students.insert_one({
        "erp_id": "H_STU_1",
        "name": "Civil Stu",
        "department": hod_dept,
        "semester": 1,
        "status": StudentStatus.ACTIVE.value,
        "assigned_teacher_ids": [],
    })
    await mock_db.risk_results.insert_one({
        "student_id": h_stu.inserted_id,
        "level": RiskLevel.LOW.value,
        "score": 20.0,
        "is_current": True,
    })

    teacher_user = {"_id": teacher_id, "role": UserRole.TEACHER.value, "name": "Prof. T"}
    hod_user = {"_id": ObjectId(), "role": UserRole.HOD.value, "name": "Dr. HOD", "department": hod_dept}
    student_user = {"_id": ObjectId(), "role": UserRole.STUDENT.value, "name": "Student A"}

    # 1. Teacher overview: sees only 1 student
    t_overview = await service.get_overview(teacher_user)
    assert t_overview["total_students"] == 1
    assert t_overview["high_risk_count"] == 1
    assert t_overview["low_risk_count"] == 0

    # 2. HOD overview: sees only Civil student
    h_overview = await service.get_overview(hod_user)
    assert h_overview["total_students"] == 1
    assert h_overview["high_risk_count"] == 0
    assert h_overview["low_risk_count"] == 1

    # 3. Student overview: raises 403 Forbidden
    with pytest.raises(Exception) as exc_info:
        await service.get_overview(student_user)
    assert "403" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 4. Distribution, Scatter Correlations, and Trend
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_distribution_and_correlations(mock_db):
    """Verifies distribution breakdown by dept/sem and scatter correlation calculation."""
    clock = TestClock()
    service = AnalyticsService(clock=clock)
    admin_user = {"_id": ObjectId(), "role": UserRole.ADMIN.value, "name": "Admin"}

    s1 = await mock_db.students.insert_one({
        "erp_id": "CORR1",
        "department": "CSE",
        "semester": 3,
        "status": StudentStatus.ACTIVE.value,
    })
    await mock_db.risk_results.insert_one({
        "student_id": s1.inserted_id,
        "score": 80.0,
        "level": RiskLevel.HIGH.value,
        "is_current": True,
    })
    await mock_db.performance.insert_one({
        "student_id": s1.inserted_id,
        "semester": 3,
        "attendance": 45.0,
        "marks": 35.0,
    })

    s2 = await mock_db.students.insert_one({
        "erp_id": "CORR2",
        "department": "CSE",
        "semester": 3,
        "status": StudentStatus.ACTIVE.value,
    })
    await mock_db.risk_results.insert_one({
        "student_id": s2.inserted_id,
        "score": 20.0,
        "level": RiskLevel.LOW.value,
        "is_current": True,
    })
    await mock_db.performance.insert_one({
        "student_id": s2.inserted_id,
        "semester": 3,
        "attendance": 90.0,
        "marks": 85.0,
    })

    # Distribution test
    dist = await service.get_distribution(admin_user)
    assert len(dist["by_department"]) == 1
    assert dist["by_department"][0]["department"] == "CSE"
    assert dist["by_department"][0]["high"] == 1
    assert dist["by_department"][0]["low"] == 1
    assert dist["by_department"][0]["total"] == 2

    assert len(dist["by_semester"]) == 1
    assert dist["by_semester"][0]["semester"] == 3

    # Attendance vs Risk
    att_corr = await service.get_attendance_vs_risk(admin_user)
    assert len(att_corr["points"]) == 2
    # Inverse relationship: low attendance has high risk score -> negative r
    assert att_corr["correlation"] is not None
    assert att_corr["correlation"] < 0.0

    # Marks vs Risk
    marks_corr = await service.get_marks_vs_risk(admin_user)
    assert len(marks_corr["points"]) == 2
    assert marks_corr["correlation"] is not None
    assert marks_corr["correlation"] < 0.0


@pytest.mark.asyncio
async def test_student_trend_trajectory(mock_db):
    """Verifies chronological trajectory of performance and risk over semesters."""
    clock = TestClock()
    service = AnalyticsService(clock=clock)
    admin_user = {"_id": ObjectId(), "role": UserRole.ADMIN.value, "name": "Admin"}

    s_res = await mock_db.students.insert_one({
        "erp_id": "TREND101",
        "name": "Trend Student",
        "department": "IT",
        "semester": 3,
        "status": StudentStatus.ACTIVE.value,
        "assigned_teacher_ids": [],
    })
    sid = s_res.inserted_id

    # Semester 1
    p1 = await mock_db.performance.insert_one({
        "student_id": sid,
        "semester": 1,
        "academic_year": "2024-25",
        "attendance": 88.0,
        "marks": 80.0,
        "backlogs": 0,
    })
    await mock_db.risk_results.insert_one({
        "student_id": sid,
        "performance_id": p1.inserted_id,
        "score": 18.0,
        "level": RiskLevel.LOW.value,
        "is_current": False,
        "computed_at": clock.now(),
    })

    # Semester 2
    p2 = await mock_db.performance.insert_one({
        "student_id": sid,
        "semester": 2,
        "academic_year": "2024-25",
        "attendance": 55.0,
        "marks": 48.0,
        "backlogs": 2,
    })
    await mock_db.risk_results.insert_one({
        "student_id": sid,
        "performance_id": p2.inserted_id,
        "score": 68.0,
        "level": RiskLevel.MEDIUM.value,
        "is_current": True,
        "computed_at": clock.now(),
    })

    trend = await service.get_student_trend(str(sid), admin_user)
    assert trend["student_id"] == str(sid)
    assert trend["erp_id"] == "TREND101"
    assert len(trend["trajectory"]) == 2
    assert trend["trajectory"][0]["semester"] == 1
    assert trend["trajectory"][0]["attendance"] == 88.0
    assert trend["trajectory"][1]["semester"] == 2
    assert trend["trajectory"][1]["attendance"] == 55.0


# -----------------------------------------------------------------------------
# 5. CSV Export with Formula Injection Defense (Scenario S15)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_high_risk_csv_with_formula_sanitization(mock_db):
    """Scenario S15: CSV export neutralizes spreadsheet formula injection."""
    clock = TestClock()
    service = AnalyticsService(clock=clock)
    admin_user = {"_id": ObjectId(), "role": UserRole.ADMIN.value, "name": "Admin"}

    # Dangerous name starting with formula trigger
    s_res = await mock_db.students.insert_one({
        "erp_id": "=cmd|' /C calc'!A0",
        "name": "+Malicious Name",
        "department": "@ExploitDept",
        "semester": 4,
        "batch": "2023-27",
        "status": StudentStatus.ACTIVE.value,
    })
    sid = s_res.inserted_id

    await mock_db.risk_results.insert_one({
        "student_id": sid,
        "score": 85.0,
        "level": RiskLevel.HIGH.value,
        "factors": [{"name": "attendance", "risk": 90.0}],
        "is_current": True,
    })

    csv_output = await service.export_high_risk_csv(admin_user)
    lines = csv_output.strip().split("\n")
    assert len(lines) == 2  # Header + 1 student

    data_row = lines[1]
    # Check that leading formula triggers are safely prefixed with single quote
    assert "'=cmd" in data_row
    assert "'+Malicious" in data_row
    assert "'@ExploitDept" in data_row


# -----------------------------------------------------------------------------
# 6. Caching & Invalidation
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_cache_and_invalidation(mock_db):
    """Verifies that short TTL cache serves repeated calls and clears on invalidation."""
    clock = TestClock()
    service = AnalyticsService(clock=clock, cache_ttl_seconds=30)
    admin_user = {"_id": ObjectId(), "role": UserRole.ADMIN.value, "name": "Admin"}

    s_res = await mock_db.students.insert_one({
        "erp_id": "CACHE_STU_1",
        "status": StudentStatus.ACTIVE.value,
    })

    res1 = await service.get_overview(admin_user)
    assert res1["total_students"] == 1

    # Insert another student in database
    await mock_db.students.insert_one({
        "erp_id": "CACHE_STU_2",
        "status": StudentStatus.ACTIVE.value,
    })

    # Within 30 seconds -> cached result returned (total_students still 1)
    res2 = await service.get_overview(admin_user)
    assert res2["total_students"] == 1

    # Invalidate cache -> reflects newly inserted student
    service.invalidate_cache()
    res3 = await service.get_overview(admin_user)
    assert res3["total_students"] == 2


# -----------------------------------------------------------------------------
# 7. FastAPI Endpoint Integration
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_api_endpoints(async_client, mock_db):
    """Full HTTP endpoint verification for all /analytics routes."""
    admin_id = ObjectId()
    await mock_db.users.insert_one({
        "_id": admin_id,
        "email": "admin.analytics@college.edu",
        "role": "admin",
        "name": "Super Admin",
        "token_version": 1,
    })

    admin_token = create_access_token(
        subject=str(admin_id),
        role="admin",
        token_version=1,
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Populate sample data
    s_res = await mock_db.students.insert_one({
        "erp_id": "API_ANALYTICS_1",
        "name": "Analytics Student",
        "department": "AI&DS",
        "semester": 2,
        "batch": "2024-28",
        "status": "active",
        "assigned_teacher_ids": [],
    })
    sid = str(s_res.inserted_id)

    await mock_db.risk_results.insert_one({
        "student_id": s_res.inserted_id,
        "score": 78.0,
        "level": RiskLevel.HIGH.value,
        "factors": [{"name": "attendance", "risk": 80.0}],
        "is_current": True,
    })
    await mock_db.performance.insert_one({
        "student_id": s_res.inserted_id,
        "semester": 2,
        "attendance": 55.0,
        "marks": 45.0,
        "backlogs": 1,
    })

    # 1. GET /analytics/overview
    ov_resp = await async_client.get("/analytics/overview", headers=headers)
    assert ov_resp.status_code == 200
    assert ov_resp.json()["total_students"] == 1
    assert ov_resp.json()["high_risk_count"] == 1

    # 2. GET /analytics/distribution
    dist_resp = await async_client.get("/analytics/distribution", headers=headers)
    assert dist_resp.status_code == 200
    assert len(dist_resp.json()["by_department"]) == 1

    # 3. GET /analytics/attendance-vs-risk
    att_resp = await async_client.get("/analytics/attendance-vs-risk", headers=headers)
    assert att_resp.status_code == 200
    assert len(att_resp.json()["points"]) == 1

    # 4. GET /analytics/marks-vs-risk
    marks_resp = await async_client.get("/analytics/marks-vs-risk", headers=headers)
    assert marks_resp.status_code == 200
    assert len(marks_resp.json()["points"]) == 1

    # 5. GET /analytics/by-department
    dept_resp = await async_client.get("/analytics/by-department", headers=headers)
    assert dept_resp.status_code == 200
    assert len(dept_resp.json()) == 1

    # 6. GET /analytics/by-semester
    sem_resp = await async_client.get("/analytics/by-semester", headers=headers)
    assert sem_resp.status_code == 200
    assert len(sem_resp.json()) == 1

    # 7. GET /analytics/trend?student_id=
    trend_resp = await async_client.get(f"/analytics/trend?student_id={sid}", headers=headers)
    assert trend_resp.status_code == 200
    assert trend_resp.json()["student_id"] == sid

    # 8. GET /analytics/export/high-risk
    csv_resp = await async_client.get("/analytics/export/high-risk", headers=headers)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "ERP ID" in csv_resp.text
    assert "API_ANALYTICS_1" in csv_resp.text

    # 9. POST /analytics/cache/invalidate
    inv_resp = await async_client.post("/analytics/cache/invalidate", headers=headers)
    assert inv_resp.status_code == 200
    assert "invalidated" in inv_resp.json()["message"]
