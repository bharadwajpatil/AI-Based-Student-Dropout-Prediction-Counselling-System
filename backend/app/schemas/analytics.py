from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsOverviewResponse(BaseModel):
    """Overall high-level KPI dashboard overview."""

    model_config = ConfigDict(extra="forbid")

    total_students: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    insufficient_data_count: int
    counselling_pending_count: int
    watchlist_count: int
    average_attendance: float | None = None
    average_marks: float | None = None
    last_updated: datetime


class DepartmentDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: str
    high: int
    medium: int
    low: int
    insufficient_data: int
    total: int


class SemesterDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester: int
    high: int
    medium: int
    low: int
    insufficient_data: int
    total: int


class AnalyticsDistributionResponse(BaseModel):
    """Categorized risk distribution breakdown."""

    model_config = ConfigDict(extra="forbid")

    by_department: list[DepartmentDistribution]
    by_semester: list[SemesterDistribution]


class AttendanceVsRiskPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    erp_id: str
    department: str
    semester: int
    attendance: float
    risk_score: float
    risk_level: str


class AttendanceVsRiskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[AttendanceVsRiskPoint]
    correlation: float | None = None


class MarksVsRiskPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    erp_id: str
    department: str
    semester: int
    marks: float
    risk_score: float
    risk_level: str


class MarksVsRiskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[MarksVsRiskPoint]
    correlation: float | None = None


class DepartmentAnalyticsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: str
    total_students: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    insufficient_data_count: int
    average_attendance: float | None = None
    average_marks: float | None = None
    average_risk_score: float | None = None


class SemesterAnalyticsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester: int
    total_students: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    insufficient_data_count: int
    average_attendance: float | None = None
    average_marks: float | None = None
    average_risk_score: float | None = None


class SemesterTrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester: int
    academic_year: str
    attendance: float | None = None
    marks: float | None = None
    backlogs: int = 0
    risk_score: float | None = None
    risk_level: str | None = None
    computed_at: datetime | None = None


class StudentTrendResponse(BaseModel):
    """Historical progression of a student's risk and academic metrics."""

    model_config = ConfigDict(extra="forbid")

    student_id: str
    erp_id: str
    name: str
    department: str
    current_semester: int
    trajectory: list[SemesterTrendPoint]
