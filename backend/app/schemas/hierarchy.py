from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class HierarchySchemaBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


# Admin -> HOD
class CreateHODRequest(HierarchySchemaBase):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    phone: str | None = None
    employee_id: str | None = Field(default=None, max_length=50)
    department: str = Field(..., min_length=1, max_length=100)
    designation: str = Field(default="Head of Department", max_length=100)
    password: str = Field(..., min_length=6)


class UpdateHODRequest(HierarchySchemaBase):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    employee_id: str | None = None
    department: str | None = None
    designation: str | None = None
    status: str | None = None


class HODResponse(HierarchySchemaBase):
    id: str
    name: str
    email: str
    phone: str | None = None
    employee_id: str | None = None
    department: str
    designation: str | None = None
    role: str = "hod"
    status: str = "active"
    teachers_count: int = 0
    students_count: int = 0
    created_at: datetime


# HOD -> Teacher
class CreateTeacherRequest(HierarchySchemaBase):
    name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    phone: str | None = None
    employee_id: str | None = Field(default=None, max_length=50)
    department: str = Field(..., min_length=1, max_length=100)
    designation: str = Field(default="Assistant Professor", max_length=100)
    password: str = Field(..., min_length=6)


class UpdateTeacherRequest(HierarchySchemaBase):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    employee_id: str | None = None
    department: str | None = None
    designation: str | None = None
    status: str | None = None


class TeacherResponse(HierarchySchemaBase):
    id: str
    name: str
    email: str
    phone: str | None = None
    employee_id: str | None = None
    department: str
    designation: str | None = None
    role: str = "teacher"
    status: str = "active"
    hod_id: str | None = None
    assigned_subjects_count: int = 0
    assigned_students_count: int = 0
    created_at: datetime


# AI Chatbot & Study Plan
class ChatMessage(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class AIChatRequest(HierarchySchemaBase):
    message: str = Field(..., min_length=1)
    student_id: str | None = None  # If teacher is chatting about student, or if student themselves
    conversation_history: list[ChatMessage] = Field(default_factory=list)


class AIChatResponse(HierarchySchemaBase):
    reply: str
    suggested_actions: list[str] = Field(default_factory=list)
    sources_consulted: list[str] = Field(default_factory=list)


class StudyPlanResponse(HierarchySchemaBase):
    id: str
    student_id: str
    student_name: str
    weekly_schedule: dict[str, list[str]]
    backlog_plans: list[dict]
    weak_areas: list[str]
    overall_advice: str
    target_attendance: float
    generated_at: datetime


# Student My Performance Dashboard (Sections 1-9)
class SubjectPerformanceItem(HierarchySchemaBase):
    subject_id: str
    subject_name: str
    subject_code: str
    semester: int
    marks: float
    grade: str
    attendance: float
    is_backlog: bool
    status: str  # "Strong" (>=75), "Average" (50-74), "Weak" (40-49), "Backlog" (<40 or F)
    attendance_warning: bool = False


class SemesterTrendItem(HierarchySchemaBase):
    semester: int
    academic_year: str
    marks: float
    attendance: float
    backlogs: int


class BacklogDetailItem(HierarchySchemaBase):
    subject_id: str
    subject_name: str
    subject_code: str
    previous_marks: float
    status: str = "Backlog"
    priority: str  # "HIGH", "MEDIUM"
    action_advice: str


class StudentPerformanceDashboardResponse(HierarchySchemaBase):
    student_id: str
    student_name: str
    erp_id: str
    department: str
    semester: int
    batch: str
    course: str | None = None

    # Section 3: Performance Summary
    average_marks: float
    cgpa: float
    overall_attendance: float
    total_subjects: int
    passed_subjects: int
    failed_subjects: int
    active_backlogs: int
    current_risk_level: str
    risk_score: float | None = None

    # Section 4: Subject-wise Performance
    subjects: list[SubjectPerformanceItem]

    # Section 5: Performance Trend
    historical_trend: list[SemesterTrendItem]
    trend_direction: str  # "Improving", "Stable", "Declining"

    # Section 6: Attendance Warnings
    attendance_warnings: list[str]

    # Section 7: Backlogs
    backlogs_list: list[BacklogDetailItem]

    # Section 8: Dropout Risk Factors
    risk_factors: list[dict] = Field(default_factory=list)

    # Section 9: Performance Improvement Recommendations
    recommendations: list[str] = Field(default_factory=list)

