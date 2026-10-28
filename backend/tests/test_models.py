import pytest
from bson import ObjectId
from pydantic import ValidationError

from backend.app.models.common import convert_object_ids_for_mongo
from backend.app.models.counselling import AISource, CounsellingInDB, CounsellingStatus
from backend.app.models.performance import PerformanceInDB
from backend.app.models.risk import RiskFactor, RiskLevel, RiskResultInDB
from backend.app.models.student import StudentInDB, StudentStatus
from backend.app.models.user import UserInDB, UserRole, UserStatus


def test_user_model_valid():
    """Verifies valid UserInDB creation and email normalization."""
    user = UserInDB(
        name="Rahul Sharma",
        email="  Rahul.Sharma@Institute.EDU  ",
        phone_e164="+919876543210",
        password_hash="hashed_secret",
        role=UserRole.STUDENT,
        status=UserStatus.PENDING_VERIFICATION,
    )
    assert user.email == "rahul.sharma@institute.edu"
    assert user.phone_e164 == "+919876543210"
    assert user.failed_login_count == 0
    assert user.token_version == 0


def test_user_model_extra_fields_forbidden():
    """Ground Rule 5: Reject unknown fields with extra='forbid'."""
    with pytest.raises(ValidationError) as exc_info:
        UserInDB(
            name="Rahul Sharma",
            email="rahul@example.com",
            password_hash="hash",
            role=UserRole.STUDENT,
            malicious_injected_field="hacked",  # Unknown field
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_user_model_invalid_phone():
    """Verifies that phone numbers without leading '+' fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        UserInDB(
            name="Rahul Sharma",
            email="rahul@example.com",
            phone_e164="9876543210",  # Missing '+'
            password_hash="hash",
            role=UserRole.STUDENT,
        )
    assert "Phone number must be in E.164 format" in str(exc_info.value)


def test_student_roster_without_user():
    """Edge Case: Student exists in roster before user account registers."""
    student = StudentInDB(
        erp_id="  met101  ",
        name="Aarav Patel",
        department="AI&DS",
        semester=6,
        batch="2022-26",
    )
    assert student.erp_id == "MET101"  # Normalized to uppercase and trimmed
    assert student.user_id is None
    assert student.status == StudentStatus.ACTIVE


def test_student_department_transfer():
    """Edge Case: Student transfers department mid-semester while preserving ID."""
    student_id = str(ObjectId())
    student = StudentInDB(
        _id=student_id,
        erp_id="MET102",
        name="Neha Verma",
        department="Computer Science",
        semester=4,
        batch="2023-27",
    )
    # Department transfer
    transferred = student.model_copy(
        update={"department": "AI&DS", "status": StudentStatus.TRANSFERRED}
    )
    assert transferred.id == student_id
    assert transferred.department == "AI&DS"
    assert transferred.status == StudentStatus.TRANSFERRED


def test_student_invalid_semester():
    """Verifies that semester must be between 1 and 12."""
    with pytest.raises(ValidationError):
        StudentInDB(
            erp_id="MET103",
            name="Test",
            department="IT",
            semester=13,  # Out of range (max 12)
            batch="2023-27",
        )
    with pytest.raises(ValidationError):
        StudentInDB(
            erp_id="MET103",
            name="Test",
            department="IT",
            semester=0,  # Out of range (min 1)
            batch="2023-27",
        )


def test_performance_metrics_validation():
    """Verifies performance ranges and required classes_held when attendance is provided."""
    student_id = str(ObjectId())

    # Valid performance
    perf = PerformanceInDB(
        student_id=student_id,
        semester=6,
        academic_year="2025-26",
        attendance=75.5,
        classes_held=60,
        marks=82.0,
        backlogs=1,
        assignments=90.0,
        engagement=70.0,
    )
    assert perf.attendance == 75.5
    assert perf.version == 1

    # Attendance provided without classes_held -> must fail
    with pytest.raises(ValidationError) as exc_info:
        PerformanceInDB(
            student_id=student_id,
            semester=6,
            academic_year="2025-26",
            attendance=75.5,
            classes_held=None,  # Invalid
        )
    assert "classes_held is required when attendance is provided" in str(exc_info.value)

    # Out of range marks (> 100) -> must fail
    with pytest.raises(ValidationError):
        PerformanceInDB(
            student_id=student_id,
            semester=6,
            academic_year="2025-26",
            marks=105.0,
        )

    # Backlogs > 50 -> must fail
    with pytest.raises(ValidationError):
        PerformanceInDB(
            student_id=student_id,
            semester=6,
            academic_year="2025-26",
            backlogs=55,
        )


def test_risk_result_validation():
    """Verifies risk calculation document structure."""
    student_id = str(ObjectId())
    risk = RiskResultInDB(
        student_id=student_id,
        score=75.4,
        level=RiskLevel.HIGH,
        confidence=0.85,
        factors=[
            RiskFactor(name="attendance", risk=70.0, weight=0.3, contribution=21.0),
        ],
        overrides_applied=["attendance_below_50"],
        inputs_hash="a" * 64,
    )
    assert risk.level == RiskLevel.HIGH
    assert risk.is_current is True
    assert len(risk.factors) == 1


def test_counselling_model_validation():
    """Verifies counselling workflow model."""
    counsel = CounsellingInDB(
        student_id=str(ObjectId()),
        risk_result_id=str(ObjectId()),
        risk_level="High",
        ai_recommendation="Arrange mentoring session.",
        ai_source=AISource.TEMPLATE,
    )
    assert counsel.status == CounsellingStatus.PENDING
    assert counsel.ai_source == AISource.TEMPLATE


def test_convert_object_ids_for_mongo_persistence():
    """Verifies recursive conversion of string IDs to BSON ObjectIds."""
    valid_oid_str = "507f1f77bcf86cd799439011"
    raw = {
        "_id": valid_oid_str,
        "student_id": valid_oid_str,
        "assigned_teacher_ids": [valid_oid_str],
        "name": "Test",
    }
    converted = convert_object_ids_for_mongo(raw)
    assert isinstance(converted["_id"], ObjectId)
    assert isinstance(converted["student_id"], ObjectId)
    assert isinstance(converted["assigned_teacher_ids"][0], ObjectId)
    assert converted["name"] == "Test"
