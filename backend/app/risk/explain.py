from typing import Any


def format_factor_explanation(
    name: str,
    raw_value: Any,
    risk: float,
    classes_held: int | None = None,
) -> str:
    """Provides human-readable explainability for an individual factor."""
    if name == "attendance":
        if classes_held is not None and classes_held < 20:
            return f"Attendance sample too small ({classes_held} classes held; minimum is 20)."
        if raw_value is not None:
            if raw_value < 50.0:
                return f"Attendance is critically low at {raw_value:.1f}% (below 50% threshold)."
            return f"Attendance is {raw_value:.1f}%."
        return "Attendance data not recorded."

    elif name == "marks":
        if raw_value is not None:
            if raw_value <= 35.0:
                return f"Academic marks are critical at {raw_value:.1f}%."
            return f"Average marks are {raw_value:.1f}%."
        return "Marks data not recorded."

    elif name == "backlogs":
        if raw_value is not None:
            if raw_value >= 4:
                return f"Severe backlog count: {int(raw_value)} active backlogs."
            elif raw_value >= 2:
                return f"Moderate backlog count: {int(raw_value)} active backlogs."
            elif raw_value > 0:
                return f"{int(raw_value)} active backlog."
            return "No active backlogs."
        return "Backlog data not recorded."

    elif name == "trend":
        if raw_value is not None:
            drop = raw_value.get("drop", 0.0)
            if drop >= 16.0:
                return f"Sharp performance drop of {drop:.1f} marks from previous semester."
            elif drop > 0.0:
                return f"Marks dropped by {drop:.1f} compared to previous semester."
            return "Academic performance is stable or improving."
        return "Previous semester marks not available to evaluate trend."

    elif name == "assignments":
        if raw_value is not None:
            return f"Assignment submission rate is {raw_value:.1f}%."
        return "Assignment completion data not recorded."

    elif name == "engagement":
        if raw_value is not None:
            return f"Class and LMS engagement score is {raw_value:.1f}%."
        return "Engagement activity not recorded."

    return f"{name.capitalize()} risk is {risk:.1f}%."


def generate_risk_explanation(
    score: float | None,
    level: str,
    confidence: float,
    factors: list[dict[str, Any]],
    overrides_applied: list[str],
    watchlist: bool,
) -> dict[str, Any]:
    """Generates complete explainability package for display on UI / dashboards."""
    reasons: list[str] = []

    if level == "Insufficient Data":
        reasons.append(
            f"Confidence is {confidence * 100:.0f}% (below the 50% required threshold). Additional data needed."
        )
    else:
        if overrides_applied:
            for override in overrides_applied:
                if override == "attendance_below_50":
                    reasons.append("Critical override: Attendance dropped below 50%, setting risk floor to High (70.0).")
                elif override == "backlogs_ge_4":
                    reasons.append("Critical override: Student has 4 or more backlogs, setting risk floor to High (70.0).")
                elif override == "backlogs_ge_2":
                    reasons.append("Override: Student has 2 or more backlogs, setting risk floor to Medium (40.0).")
                elif override == "trend_drop_critical":
                    reasons.append("Critical decline: Marks dropped by 16 or more points, triggering Watchlist flag.")

        top_factors = [f for f in factors if f["contribution"] > 0]
        if top_factors:
            top_name = top_factors[0]["name"]
            reasons.append(f"Top contributing risk factor: {top_name} (contributes {top_factors[0]['contribution']:.1f} points).")

    if watchlist:
        reasons.append("Student is marked on Watchlist due to rapid academic decline.")

    return {
        "level": level,
        "score": score,
        "confidence": confidence,
        "summary": " ".join(reasons) if reasons else "Student risk level is within expected baseline.",
        "top_factors": factors[:3],
        "overrides_applied": overrides_applied,
        "watchlist": watchlist,
    }
