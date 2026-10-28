#!/usr/bin/env python3
"""
Phase 12: Comprehensive Demo & Synthetic Dataset Seeding Script
Populates the database with:
- Demo Users: Admin, HODs, Faculty, and Students
- 200 Synthetic Students across multiple departments and semesters
- Performance records spanning multiple semesters
- Deterministic risk evaluations matching Phase 5 engine logic
- Automated counselling cases, AI recommendations, and meeting notes
- In-app notification alerts
"""

import asyncio
from datetime import UTC, datetime, timedelta
import random
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from typing import Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.models.student import StudentStatus
from backend.app.models.user import UserRole, UserStatus
from backend.app.risk.risk_engine import compute_student_risk
from backend.app.services.email_validation import compute_canonical_email

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Shaurya", "Atharva", "Advik", "Pranav", "Advaith", "Aaryan", "Dhruv", "Kabir", "Ritvik", "Darsh",
    "Diya", "Saanvi", "Aanya", "Aadhya", "Ananya", "Pari", "Anika", "Navya", "Angel", "Myra",
    "Sara", "Ira", "Kavya", "Avani", "Riya", "Isha", "Tara", "Tanvi", "Siya", "Meera",
    "Rohan", "Vikram", "Sneha", "Rahul", "Pooja", "Amit", "Neha", "Deepak", "Sunita", "Gaurav",
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Patel", "Kumar", "Singh", "Mishra", "Joshi", "Chauhan", "Rao",
    "Nair", "Reddy", "Iyer", "Deshmukh", "Kulkarni", "Mehta", "Bhat", "Chatterjee", "Banerjee", "Das",
    "Sen", "Saxena", "Bose", "Ghosh", "Malhotra", "Kapoor", "Chopra", "Khanna", "Bhardwaj", "Aggarwal",
]

DEPARTMENTS = ["Computer Science", "Electrical Engineering", "Mechanical Engineering"]


async def seed_database(target_db: Any = None) -> dict[str, int]:
    if target_db is not None:
        db = target_db
    else:
        print(f"[INFO] Connecting to MongoDB: {settings.MONGODB_URI} -> {settings.MONGODB_DATABASE}")
        client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
        db = client[settings.MONGODB_DATABASE]

        # Test connection
        try:
            await client.admin.command("ping")
            print("[SUCCESS] MongoDB connection established.")
        except Exception as e:
            print(f"[ERROR] Failed to connect to MongoDB: {e}")
            return {}

    # Clean existing collections
    print("[INFO] Cleaning existing collections...")
    for coll_name in [
        "users",
        "students",
        "performance",
        "risk_results",
        "counselling_records",
        "notifications",
        "audit_logs",
    ]:
        await db[coll_name].delete_many({})

    now = datetime.now(UTC)

    # 1. Seed Demo Staff Users
    print("[INFO] Creating demo accounts...")
    admin_id = ObjectId()
    hod_cs_id = ObjectId()
    hod_ee_id = ObjectId()
    teacher1_id = ObjectId()
    teacher2_id = ObjectId()
    student_user_id = ObjectId()

    users_to_create = [
        {
            "_id": admin_id,
            "email": "admin@university.edu",
            "canonical_email": compute_canonical_email("admin@university.edu"),
            "password_hash": hash_password("AdminPass@123"),
            "name": "Dr. Ramesh Chandra (Super Admin)",
            "role": UserRole.ADMIN.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": hod_cs_id,
            "email": "hod.cs@university.edu",
            "canonical_email": compute_canonical_email("hod.cs@university.edu"),
            "password_hash": hash_password("HodPass@123"),
            "name": "Dr. Sunita Kulkarni (HOD CS)",
            "department": "Computer Science",
            "role": UserRole.HOD.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": hod_ee_id,
            "email": "hod.ee@university.edu",
            "canonical_email": compute_canonical_email("hod.ee@university.edu"),
            "password_hash": hash_password("HodPass@123"),
            "name": "Dr. Arvind Deshmukh (HOD EE)",
            "department": "Electrical Engineering",
            "role": UserRole.HOD.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": teacher1_id,
            "email": "prof.sharma@university.edu",
            "canonical_email": compute_canonical_email("prof.sharma@university.edu"),
            "password_hash": hash_password("TeacherPass@123"),
            "name": "Prof. Rajesh Sharma",
            "department": "Computer Science",
            "role": UserRole.TEACHER.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": teacher2_id,
            "email": "prof.kapoor@university.edu",
            "canonical_email": compute_canonical_email("prof.kapoor@university.edu"),
            "password_hash": hash_password("TeacherPass@123"),
            "name": "Prof. Ananya Kapoor",
            "department": "Computer Science",
            "role": UserRole.TEACHER.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": student_user_id,
            "email": "student.demo@university.edu",
            "canonical_email": compute_canonical_email("student.demo@university.edu"),
            "password_hash": hash_password("StudentPass@123"),
            "name": "Rohan Verma",
            "department": "Computer Science",
            "role": UserRole.STUDENT.value,
            "status": UserStatus.ACTIVE.value,
            "email_verified": True,
            "phone_verified": True,
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
    ]
    await db.users.insert_many(users_to_create)
    print(f"[SUCCESS] Created {len(users_to_create)} demo staff and student accounts.")

    # 2. Generate 200 Synthetic Students
    print("[INFO] Synthesizing 200 students with performance histories and risk profiles...")
    students_docs = []
    perf_docs = []
    risk_docs = []
    counselling_docs = []
    notification_docs = []

    # Distribution targets: 100 Low (50%), 50 Med (25%), 40 High (20%), 10 Insufficient Data (5%)
    profiles = (
        ["LOW"] * 100 +
        ["MED"] * 50 +
        ["HIGH"] * 40 +
        ["INSUFFICIENT"] * 10
    )
    random.seed(42)  # Deterministic seed for reproducible demo datasets
    random.shuffle(profiles)

    faculty_cs = [teacher1_id, teacher2_id]

    for idx, risk_tier in enumerate(profiles, start=1):
        s_oid = ObjectId()
        dept = random.choice(DEPARTMENTS)
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        name = f"{fn} {ln}"
        prefix = "CS" if dept == "Computer Science" else ("EE" if dept == "Electrical Engineering" else "ME")
        erp_id = f"{prefix}2024-{idx:03d}"
        inst_email = f"{fn.lower()}.{ln.lower()}{idx}@university.edu"
        semester = random.randint(1, 6)
        batch = f"202{4 - (semester // 2)}-2{8 - (semester // 2)}"

        # Assign demo student account to first CS student
        user_id = student_user_id if idx == 1 else None
        if idx == 1:
            name = "Rohan Verma"
            inst_email = "student.demo@university.edu"
            dept = "Computer Science"
            risk_tier = "LOW"

        assigned_teachers = [random.choice(faculty_cs)] if dept == "Computer Science" else []

        students_docs.append({
            "_id": s_oid,
            "erp_id": erp_id,
            "user_id": user_id,
            "name": name,
            "institutional_email": inst_email,
            "department": dept,
            "semester": semester,
            "batch": batch,
            "assigned_teacher_ids": assigned_teachers,
            "status": StudentStatus.ACTIVE.value,
            "created_at": now - timedelta(days=random.randint(60, 300)),
            "updated_at": now,
        })

        if risk_tier == "INSUFFICIENT":
            # No performance record yet
            continue

        # Generate realistic performance parameters
        if risk_tier == "LOW":
            attendance = round(random.uniform(80.0, 96.0), 1)
            marks = round(random.uniform(70.0, 90.0), 1)
            backlogs = 0
            assignments = round(random.uniform(78.0, 95.0), 1)
            engagement = round(random.uniform(75.0, 92.0), 1)
        elif risk_tier == "MED":
            attendance = round(random.uniform(58.0, 72.0), 1)
            marks = round(random.uniform(48.0, 62.0), 1)
            backlogs = random.choice([1, 2])
            assignments = round(random.uniform(52.0, 68.0), 1)
            engagement = round(random.uniform(50.0, 65.0), 1)
        else:  # HIGH
            # Either attendance floor or backlog override or multi-factor decline
            high_scenario = random.choice(["att_floor", "backlog_floor", "composite"])
            if high_scenario == "att_floor":
                attendance = round(random.uniform(32.0, 48.0), 1)
                marks = round(random.uniform(40.0, 60.0), 1)
                backlogs = random.choice([1, 2])
            elif high_scenario == "backlog_floor":
                attendance = round(random.uniform(55.0, 70.0), 1)
                marks = round(random.uniform(40.0, 55.0), 1)
                backlogs = random.choice([4, 5, 6])
            else:
                attendance = round(random.uniform(42.0, 52.0), 1)
                marks = round(random.uniform(35.0, 46.0), 1)
                backlogs = random.choice([3, 4])
            assignments = round(random.uniform(30.0, 50.0), 1)
            engagement = round(random.uniform(25.0, 45.0), 1)

        p_oid = ObjectId()
        perf_docs.append({
            "_id": p_oid,
            "student_id": s_oid,
            "semester": semester,
            "academic_year": "2024-25",
            "attendance": attendance,
            "classes_held": 100,
            "marks": marks,
            "backlogs": backlogs,
            "assignments": assignments,
            "engagement": engagement,
            "version": 1,
            "updated_by": admin_id,
            "updated_at": now - timedelta(days=random.randint(1, 30)),
        })

        # Evaluate risk using engine
        inputs = {
            "attendance": attendance,
            "classes_held": 100,
            "marks": marks,
            "backlogs": backlogs,
            "assignments": assignments,
            "engagement": engagement,
        }
        risk_calc = compute_student_risk(inputs=inputs)

        r_oid = ObjectId()
        risk_docs.append({
            "_id": r_oid,
            "student_id": s_oid,
            "performance_id": p_oid,
            "score": risk_calc["score"],
            "level": risk_calc["level"],
            "confidence": risk_calc["confidence"],
            "watchlist": risk_calc["watchlist"],
            "factors": risk_calc["factors"],
            "overrides_applied": risk_calc["overrides_applied"],
            "engine_version": "1.0.0",
            "inputs_hash": f"seed_hash_{idx}",
            "computed_at": now - timedelta(days=random.randint(1, 30)),
            "is_current": True,
        })

        # If High Risk, generate automated counselling case & timeline notes
        if risk_calc["level"] == "High":
            case_status = random.choice(["pending", "in_progress", "follow_up"])
            c_oid = ObjectId()

            top_factors = sorted(risk_calc["factors"], key=lambda f: f["risk"], reverse=True)[:3]
            top_names = [f["name"].replace("_", " ").title() for f in top_factors]

            timeline = [
                {
                    "timestamp": now - timedelta(days=random.randint(5, 15)),
                    "author_id": admin_id,
                    "author_name": "System Automator",
                    "content": f"Case automatically initiated due to High Risk evaluation. Primary risk drivers: {', '.join(top_names)}.",
                    "entry_type": "system",
                }
            ]

            if case_status in ("in_progress", "follow_up"):
                timeline.append({
                    "timestamp": now - timedelta(days=random.randint(1, 4)),
                    "author_id": teacher1_id,
                    "author_name": "Prof. Rajesh Sharma",
                    "content": "Conducted initial mentorship session. Student cited commuting challenges and requested tutorial makeup classes.",
                    "entry_type": "note",
                })

            counselling_docs.append({
                "_id": c_oid,
                "student_id": s_oid,
                "status": case_status,
                "risk_assessment_id": r_oid,
                "assigned_counsellor_id": random.choice(assigned_teachers) if assigned_teachers else teacher1_id,
                "ai_recommendation": {
                    "summary": f"High risk identified primarily driven by {top_names[0] if top_names else 'academic indicators'}.",
                    "action_items": [
                        "Schedule mandatory 1-on-1 mentorship session within 5 working days.",
                        "Offer remedial peer-study cohort enrollment.",
                        "Audit morning attendance patterns for early interventions.",
                    ],
                    "refer_to_counsellor": True,
                    "escalate_to_hod": attendance < 40.0,
                    "generated_at": now - timedelta(days=5),
                    "ai_source": "template",
                },
                "notes_timeline": timeline,
                "created_at": now - timedelta(days=15),
                "updated_at": now,
            })

            # Create notification for assigned teacher
            for t_id in assigned_teachers:
                notification_docs.append({
                    "_id": ObjectId(),
                    "user_id": t_id,
                    "type": "risk.changed",
                    "payload": {
                        "student_id": str(s_oid),
                        "erp_id": erp_id,
                        "old_level": "Medium",
                        "new_level": "High",
                        "score": risk_calc["score"],
                    },
                    "read_at": None if random.random() > 0.5 else now,
                    "created_at": now - timedelta(days=random.randint(1, 7)),
                })

    # Bulk insert synthetic records
    print("[INFO] Writing documents to MongoDB...")
    await db.students.insert_many(students_docs)
    if perf_docs:
        await db.performance.insert_many(perf_docs)
    if risk_docs:
        await db.risk_results.insert_many(risk_docs)
    if counselling_docs:
        await db.counselling_records.insert_many(counselling_docs)
    if notification_docs:
        await db.notifications.insert_many(notification_docs)

    print("\n" + "=" * 60)
    print("DEMO DATA SEEDING COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"Total Users:            {len(users_to_create)}")
    print(f"Total Students:         {len(students_docs)}")
    print(f"Total Performances:     {len(perf_docs)}")
    print(f"Total Risk Results:     {len(risk_docs)}")
    print(f"Total Counselling Cases:{len(counselling_docs)}")
    print(f"Total Notifications:    {len(notification_docs)}")
    print("-" * 60)
    print("DEMO CREDENTIALS:")
    print("  Super Admin:  admin@university.edu       / AdminPass@123")
    print("  HOD CS:       hod.cs@university.edu      / HodPass@123")
    print("  HOD EE:       hod.ee@university.edu      / HodPass@123")
    print("  Faculty 1:    prof.sharma@university.edu / TeacherPass@123")
    print("  Faculty 2:    prof.kapoor@university.edu / TeacherPass@123")
    print("  Demo Student: student.demo@university.edu / StudentPass@123")
    print("=" * 60 + "\n")

    return {
        "users": len(users_to_create),
        "students": len(students_docs),
        "performances": len(perf_docs),
        "risk_results": len(risk_docs),
        "counselling_records": len(counselling_docs),
        "notifications": len(notification_docs),
    }


if __name__ == "__main__":
    asyncio.run(seed_database())
