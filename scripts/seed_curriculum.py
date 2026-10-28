import os
from datetime import UTC, datetime
import pymongo
from bson import ObjectId

def seed_curriculum():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/student_dropout_db?directConnection=true")
    client = pymongo.MongoClient(uri)
    db = client.get_database("student_dropout_db")

    # Check if subjects exist
    if db.subjects.count_documents({}) == 0:
        print("Seeding subjects...")

    # Find HOD and Teachers
    hod_cs = db.users.find_one({"role": "hod", "department": "Computer Science"})
    hod_id = hod_cs["_id"] if hod_cs else None

    teacher_bharadwaj = db.users.find_one({"email": "patilbharadwaj@gmail.com"})
    teacher_sharma = db.users.find_one({"email": "prof.sharma@university.edu"})
    teacher_kapoor = db.users.find_one({"email": "prof.kapoor@university.edu"})

    b_id = teacher_bharadwaj["_id"] if teacher_bharadwaj else None
    b_name = teacher_bharadwaj["name"] if teacher_bharadwaj else None

    s_id = teacher_sharma["_id"] if teacher_sharma else None
    s_name = teacher_sharma["name"] if teacher_sharma else None

    k_id = teacher_kapoor["_id"] if teacher_kapoor else None
    k_name = teacher_kapoor["name"] if teacher_kapoor else None

    now = datetime.now(UTC)

    subjects = [
        {
            "name": "Machine Learning",
            "code": "CS601",
            "department": "Computer Science",
            "year": "3rd Year",
            "semester": 6,
            "credits": 4,
            "academic_year": "2024-25",
            "assigned_teacher_id": b_id,
            "assigned_teacher_name": b_name,
            "hod_id": hod_id,
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Python & Data Science",
            "code": "CS602",
            "department": "Computer Science",
            "year": "3rd Year",
            "semester": 6,
            "credits": 4,
            "academic_year": "2024-25",
            "assigned_teacher_id": b_id,
            "assigned_teacher_name": b_name,
            "hod_id": hod_id,
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Database Management Systems",
            "code": "CS603",
            "department": "Computer Science",
            "year": "3rd Year",
            "semester": 6,
            "credits": 3,
            "academic_year": "2024-25",
            "assigned_teacher_id": s_id,
            "assigned_teacher_name": s_name,
            "hod_id": hod_id,
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Applied Mathematics",
            "code": "CS604",
            "department": "Computer Science",
            "year": "3rd Year",
            "semester": 6,
            "credits": 4,
            "academic_year": "2024-25",
            "assigned_teacher_id": k_id,
            "assigned_teacher_name": k_name,
            "hod_id": hod_id,
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Computer Networks",
            "code": "CS605",
            "department": "Computer Science",
            "year": "3rd Year",
            "semester": 6,
            "credits": 3,
            "academic_year": "2024-25",
            "assigned_teacher_id": s_id,
            "assigned_teacher_name": s_name,
            "hod_id": hod_id,
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Software Engineering & Agile",
            "code": "CS606",
            "department": "Computer Science",
            "year": "3rd Year",
            "semester": 6,
            "credits": 3,
            "academic_year": "2024-25",
            "assigned_teacher_id": k_id,
            "assigned_teacher_name": k_name,
            "hod_id": hod_id,
            "created_at": now,
            "updated_at": now,
        },
    ]

    res = db.subjects.insert_many(subjects)
    print(f"Seeded {len(res.inserted_ids)} initial subjects successfully.")

    # Seed subject marks for demo student Rohan Verma (CS2024-001)
    rohan = db.students.find_one({"erp_id": "CS2024-001"})
    if rohan:
        ml_sub = db.subjects.find_one({"code": "CS601"})
        py_sub = db.subjects.find_one({"code": "CS602"})
        dbms_sub = db.subjects.find_one({"code": "CS603"})
        math_sub = db.subjects.find_one({"code": "CS604"})

        sample_marks = [
            {
                "student_id": rohan["_id"],
                "subject_id": ml_sub["_id"],
                "subject_name": ml_sub["name"],
                "subject_code": ml_sub["code"],
                "semester": 6,
                "academic_year": "2024-25",
                "internal_marks": 18,
                "external_marks": 42,
                "practical_marks": 15,
                "assignment_marks": 15,
                "total_marks": 60,
                "grade": "B",
                "attendance": 72.0,
                "is_backlog": False,
                "entered_by": b_id,
                "created_at": now,
                "updated_at": now,
            },
            {
                "student_id": rohan["_id"],
                "subject_id": py_sub["_id"],
                "subject_name": py_sub["name"],
                "subject_code": py_sub["code"],
                "semester": 6,
                "academic_year": "2024-25",
                "internal_marks": 25,
                "external_marks": 58,
                "practical_marks": 18,
                "assignment_marks": 18,
                "total_marks": 83,
                "grade": "A",
                "attendance": 88.0,
                "is_backlog": False,
                "entered_by": b_id,
                "created_at": now,
                "updated_at": now,
            },
            {
                "student_id": rohan["_id"],
                "subject_id": math_sub["_id"],
                "subject_name": math_sub["name"],
                "subject_code": math_sub["code"],
                "semester": 6,
                "academic_year": "2024-25",
                "internal_marks": 10,
                "external_marks": 24,
                "practical_marks": 0,
                "assignment_marks": 4,
                "total_marks": 34,
                "grade": "F",
                "attendance": 65.0,
                "is_backlog": True,
                "entered_by": k_id,
                "created_at": now,
                "updated_at": now,
            },
            {
                "student_id": rohan["_id"],
                "subject_id": dbms_sub["_id"],
                "subject_name": dbms_sub["name"],
                "subject_code": dbms_sub["code"],
                "semester": 6,
                "academic_year": "2024-25",
                "internal_marks": 19,
                "external_marks": 49,
                "practical_marks": 14,
                "assignment_marks": 14,
                "total_marks": 68,
                "grade": "C",
                "attendance": 82.0,
                "is_backlog": False,
                "entered_by": s_id,
                "created_at": now,
                "updated_at": now,
            },
        ]
        db.subject_marks.delete_many({"student_id": rohan["_id"]})
        db.subject_marks.insert_many(sample_marks)
        print("Seeded marks for student Rohan Verma (including 1 backlog in Applied Mathematics).")

if __name__ == "__main__":
    seed_curriculum()
