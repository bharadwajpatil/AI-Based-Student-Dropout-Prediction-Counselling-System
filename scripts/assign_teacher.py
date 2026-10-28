#!/usr/bin/env python3
"""
CLI Utility to inspect teacher workloads and assign students to teachers/mentors.

Usage:
  # 1. Inspect all teachers and current assigned student counts:
  python scripts/assign_teacher.py --list

  # 2. Assign 20 Computer Science students to teacher Bharadwaj:
  python scripts/assign_teacher.py --teacher patilbharadwaj@gmail.com --dept "Computer Science" --count 20

  # 3. Assign all Computer Science students to teacher Bharadwaj:
  python scripts/assign_teacher.py --teacher patilbharadwaj@gmail.com --dept "Computer Science" --all

  # 4. Assign a specific student by ERP ID to Bharadwaj:
  python scripts/assign_teacher.py --teacher patilbharadwaj@gmail.com --erp CS2024-001
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from backend.app.core.config import settings


async def get_db():
    import os
    # If MONGODB_URI is explicitly set in env or running inside docker
    uri = os.environ.get("MONGODB_URI") or settings.MONGODB_URI
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=1500)
        await client.admin.command("ping")
        return client[settings.MONGODB_DATABASE]
    except Exception:
        # Fallback to local docker mongodb port on host
        local_uri = "mongodb://localhost:27017/student_dropout_db?replicaSet=rs0&directConnection=true"
        client = AsyncIOMotorClient(local_uri, serverSelectionTimeoutMS=2000)
        await client.admin.command("ping")
        return client["student_dropout_db"]



async def list_teachers(db):
    print("\n" + "=" * 70)
    print("👨‍🏫 FACULTY MEMBERS & CURRENT STUDENT ASSIGNMENTS")
    print("=" * 70)
    teachers = await db.users.find({"role": "teacher"}).to_list(100)
    if not teachers:
        print("No users found with role 'teacher'.")
        return

    for t in teachers:
        t_id = t["_id"]
        t_name = t.get("name", "Unknown")
        t_email = t.get("email", "No email")
        t_dept = t.get("department", "No department")
        assigned_count = await db.students.count_documents({"assigned_teacher_ids": t_id})
        print(f" • ID: {t_id}")
        print(f"   Name:       {t_name}")
        print(f"   Email:      {t_email}")
        print(f"   Department: {t_dept}")
        print(f"   Assigned:   {assigned_count} students")
        print("-" * 70)


async def assign_students(
    teacher_query: str,
    dept: str | None = None,
    count: int | None = None,
    assign_all: bool = False,
    student_erp: str | None = None,
    replace: bool = False,
):
    db = await get_db()

    # Find teacher by ID, email, or name
    teacher = None
    if ObjectId.is_valid(teacher_query):
        teacher = await db.users.find_one({"_id": ObjectId(teacher_query), "role": "teacher"})
    if not teacher:
        teacher = await db.users.find_one({
            "email": teacher_query.strip().lower(),
            "role": "teacher",
        })
    if not teacher:
        teacher = await db.users.find_one({
            "name": {"$regex": f"^{teacher_query.strip()}$", "$options": "i"},
            "role": "teacher",
        })

    if not teacher:
        print(f"\n❌ Error: No teacher found matching '{teacher_query}'.")
        print("Run with --list to see all available teachers.")
        return

    teacher_id = teacher["_id"]
    teacher_name = teacher.get("name", "Unknown")
    teacher_email = teacher.get("email", "")
    print(f"\n🎯 Target Teacher: {teacher_name} ({teacher_email}) [ID: {teacher_id}]")

    # If specific student ERP ID requested
    if student_erp:
        normalized_erp = student_erp.strip().upper()
        student = await db.students.find_one({"erp_id": normalized_erp})
        if not student:
            print(f"❌ Student with ERP ID '{normalized_erp}' not found.")
            return

        op = {"$set": {"assigned_teacher_ids": [teacher_id]}} if replace else {"$addToSet": {"assigned_teacher_ids": teacher_id}}
        await db.students.update_one({"_id": student["_id"]}, op)
        print(f"✅ Successfully assigned student {student['name']} ({normalized_erp}) to {teacher_name}!")
        return

    # Find candidate students
    query = {}
    if dept:
        query["department"] = dept

    cursor = db.students.find(query).sort("_id", 1)
    if not assign_all and count:
        cursor = cursor.limit(count)

    students = await cursor.to_list(1000)
    if not students:
        print(f"❌ No students found matching criteria (department={dept}).")
        return

    updated = 0
    for s in students:
        op = {"$set": {"assigned_teacher_ids": [teacher_id]}} if replace else {"$addToSet": {"assigned_teacher_ids": teacher_id}}
        res = await db.students.update_one({"_id": s["_id"]}, op)
        if res.modified_count > 0:
            updated += 1

    total_now = await db.students.count_documents({"assigned_teacher_ids": teacher_id})
    print(f"✅ Successfully assigned {updated} new student(s) to {teacher_name}!")
    print(f"📊 Total students now under {teacher_name}: {total_now}")


async def main():
    parser = argparse.ArgumentParser(description="Assign students to teachers")
    parser.add_argument("--list", action="store_true", help="List all teachers and current workload")
    parser.add_argument("--teacher", type=str, default="patilbharadwaj@gmail.com", help="Teacher email, name, or ObjectId")
    parser.add_argument("--dept", type=str, help="Filter students by department (e.g. 'Computer Science')")
    parser.add_argument("--count", type=int, help="Number of students to assign")
    parser.add_argument("--all", action="store_true", help="Assign all matching students")
    parser.add_argument("--erp", type=str, help="Specific student ERP ID (e.g. CS2024-001)")
    parser.add_argument("--replace", action="store_true", help="Replace existing assigned teachers instead of appending")

    args = parser.parse_args()
    db = await get_db()

    if args.list:
        await list_teachers(db)
        return

    if not args.count and not args.all and not args.erp:
        # Default behavior if just run with --teacher: show list and instruct
        await list_teachers(db)
        print("\n💡 To assign students to a teacher, specify --count, --all, or --erp.")
        print("Example: python scripts/assign_teacher.py --teacher patilbharadwaj@gmail.com --dept 'Computer Science' --count 20")
        return

    await assign_students(
        teacher_query=args.teacher,
        dept=args.dept,
        count=args.count,
        assign_all=args.all,
        student_erp=args.erp,
        replace=args.replace,
    )


if __name__ == "__main__":
    asyncio.run(main())
