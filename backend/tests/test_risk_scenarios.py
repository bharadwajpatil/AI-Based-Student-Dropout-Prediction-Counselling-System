import math
from datetime import UTC, datetime

import pytest
from bson import ObjectId
from hypothesis import given, settings as hyp_settings, strategies as st

from backend.app.models.risk import RiskLevel
from backend.app.risk.config import RiskThresholds, RiskWeights
from backend.app.risk.explain import format_factor_explanation, generate_risk_explanation
from backend.app.risk.risk_engine import (
    compute_inputs_hash,
    compute_student_risk,
    round_half_up,
)
from backend.app.risk.service import RiskService


# -----------------------------------------------------------------------------
# Scenarios R1 to R15
# -----------------------------------------------------------------------------

def test_r1_typical_borderline_student():
    """Scenario R1: att 72, marks 65, backlogs 1, assign 80 -> weighted 20.1 / 0.80 = 25.1 -> Low, confidence 0.80."""
    inputs = {
        "attendance": 72.0,
        "classes_held": 100,
        "marks": 65.0,
        "backlogs": 1,
        "assignments": 80.0,
        "prev_marks": None,
        "engagement": None,
    }
    result = compute_student_risk(inputs)
    assert result["confidence"] == 0.80
    assert result["score"] == pytest.approx(25.1, abs=0.1)
    assert result["level"] == RiskLevel.LOW.value
    assert not result["watchlist"]
    assert len(result["factors"]) == 4


def test_r2_multi_factor_collapse():
    """Scenario R2: att 55, marks 40 (prev 55), backlogs 3, assign 30, eng 20 -> 75.4 -> High."""
    inputs = {
        "attendance": 55.0,
        "classes_held": 100,
        "marks": 40.0,
        "prev_marks": 55.0,
        "backlogs": 3,
        "assignments": 30.0,
        "engagement": 20.0,
    }
    result = compute_student_risk(inputs)
    assert result["confidence"] == 1.00
    assert result["score"] == pytest.approx(75.4, abs=0.1)
    assert result["level"] == RiskLevel.HIGH.value
    assert len(result["overrides_applied"]) == 1  # backlogs_ge_2
    assert not result["watchlist"]


def test_r3_hidden_decline_watchlist():
    """Scenario R3: att 95, marks 70 (prev 88), backlogs 0, assign 90, eng 70 -> score ~16.0 -> Low but watchlist = true."""
    inputs = {
        "attendance": 95.0,
        "classes_held": 100,
        "marks": 70.0,
        "prev_marks": 88.0,
        "backlogs": 0,
        "assignments": 90.0,
        "engagement": 70.0,
    }
    result = compute_student_risk(inputs)
    assert result["score"] == pytest.approx(16.0, abs=0.1)
    assert result["level"] == RiskLevel.LOW.value
    assert result["watchlist"] is True
    assert "trend_drop_critical" in result["overrides_applied"]


def test_r4_override_attendance_collapse():
    """Scenario R4: att 48, marks 85, backlogs 0, assign 95, eng 80 -> weighted ~26.8 -> floor 70.0 -> High."""
    inputs = {
        "attendance": 48.0,
        "classes_held": 100,
        "marks": 85.0,
        "backlogs": 0,
        "assignments": 95.0,
        "engagement": 80.0,
    }
    result = compute_student_risk(inputs)
    assert result["score"] == 70.0
    assert result["level"] == RiskLevel.HIGH.value
    assert "attendance_below_50" in result["overrides_applied"]


def test_r5_insufficient_data():
    """Scenario R5: att 60 only, everything else null -> confidence 0.30 -> Insufficient Data."""
    inputs = {
        "attendance": 60.0,
        "classes_held": 100,
    }
    result = compute_student_risk(inputs)
    assert result["confidence"] == 0.30
    assert result["level"] == RiskLevel.INSUFFICIENT_DATA.value
    assert result["score"] is None


def test_r6_tiny_attendance_sample():
    """Scenario R6: att 40 but classes_held = 8, marks 80, backlogs 0, assign 85 -> att ignored -> Low."""
    inputs = {
        "attendance": 40.0,
        "classes_held": 8,  # < 20 -> ignored
        "marks": 80.0,
        "backlogs": 0,
        "assignments": 85.0,
    }
    result = compute_student_risk(inputs)
    # Available: marks (0.25), backlogs (0.15), assignments (0.10) = 0.50 confidence
    assert result["confidence"] == 0.50
    assert result["score"] == 0.0
    assert result["level"] == RiskLevel.LOW.value
    # Attendance factor notes small sample
    att_factor = next(f for f in result["factors"] if f["name"] == "attendance")
    assert "sample too small" in att_factor["explanation"]


def test_r7_rounding_boundary():
    """Scenario R7: score 39.95 rounds half-up to 40.0 -> Medium."""
    assert round_half_up(39.95, 1) == 40.0

    # Test via engine with craft weights/inputs:
    # att=50 -> risk=80. w=0.5. (80 * 0.5 = 40.0)
    # But let's check half-up round of 39.94 vs 39.95:
    assert round_half_up(39.94, 1) == 39.9
    assert round_half_up(39.95, 1) == 40.0


def test_r8_hysteresis_sequence():
    """
    Scenario R8: scores in sequence 69.0 -> 70.4 -> 68.9 -> 66.9
    Sequence of levels: Medium -> High -> High (held) -> Medium.
    """
    thresholds = RiskThresholds()

    from backend.app.risk.risk_engine import _classify_with_hysteresis

    # 1. Score 69.0, no previous level -> Medium
    l1 = _classify_with_hysteresis(69.0, previous_level=None, thresholds=thresholds)
    assert l1 == RiskLevel.MEDIUM.value

    # 2. Score 70.4, previous Medium -> High (immediate upgrade)
    l2 = _classify_with_hysteresis(70.4, previous_level=l1, thresholds=thresholds)
    assert l2 == RiskLevel.HIGH.value

    # 3. Score 68.9, previous High -> High (held! requires < 67 to downgrade)
    l3 = _classify_with_hysteresis(68.9, previous_level=l2, thresholds=thresholds)
    assert l3 == RiskLevel.HIGH.value

    # 4. Score 66.9, previous High -> Medium (downgraded because < 67)
    l4 = _classify_with_hysteresis(66.9, previous_level=l3, thresholds=thresholds)
    assert l4 == RiskLevel.MEDIUM.value

    # 5. Score 38.0, previous Medium -> Medium (held! requires < 37 to downgrade)
    l5 = _classify_with_hysteresis(38.0, previous_level=l4, thresholds=thresholds)
    assert l5 == RiskLevel.MEDIUM.value

    # 6. Score 36.9, previous Medium -> Low (downgraded because < 37)
    l6 = _classify_with_hysteresis(36.9, previous_level=l5, thresholds=thresholds)
    assert l6 == RiskLevel.LOW.value


def test_r9_backlog_floor():
    """Scenario R9: backlogs 2, everything else perfect -> floor 40.0 -> Medium."""
    inputs = {
        "attendance": 100.0,
        "classes_held": 100,
        "marks": 100.0,
        "backlogs": 2,
        "assignments": 100.0,
        "engagement": 100.0,
    }
    result = compute_student_risk(inputs)
    assert result["score"] == 40.0
    assert result["level"] == RiskLevel.MEDIUM.value
    assert "backlogs_ge_2" in result["overrides_applied"]


def test_r10_performance_improvement():
    """Scenario R10: marks rose 50 -> 80 -> trend risk is 0 (never negative)."""
    inputs = {
        "attendance": 90.0,
        "classes_held": 100,
        "marks": 80.0,
        "prev_marks": 50.0,
        "backlogs": 0,
        "assignments": 90.0,
        "engagement": 90.0,
    }
    result = compute_student_risk(inputs)
    trend_factor = next(f for f in result["factors"] if f["name"] == "trend")
    assert trend_factor["risk"] == 0.0
    assert trend_factor["contribution"] == 0.0


def test_r11_extreme_worst_student():
    """Scenario R11: att 0, marks 0, backlogs 10, assign 0, eng 0, prev marks 100 -> score 100.0."""
    inputs = {
        "attendance": 0.0,
        "classes_held": 100,
        "marks": 0.0,
        "prev_marks": 100.0,
        "backlogs": 10,
        "assignments": 0.0,
        "engagement": 0.0,
    }
    result = compute_student_risk(inputs)
    assert result["score"] == 100.0
    assert result["level"] == RiskLevel.HIGH.value


def test_r12_perfect_student():
    """Scenario R12: att 100, marks 100, backlogs 0, assign 100, eng 100 -> score 0.0 -> Low."""
    inputs = {
        "attendance": 100.0,
        "classes_held": 100,
        "marks": 100.0,
        "backlogs": 0,
        "assignments": 100.0,
        "engagement": 100.0,
    }
    result = compute_student_risk(inputs)
    assert result["score"] == 0.0
    assert result["level"] == RiskLevel.LOW.value


def test_r13_bad_input_defensive_clamping():
    """Scenario R13: att 120 / -5 / NaN / 'abc' -> engine clamps defensively and never crashes."""
    inputs = {
        "attendance": 120.0,  # Clamped to 100.0
        "classes_held": 100,
        "marks": -5.0,  # Clamped to 0.0
        "backlogs": "invalid",  # Ignored safely
        "assignments": float("nan"),  # Non-finite ignored safely
        "engagement": "80",  # String converted safely
    }
    result = compute_student_risk(inputs)
    assert result["score"] is not None
    assert 0.0 <= result["score"] <= 100.0


@pytest.mark.asyncio
async def test_r14_idempotency(mock_db):
    """Scenario R14: Recomputing twice with same inputs produces single risk row and returns existing."""
    risk_srv = RiskService()

    # Create a student
    student_doc = {
        "erp_id": "IDEMP101",
        "name": "Idempotent Student",
        "department": "AI&DS",
        "semester": 4,
        "batch": "2024-28",
        "assigned_teacher_ids": [],
        "status": "active",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    res = await mock_db.students.insert_one(student_doc)
    student_id = res.inserted_id

    # Add performance
    await mock_db.performance.insert_one({
        "student_id": student_id,
        "semester": 4,
        "academic_year": "2025-26",
        "attendance": 75.0,
        "classes_held": 100,
        "marks": 65.0,
        "backlogs": 1,
        "assignments": 80.0,
        "engagement": 70.0,
        "version": 1,
        "updated_at": datetime.now(UTC),
    })

    # First recompute
    row1 = await risk_srv.recompute_student_risk(student_id=student_id)
    assert row1 is not None

    # Count rows in risk_results
    count1 = await mock_db.risk_results.count_documents({"student_id": student_id})
    assert count1 == 1

    # Second recompute with same inputs
    row2 = await risk_srv.recompute_student_risk(student_id=student_id)
    assert row2["_id"] == row1["_id"]

    # Still exactly 1 row!
    count2 = await mock_db.risk_results.count_documents({"student_id": student_id})
    assert count2 == 1


@pytest.mark.asyncio
async def test_r15_engine_version_change(mock_db):
    """Scenario R15: Bumping engine version creates new row with new version; old rows untouched."""
    risk_srv = RiskService()

    student_doc = {
        "erp_id": "VER101",
        "name": "Version Student",
        "department": "AI&DS",
        "semester": 4,
        "batch": "2024-28",
        "assigned_teacher_ids": [],
        "status": "active",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    res = await mock_db.students.insert_one(student_doc)
    student_id = res.inserted_id

    await mock_db.performance.insert_one({
        "student_id": student_id,
        "semester": 4,
        "academic_year": "2025-26",
        "attendance": 60.0,
        "classes_held": 100,
        "marks": 50.0,
        "backlogs": 2,
        "assignments": 60.0,
        "engagement": 50.0,
        "version": 1,
        "updated_at": datetime.now(UTC),
    })

    # Version 1.0.0
    row1 = await risk_srv.recompute_student_risk(student_id=student_id, engine_version="1.0.0")
    assert row1["engine_version"] == "1.0.0"
    assert row1["is_current"] is True

    # Version 1.1.0 with bumped weights
    bumped_weights = RiskWeights(attendance=0.35, marks=0.20, backlogs=0.15, trend=0.12, assignments=0.10, engagement=0.08)
    row2 = await risk_srv.recompute_student_risk(
        student_id=student_id,
        weights=bumped_weights,
        engine_version="1.1.0",
    )
    assert row2["_id"] != row1["_id"]
    assert row2["engine_version"] == "1.1.0"
    assert row2["is_current"] is True

    # Verify old row has is_current = False and remains untouched
    old_row = await mock_db.risk_results.find_one({"_id": row1["_id"]})
    assert old_row["engine_version"] == "1.0.0"
    assert old_row["is_current"] is False


# -----------------------------------------------------------------------------
# Property-Based Testing (Hypothesis)
# -----------------------------------------------------------------------------

@hyp_settings(max_examples=100)
@given(
    att=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    marks=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    backlogs=st.integers(min_value=0, max_value=10),
    assign=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    eng=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_property_score_always_bounded(att, marks, backlogs, assign, eng):
    """Property test: Risk score is always bounded in [0, 100]."""
    inputs = {
        "attendance": att,
        "classes_held": 100,
        "marks": marks,
        "backlogs": backlogs,
        "assignments": assign,
        "engagement": eng,
    }
    result = compute_student_risk(inputs)
    assert result["score"] is not None
    assert 0.0 <= result["score"] <= 100.0
    assert result["level"] in (RiskLevel.LOW.value, RiskLevel.MEDIUM.value, RiskLevel.HIGH.value)


@hyp_settings(max_examples=100)
@given(
    att1=st.floats(min_value=0.0, max_value=49.0, allow_nan=False, allow_infinity=False),
    att2=st.floats(min_value=50.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    marks=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    backlogs=st.integers(min_value=0, max_value=1),
    assign=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    eng=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_property_monotonic_attendance(att1, att2, marks, backlogs, assign, eng):
    """
    Property test: Monotonicity — Lowering attendance never lowers risk score.
    If att1 < att2, risk(att1) >= risk(att2).
    """
    inputs_low_att = {
        "attendance": att1,
        "classes_held": 100,
        "marks": marks,
        "backlogs": backlogs,
        "assignments": assign,
        "engagement": eng,
    }
    inputs_high_att = {
        "attendance": att2,
        "classes_held": 100,
        "marks": marks,
        "backlogs": backlogs,
        "assignments": assign,
        "engagement": eng,
    }
    res_low = compute_student_risk(inputs_low_att)
    res_high = compute_student_risk(inputs_high_att)
    assert res_low["score"] >= res_high["score"]


def test_explain_functions():
    """Verifies factor explanation formatting coverage."""
    exp1 = format_factor_explanation("attendance", 45.0, 90.0, classes_held=100)
    assert "critically low" in exp1

    exp2 = format_factor_explanation("attendance", None, 0.0)
    assert "not recorded" in exp2

    exp3 = format_factor_explanation("marks", 30.0, 100.0)
    assert "critical" in exp3

    exp4 = format_factor_explanation("backlogs", 5, 100.0)
    assert "Severe" in exp4

    exp5 = format_factor_explanation("trend", {"drop": 18.0}, 90.0)
    assert "Sharp" in exp5

    pkg = generate_risk_explanation(
        score=75.0,
        level="High",
        confidence=1.0,
        factors=[{"name": "attendance", "risk": 80.0, "weight": 0.3, "contribution": 24.0}],
        overrides_applied=["attendance_below_50"],
        watchlist=True,
    )
    assert "Critical override" in pkg["summary"]
    assert pkg["watchlist"] is True


def test_config_as_dict():
    """Verifies RiskWeights as_dict method."""
    weights = RiskWeights()
    d = weights.as_dict()
    assert d["attendance"] == 0.30
    assert d["marks"] == 0.25
    assert d["backlogs"] == 0.15
    assert d["trend"] == 0.12
    assert d["assignments"] == 0.10
    assert d["engagement"] == 0.08


def test_explain_comprehensive_coverage():
    """Exercises all factor explanation formatting branches."""
    assert "Attendance is 80.0%" in format_factor_explanation("attendance", 80.0, 20.0, classes_held=100)
    assert "Average marks are 80.0%" in format_factor_explanation("marks", 80.0, 0.0)
    assert "Marks data not recorded." in format_factor_explanation("marks", None, 0.0)
    assert "Moderate backlog count: 3 active backlogs." in format_factor_explanation("backlogs", 3, 75.0)
    assert "1 active backlog." in format_factor_explanation("backlogs", 1, 25.0)
    assert "No active backlogs." in format_factor_explanation("backlogs", 0, 0.0)
    assert "Backlog data not recorded." in format_factor_explanation("backlogs", None, 0.0)
    assert "Marks dropped by 10.0" in format_factor_explanation("trend", {"drop": 10.0}, 50.0)
    assert "Academic performance is stable or improving." in format_factor_explanation("trend", {"drop": 0.0}, 0.0)
    assert "Previous semester marks not available" in format_factor_explanation("trend", None, 0.0)
    assert "Assignment submission rate is 90.0%" in format_factor_explanation("assignments", 90.0, 0.0)
    assert "Assignment completion data not recorded." in format_factor_explanation("assignments", None, 0.0)
    assert "Class and LMS engagement score is 80.0%" in format_factor_explanation("engagement", 80.0, 20.0)
    assert "Engagement activity not recorded." in format_factor_explanation("engagement", None, 0.0)
    assert "Custom risk is 20.0%" in format_factor_explanation("custom", 10.0, 20.0)

    # Explanations for all overrides
    pkg1 = generate_risk_explanation(
        score=None,
        level="Insufficient Data",
        confidence=0.3,
        factors=[],
        overrides_applied=[],
        watchlist=False,
    )
    assert "Additional data needed" in pkg1["summary"]

    pkg2 = generate_risk_explanation(
        score=75.0,
        level="High",
        confidence=1.0,
        factors=[],
        overrides_applied=["backlogs_ge_4", "backlogs_ge_2", "trend_drop_critical"],
        watchlist=False,
    )
    assert "4 or more backlogs" in pkg2["summary"]
    assert "2 or more backlogs" in pkg2["summary"]
    assert "16 or more points" in pkg2["summary"]

    pkg3 = generate_risk_explanation(
        score=10.0,
        level="Low",
        confidence=1.0,
        factors=[],
        overrides_applied=[],
        watchlist=False,
    )
    assert "baseline" in pkg3["summary"]


def test_risk_engine_null_attendance_and_empty_inputs():
    """Verifies risk calculation when attendance is null or classes_held is non-integer."""
    inputs = {
        "attendance": None,
        "classes_held": "not_an_int",
        "marks": 70.0,
        "backlogs": 1,
        "assignments": 80.0,
    }
    res = compute_student_risk(inputs)
    assert res["confidence"] == 0.50
    assert res["score"] is not None

    # Completely empty inputs
    res_empty = compute_student_risk({})
    assert res_empty["confidence"] == 0.0
    assert res_empty["level"] == RiskLevel.INSUFFICIENT_DATA.value
    assert res_empty["score"] is None


@pytest.mark.asyncio
async def test_risk_service_edge_cases(mock_db):
    """Exercises RiskService student not found, no performance data, and auto-counselling."""
    risk_srv = RiskService()

    # 1. Non-existent student
    res = await risk_srv.recompute_student_risk(student_id=ObjectId())
    assert res is None

    # 2. Student with no performance records
    student_res = await mock_db.students.insert_one({
        "erp_id": "NOPERF101",
        "name": "No Perf Student",
        "department": "AI&DS",
        "semester": 1,
        "batch": "2024-28",
        "assigned_teacher_ids": [],
        "status": "active",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })
    sid = student_res.inserted_id

    res2 = await risk_srv.recompute_student_risk(student_id=sid)
    assert res2["level"] == RiskLevel.INSUFFICIENT_DATA.value

    # 3. High-risk student auto-creates pending counselling case
    teacher_id = ObjectId()
    high_student_res = await mock_db.students.insert_one({
        "erp_id": "HIGH_STU_101",
        "name": "High Risk Student",
        "department": "AI&DS",
        "semester": 2,
        "batch": "2024-28",
        "assigned_teacher_ids": [teacher_id],
        "status": "active",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })
    high_sid = high_student_res.inserted_id

    # Semester 1 performance
    await mock_db.performance.insert_one({
        "student_id": high_sid,
        "semester": 1,
        "academic_year": "2025-26",
        "attendance": 80.0,
        "classes_held": 100,
        "marks": 70.0,
        "backlogs": 0,
        "assignments": 80.0,
        "version": 1,
        "updated_at": datetime.now(UTC),
    })

    # Semester 2 performance (multi-factor collapse -> High)
    await mock_db.performance.insert_one({
        "student_id": high_sid,
        "semester": 2,
        "academic_year": "2025-26",
        "attendance": 45.0,  # below 50 -> override to High!
        "classes_held": 100,
        "marks": 35.0,
        "backlogs": 4,
        "assignments": 30.0,
        "version": 1,
        "updated_at": datetime.now(UTC),
    })

    # Recompute targeting semester 2
    high_risk = await risk_srv.recompute_student_risk(student_id=high_sid, semester=2)
    assert high_risk["level"] == RiskLevel.HIGH.value

    # Verify counselling stub was automatically created
    counselling_case = await mock_db.counselling.find_one({"student_id": high_sid})
    assert counselling_case is not None
    assert counselling_case["status"] == "pending"
    assert counselling_case["teacher_id"] == teacher_id
    assert counselling_case["risk_level"] == "High"

    # Recompute targeting a non-matching semester falls back to last semester
    fallback_res = await risk_srv.recompute_student_risk(student_id=high_sid, semester=99)
    assert fallback_res is not None

    # Update performance with new data so idempotency hash differs, but existing counselling is preserved
    await mock_db.performance.update_one(
        {"student_id": high_sid, "semester": 2},
        {"$set": {"backlogs": 5}},
    )
    await risk_srv.recompute_student_risk(student_id=high_sid, semester=2)
    counselling_count = await mock_db.counselling.count_documents({"student_id": high_sid})
    assert counselling_count == 1

    # Custom/unrecognized override explanation
    pkg_custom = generate_risk_explanation(
        score=70.0,
        level="High",
        confidence=1.0,
        factors=[],
        overrides_applied=["unrecognized_override"],
        watchlist=False,
    )
    assert pkg_custom is not None

