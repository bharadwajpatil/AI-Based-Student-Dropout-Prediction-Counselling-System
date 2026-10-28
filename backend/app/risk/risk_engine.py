import hashlib
import json
import logging
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from backend.app.models.risk import RiskLevel
from backend.app.risk.config import (
    ENGINE_VERSION,
    RiskThresholds,
    RiskWeights,
    default_thresholds,
    default_weights,
)
from backend.app.risk.explain import format_factor_explanation

logger = logging.getLogger("student-dropout-system.risk.engine")


def round_half_up(val: float, decimals: int = 1) -> float:
    """Rounds float using exact half-up rounding (39.95 -> 40.0)."""
    d = Decimal(str(val))
    q = Decimal("10") ** -decimals
    return float(d.quantize(q, rounding=ROUND_HALF_UP))


def clamp(val: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamps value defensively between min_val and max_val."""
    return max(min_val, min(max_val, val))


def _clean_numeric(val: Any) -> float | None:
    """Safely extracts a finite float or returns None if invalid/non-numeric."""
    if val is None:
        return None
    try:
        f = float(val)
        if not math.isfinite(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def compute_inputs_hash(
    inputs: dict[str, Any],
    engine_version: str = ENGINE_VERSION,
) -> str:
    """Computes a deterministic SHA-256 hash over normalized input values for idempotency."""
    normalized: dict[str, Any] = {
        "engine_version": engine_version,
        "attendance": inputs.get("attendance"),
        "classes_held": inputs.get("classes_held"),
        "marks": inputs.get("marks"),
        "prev_marks": inputs.get("prev_marks"),
        "backlogs": inputs.get("backlogs"),
        "assignments": inputs.get("assignments"),
        "engagement": inputs.get("engagement"),
    }
    dumped = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def compute_student_risk(
    inputs: dict[str, Any],
    previous_level: str | None = None,
    weights: RiskWeights = default_weights,
    thresholds: RiskThresholds = default_thresholds,
    engine_version: str = ENGINE_VERSION,
) -> dict[str, Any]:
    """
    Pure, deterministic risk engine.
    Calculates student dropout risk from input metrics.
    Ground Rule 2: Pure function with no database, clock, or network calls.
    """
    factors: list[dict[str, Any]] = []
    overrides_applied: list[str] = []
    watchlist: bool = False

    raw_att = _clean_numeric(inputs.get("attendance"))
    raw_classes = inputs.get("classes_held")
    raw_marks = _clean_numeric(inputs.get("marks"))
    raw_prev_marks = _clean_numeric(inputs.get("prev_marks"))
    raw_backlogs = _clean_numeric(inputs.get("backlogs"))
    raw_assign = _clean_numeric(inputs.get("assignments"))
    raw_eng = _clean_numeric(inputs.get("engagement"))

    # Defensive range clamping
    att = clamp(raw_att, 0.0, 100.0) if raw_att is not None else None
    classes_held = int(raw_classes) if raw_classes is not None and str(raw_classes).isdigit() else None
    marks = clamp(raw_marks, 0.0, 100.0) if raw_marks is not None else None
    prev_marks = clamp(raw_prev_marks, 0.0, 100.0) if raw_prev_marks is not None else None
    backlogs = clamp(raw_backlogs, 0.0, 50.0) if raw_backlogs is not None else None
    assignments = clamp(raw_assign, 0.0, 100.0) if raw_assign is not None else None
    engagement = clamp(raw_eng, 0.0, 100.0) if raw_eng is not None else None

    # 1. Component 1: Attendance
    # Sample size rule: if classes_held < min_classes_held, ignore attendance (Scenario R6)
    att_available = False
    if att is not None:
        if classes_held is not None and classes_held < thresholds.min_classes_held:
            # Sample size too small, treat as unavailable
            factors.append({
                "name": "attendance",
                "risk": 0.0,
                "weight": weights.attendance,
                "contribution": 0.0,
                "explanation": format_factor_explanation("attendance", att, 0.0, classes_held),
            })
        else:
            att_available = True
            att_risk = clamp((90.0 - att) / 50.0 * 100.0)
            factors.append({
                "name": "attendance",
                "risk": round_half_up(att_risk, 1),
                "weight": weights.attendance,
                "contribution": round_half_up(att_risk * weights.attendance, 1),
                "raw_risk": att_risk,
                "explanation": format_factor_explanation("attendance", att, att_risk, classes_held),
            })

    # 2. Component 2: Marks
    marks_available = False
    if marks is not None:
        marks_available = True
        marks_risk = clamp((75.0 - marks) / 45.0 * 100.0)
        factors.append({
            "name": "marks",
            "risk": round_half_up(marks_risk, 1),
            "weight": weights.marks,
            "contribution": round_half_up(marks_risk * weights.marks, 1),
            "raw_risk": marks_risk,
            "explanation": format_factor_explanation("marks", marks, marks_risk),
        })

    # 3. Component 3: Backlogs
    backlogs_available = False
    if backlogs is not None:
        backlogs_available = True
        backlog_risk = min(backlogs * 25.0, 100.0)
        factors.append({
            "name": "backlogs",
            "risk": round_half_up(backlog_risk, 1),
            "weight": weights.backlogs,
            "contribution": round_half_up(backlog_risk * weights.backlogs, 1),
            "raw_risk": backlog_risk,
            "explanation": format_factor_explanation("backlogs", backlogs, backlog_risk),
        })

    # 4. Component 4: Trend
    trend_available = False
    trend_risk = 0.0
    if prev_marks is not None and marks is not None:
        trend_available = True
        drop = prev_marks - marks
        if drop <= 0.0:
            trend_risk = 0.0
        else:
            trend_risk = clamp(drop / 20.0 * 100.0)

        factors.append({
            "name": "trend",
            "risk": round_half_up(trend_risk, 1),
            "weight": weights.trend,
            "contribution": round_half_up(trend_risk * weights.trend, 1),
            "raw_risk": trend_risk,
            "explanation": format_factor_explanation("trend", {"drop": max(0.0, drop)}, trend_risk),
        })

    # 5. Component 5: Assignments
    assign_available = False
    if assignments is not None:
        assign_available = True
        assign_risk = clamp((80.0 - assignments) / 60.0 * 100.0)
        factors.append({
            "name": "assignments",
            "risk": round_half_up(assign_risk, 1),
            "weight": weights.assignments,
            "contribution": round_half_up(assign_risk * weights.assignments, 1),
            "raw_risk": assign_risk,
            "explanation": format_factor_explanation("assignments", assignments, assign_risk),
        })

    # 6. Component 6: Engagement
    eng_available = False
    if engagement is not None:
        eng_available = True
        eng_risk = clamp(100.0 - engagement)
        factors.append({
            "name": "engagement",
            "risk": round_half_up(eng_risk, 1),
            "weight": weights.engagement,
            "contribution": round_half_up(eng_risk * weights.engagement, 1),
            "raw_risk": eng_risk,
            "explanation": format_factor_explanation("engagement", engagement, eng_risk),
        })

    # 7. Confidence & Weighted Score
    # Available weights sum
    available_weight = sum(
        f["weight"] for f in factors if f.get("raw_risk") is not None
    )
    confidence = round_half_up(available_weight, 2)

    # Check for Insufficient Data
    if confidence < thresholds.min_confidence or available_weight == 0:
        # Sort factors
        factors.sort(key=lambda x: x.get("contribution", 0.0), reverse=True)
        # Strip internal raw_risk key
        for f in factors:
            f.pop("raw_risk", None)

        return {
            "score": None,
            "level": RiskLevel.INSUFFICIENT_DATA.value,
            "confidence": confidence,
            "watchlist": False,
            "factors": factors,
            "overrides_applied": [],
            "engine_version": engine_version,
            "inputs_hash": compute_inputs_hash(inputs, engine_version),
        }

    # Calculate weighted score renormalised over available weights
    weighted_sum = sum(f["raw_risk"] * f["weight"] for f in factors if "raw_risk" in f)
    raw_score = weighted_sum / available_weight

    # 8. Overrides (applied after weighted score)
    # Rule 1: Attendance collapse (< 50%) -> High (score >= 70)
    if att_available and att is not None and att < thresholds.attendance_override_threshold:
        if raw_score < 70.0:
            raw_score = 70.0
        overrides_applied.append("attendance_below_50")

    # Rule 2: Backlogs >= 4 -> High (score >= 70)
    if backlogs_available and backlogs is not None and backlogs >= thresholds.backlogs_high_override:
        if raw_score < 70.0:
            raw_score = 70.0
        overrides_applied.append("backlogs_ge_4")

    # Rule 3: Backlogs >= 2 (and < 4) -> Medium floor (score >= 40)
    elif backlogs_available and backlogs is not None and backlogs >= thresholds.backlogs_med_override:
        if raw_score < 40.0:
            raw_score = 40.0
        overrides_applied.append("backlogs_ge_2")

    # Rule 4: Trend risk >= 80 (marks dropped by >= 16 pts) -> watchlist = True
    if trend_available and trend_risk >= thresholds.trend_critical_risk:
        watchlist = True
        overrides_applied.append("trend_drop_critical")

    # 9. Half-up Rounding (Scenario R7)
    final_score = round_half_up(raw_score, 1)

    # 10. Hysteresis Classification (Scenario R8)
    level = _classify_with_hysteresis(
        score=final_score,
        previous_level=previous_level,
        thresholds=thresholds,
    )

    # Sort factors by contribution descending
    factors.sort(key=lambda x: x.get("contribution", 0.0), reverse=True)
    for f in factors:
        f.pop("raw_risk", None)

    return {
        "score": final_score,
        "level": level,
        "confidence": confidence,
        "watchlist": watchlist,
        "factors": factors,
        "overrides_applied": overrides_applied,
        "engine_version": engine_version,
        "inputs_hash": compute_inputs_hash(inputs, engine_version),
    }


def _classify_with_hysteresis(
    score: float,
    previous_level: str | None,
    thresholds: RiskThresholds,
) -> str:
    """
    Applies hysteresis stability:
    - Upgrading is immediate (score >= 70 -> High; score >= 40 -> Medium).
    - Downgrading requires dropping at least 3 points below the threshold
      (High -> Medium requires < 67; Medium -> Low requires < 37).
    """
    margin = thresholds.downgrade_margin

    # 1. High threshold
    if score >= thresholds.high_lower:  # >= 70.0
        return RiskLevel.HIGH.value

    # 2. Medium boundary [40.0, 69.9]
    if score >= 40.0:
        if previous_level == RiskLevel.HIGH.value:
            # Downgrading from High requires score < 67.0
            if score >= (thresholds.high_lower - margin):  # >= 67.0
                return RiskLevel.HIGH.value
            return RiskLevel.MEDIUM.value
        return RiskLevel.MEDIUM.value

    # 3. Low boundary [< 40.0]
    if previous_level in (RiskLevel.HIGH.value, RiskLevel.MEDIUM.value):
        # Downgrading to Low requires score < 37.0
        if score >= (40.0 - margin):  # >= 37.0
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value

    return RiskLevel.LOW.value
