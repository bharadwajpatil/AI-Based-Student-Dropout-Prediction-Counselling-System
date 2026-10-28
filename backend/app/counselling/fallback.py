from typing import Any

from backend.app.counselling.guardrails import detect_crisis
from backend.app.counselling.schemas import AICounsellingRecommendation
from backend.app.models.risk import RiskLevel


def generate_template_recommendation(
    risk_level: str,
    score: float,
    factors: list[dict[str, Any]],
    teacher_notes: str | None = None,
) -> AICounsellingRecommendation:
    """
    Generates deterministic, high-quality rule-based recommendations based on
    contributing risk factors when the AI service is unavailable, times out, or errors.
    """
    has_crisis = detect_crisis(teacher_notes)

    actions: list[str] = []
    factor_names = [f.get("name", "").lower() for f in factors if f.get("risk", 0.0) >= 30.0]

    # Attendance actions
    if any(f.get("name") == "attendance" and f.get("risk", 0.0) >= 30.0 for f in factors):
        actions.append("Schedule a dedicated 1-on-1 check-in to discuss attendance obstacles, daily commute, or scheduling conflicts.")
        actions.append("Pair the student with an active class peer mentor to share lecture notes and review missed coursework.")
        actions.append("Establish a clear weekly attendance recovery plan with a target threshold above 75%.")

    # Marks actions
    if any(f.get("name") == "marks" and f.get("risk", 0.0) >= 30.0 for f in factors):
        actions.append("Recommend enrollment in departmental remedial tutoring sessions for core academic subjects.")
        actions.append("Review recent examination papers with the student to pinpoint specific conceptual difficulties.")

    # Backlog actions
    if any(f.get("name") == "backlogs" and f.get("risk", 0.0) > 0.0 for f in factors):
        actions.append("Develop a structured backlog clearance roadmap balancing current semester courses with re-examination preparation.")
        actions.append("Coordinate with the academic advisor to verify prerequisite coverage and exam registration schedules.")

    # Trend actions
    if any(f.get("name") == "trend" and f.get("risk", 0.0) >= 40.0 for f in factors):
        actions.append("Discuss sudden performance decline compared to previous semester to identify recent academic or personal disruptions.")

    # Assignment actions
    if any(f.get("name") == "assignments" and f.get("risk", 0.0) >= 30.0 for f in factors):
        actions.append("Break upcoming course deliverables and lab submissions into weekly intermediate milestones.")

    # Engagement actions
    if any(f.get("name") == "engagement" and f.get("risk", 0.0) >= 30.0 for f in factors):
        actions.append("Encourage regular login and participation in the departmental learning management system (LMS).")

    # Fallback default actions if none triggered
    if not actions:
        if risk_level == RiskLevel.LOW.value:
            actions = [
                "Acknowledge consistent coursework and attendance progress during routine advising.",
                "Offer optional enrichment opportunities, peer tutoring roles, or extracurricular projects.",
            ]
        elif risk_level == RiskLevel.MEDIUM.value:
            actions = [
                "Conduct a mid-semester check-in to discuss coursework comfort and study routines.",
                "Review upcoming assignment submission schedule and exam preparation plan.",
            ]
        else:
            actions = [
                "Conduct an urgent academic advising consultation to review overall performance.",
                "Formulate an academic recovery plan with regular bi-weekly milestones.",
            ]

    # Determine follow up days and escalation
    if risk_level == RiskLevel.HIGH.value:
        follow_up_days = 7
        escalate_to_hod = score >= 75.0 or any(f.get("name") == "backlogs" and f.get("risk", 0.0) >= 75.0 for f in factors)
        driver_str = ", ".join(factor_names[:2]) if factor_names else "overall academic performance"
        summary = f"Student is at High academic dropout risk (Score {score:.1f}/100) driven by {driver_str}. Prompt faculty advising intervention is needed."
    elif risk_level == RiskLevel.MEDIUM.value:
        follow_up_days = 14
        escalate_to_hod = False
        driver_str = ", ".join(factor_names[:2]) if factor_names else "borderline performance metrics"
        summary = f"Student exhibits Medium academic risk (Score {score:.1f}/100) influenced by {driver_str}. Targeted academic support is recommended."
    elif risk_level == RiskLevel.LOW.value:
        follow_up_days = 30
        escalate_to_hod = False
        summary = f"Student maintains solid academic standing with Low risk (Score {score:.1f}/100). Continue standard periodic faculty check-ins."
    else:  # Insufficient Data
        follow_up_days = 14
        escalate_to_hod = False
        summary = "Insufficient academic performance records to evaluate comprehensive dropout risk. Review latest data submissions."
        actions = ["Verify that latest attendance and mid-semester assessment marks are uploaded to the academic portal."]

    # Crisis handling
    refer_to_counsellor = False
    if has_crisis:
        escalate_to_hod = True
        refer_to_counsellor = True
        actions.insert(0, "URGENT: Immediately notify campus student wellness / counseling center and contact HOD regarding student wellbeing.")
        summary = f"URGENT ATTENTION REQUIRED: {summary}"

    return AICounsellingRecommendation(
        summary=summary,
        actions=actions[:5],  # Cap at top 5 actions
        follow_up_in_days=follow_up_days,
        escalate_to_hod=escalate_to_hod,
        refer_to_counsellor=refer_to_counsellor,
    )
