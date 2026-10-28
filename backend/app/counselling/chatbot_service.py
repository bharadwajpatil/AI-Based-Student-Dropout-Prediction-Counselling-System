import json
import logging
from datetime import UTC, datetime
from typing import Any
from bson import ObjectId

from backend.app.core.config import settings
from backend.app.counselling.client import GeminiClient, GeminiError
from backend.app.db.mongo import get_database
from backend.app.models.marks import calculate_grade
from backend.app.schemas.hierarchy import AIChatResponse, StudyPlanResponse

logger = logging.getLogger("student-dropout-system.counselling.chatbot")


class AcademicChatbotService:
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self.gemini_client = gemini_client or GeminiClient(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )

    async def get_student_academic_summary(self, student_id: str) -> dict[str, Any]:
        """Gathers actual verified student data from MongoDB."""
        db = get_database()
        st_oid = ObjectId(student_id)

        student = await db.students.find_one({"_id": st_oid})
        if not student:
            return {}

        # Latest performance
        perf = await db.performance.find({"student_id": st_oid}).sort("semester", -1).to_list(5)
        latest_perf = perf[0] if perf else {}

        # Latest risk
        risk = await db.risk_results.find_one({"student_id": st_oid, "is_current": True})

        # Subject marks & backlogs
        marks = await db.subject_marks.find({"student_id": st_oid}).to_list(100)
        backlog_subjects = [
            f"{m['subject_name']} ({m.get('total_marks', 0):.0f}/100)"
            for m in marks if m.get("is_backlog", False)
        ]
        weak_subjects = [
            f"{m['subject_name']} ({m.get('total_marks', 0):.0f}/100, Att: {m.get('attendance', 0):.0f}%)"
            for m in marks if m.get("total_marks", 100) < 55.0 or m.get("attendance", 100) < 75.0
        ]

        return {
            "name": student.get("name"),
            "erp_id": student.get("erp_id"),
            "department": student.get("department"),
            "semester": student.get("semester"),
            "attendance": latest_perf.get("attendance", 85.0),
            "cgpa_marks": latest_perf.get("marks", 75.0),
            "backlogs_count": latest_perf.get("backlogs", len(backlog_subjects)),
            "backlog_subjects": backlog_subjects,
            "weak_subjects": weak_subjects,
            "risk_level": risk.get("level", "Low") if risk else "Low",
            "risk_score": risk.get("score", 20.0) if risk else 20.0,
            "risk_factors": [f.get("name") for f in risk.get("factors", []) if f.get("contribution", 0) > 0] if risk else [],
        }

    async def chat(
        self,
        student_id: str,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AIChatResponse:
        """Processes a chat query using the student's real academic record."""
        summary = await self.get_student_academic_summary(student_id)

        history_text = ""
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = "Student" if turn.get("role") == "user" else "AI Counsellor"
                history_text += f"{role}: {turn.get('content', '')}\n"

        prompt = f"""You are an empathetic, highly practical college Academic Counsellor and Mentor in an early warning system.
You are advising a student named {summary.get('name', 'Student')} based on their ACTUAL, VERIFIED institutional records:

STUDENT PROFILE:
- Name: {summary.get('name')} (ID: {summary.get('erp_id')})
- Department: {summary.get('department')}, Semester {summary.get('semester')}
- Current Risk Level: {summary.get('risk_level')} (Risk Score: {summary.get('risk_score')}/100)
- Attendance Rate: {summary.get('attendance')}%
- Average Marks: {summary.get('cgpa_marks')}%
- Active Backlogs ({summary.get('backlogs_count')}): {', '.join(summary.get('backlog_subjects', [])) or 'None'}
- Subjects Requiring Attention: {', '.join(summary.get('weak_subjects', [])) or 'None'}
- Risk Drivers: {', '.join(summary.get('risk_factors', [])) or 'None'}

CONVERSATION CONTEXT:
{history_text}
Student's latest message: "{message}"

COUNSELLING GUIDELINES:
1. Always reference the student's specific academic data (e.g. mention their actual backlog subjects, attendance %, and scores).
2. Prioritize backlogs and weak subjects: explain which subject to tackle first (usually the one with lowest marks) and recommend daily hours.
3. If attendance is low (< 75%), give concrete tips on attendance recovery and meeting professors.
4. Keep the tone encouraging, empathetic, and actionable. Avoid medical diagnoses.
5. Provide 2-3 specific action items at the end.

Give your supportive, direct response:"""

        reply_text = ""
        try:
            raw_reply = await self.gemini_client.generate_text(prompt)
            reply_text = raw_reply.strip()
        except Exception as e:
            logger.warning("Gemini chat fallback invoked: %s", e)
            # Intelligent fallback tailored to actual data
            backlogs = summary.get("backlog_subjects", [])
            att = summary.get("attendance", 85)
            if backlogs:
                reply_text = (
                    f"Hello {summary.get('name', 'there')}. Looking closely at your academic record, your primary focus should be clearing your {len(backlogs)} active backlog(s): "
                    f"{', '.join(backlogs)}. "
                    f"Start with {backlogs[0]} by dedicating at least 1.5 to 2 hours of daily problem solving, focusing on high-weightage topics and previous question papers. "
                    f"Also ensure your attendance stays above 75% (currently {att}%) so you don't face exam eligibility issues. "
                    f"Would you like me to generate a personalized 7-day study plan for these subjects?"
                )
            else:
                reply_text = (
                    f"Hello {summary.get('name', 'there')}. Your record shows an attendance of {att}% and average marks of {summary.get('cgpa_marks', 75)}% with no active backlogs. "
                    f"To keep your risk level Low, continue maintaining consistent class engagement, submit all lab assignments ahead of deadlines, and review challenging course material weekly."
                )

        actions = [
            f"Dedicate 2 hours daily to {summary.get('backlog_subjects', ['core revision'])[0]}",
            "Attend all upcoming lectures to maintain eligibility",
            "Consult with your faculty mentor during office hours",
        ]

        return AIChatResponse(
            reply=reply_text,
            suggested_actions=actions,
            sources_consulted=["Student Transcript", "Attendance Records", "Dropout Risk Model"],
        )

    async def generate_or_get_study_plan(self, student_id: str) -> StudyPlanResponse:
        """Generates or loads a persistent personalized 7-Day Study Plan & Backlog Roadmap."""
        db = get_database()
        st_oid = ObjectId(student_id)
        summary = await self.get_student_academic_summary(student_id)

        # Check existing study plan in DB
        existing = await db.study_plans.find_one({"student_id": st_oid})
        now = datetime.now(UTC)

        backlogs = summary.get("backlog_subjects", [])
        weak = summary.get("weak_subjects", [])

        # Priority subjects
        b_names = [b.split(" (")[0] for b in backlogs] if backlogs else ["Data Structures", "Mathematics"]
        w_names = [w.split(" (")[0] for w in weak] if weak else ["Core Engineering", "Applied Computing"]

        subj_1 = b_names[0] if b_names else (w_names[0] if w_names else "Core Subject 1")
        subj_2 = b_names[1] if len(b_names) > 1 else (w_names[0] if w_names else "Core Subject 2")
        subj_3 = w_names[1] if len(w_names) > 1 else "Elective / Lab"

        # Construct customized 7-day schedule
        weekly_schedule = {
            "Monday": [
                f"2.0 hrs: {subj_1} (Theory concepts & textbook examples)",
                f"1.0 hr: {subj_2} (Assignment review)",
            ],
            "Tuesday": [
                f"2.0 hrs: {subj_2} (Algorithms & numerical problems)",
                f"1.0 hr: {subj_1} (Flashcard revision)",
            ],
            "Wednesday": [
                f"2.0 hrs: {subj_1} (Previous university question papers)",
                f"1.0 hr: {subj_3} (Lab write-ups & concepts)",
            ],
            "Thursday": [
                f"2.0 hrs: {subj_2} (Model evaluation & practicals)",
                f"1.0 hr: {subj_1} (Doubt clearing notes)",
            ],
            "Friday": [
                f"1.5 hrs: {subj_1} + 1.5 hrs: {subj_2} (Comprehensive weekly topic synthesis)",
            ],
            "Saturday": [
                "2.5 hrs: Timed Mock Test under exam conditions",
                "1.0 hr: Error analysis & weakness logging",
            ],
            "Sunday": [
                "1.5 hrs: Weekly backlog progress review with peer or mentor",
                "Rest & wellness recharge",
            ],
        }

        # Backlog improvement plans
        backlog_plans = []
        for b in b_names:
            backlog_plans.append({
                "subject": b,
                "status": "BACKLOG",
                "problem": "Foundational gaps in core algorithms and insufficient practice on past exam formats.",
                "daily_study_time": "1.5 - 2.0 hours daily",
                "target_marks": "65+ / 100",
                "weekly_roadmap": [
                    "Week 1: Fundamentals, formulas, and textbook solved problems",
                    "Week 2: Mid-level difficulty problems & unit questions",
                    "Week 3: High-weightage topics & faculty assigned homework",
                    "Week 4: 3 Full previous-year papers under timed conditions",
                ],
            })

        plan_doc = {
            "student_id": st_oid,
            "weekly_schedule": weekly_schedule,
            "backlog_plans": backlog_plans,
            "weak_areas": b_names + w_names,
            "overall_advice": (
                f"Consistency over cramming: Committing 3 hours each evening will comfortably clear your "
                f"backlog in {subj_1} while maintaining attendance above 80%."
            ),
            "target_attendance": 85.0,
            "generated_at": now,
            "updated_at": now,
        }

        if existing:
            await db.study_plans.update_one({"_id": existing["_id"]}, {"$set": plan_doc})
            saved = await db.study_plans.find_one({"_id": existing["_id"]})
        else:
            res = await db.study_plans.insert_one(plan_doc)
            plan_doc["_id"] = res.inserted_id
            saved = plan_doc

        return StudyPlanResponse(
            id=str(saved["_id"]),
            student_id=str(st_oid),
            student_name=summary.get("name", "Student"),
            weekly_schedule=saved["weekly_schedule"],
            backlog_plans=saved["backlog_plans"],
            weak_areas=saved["weak_areas"],
            overall_advice=saved["overall_advice"],
            target_attendance=float(saved["target_attendance"]),
            generated_at=saved["generated_at"],
        )


chatbot_service = AcademicChatbotService()
