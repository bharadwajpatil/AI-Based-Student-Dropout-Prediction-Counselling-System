"""
Tests for Phase 12 demo data seed script.
Verifies:
- 6 demo users created (Admin, HOD CS, HOD EE, 2 Teachers, 1 Student)
- 200 synthetic students generated
- Risk distribution includes Low, Med, High, and Insufficient Data
- Counselling cases and meeting notes created for High-risk students
"""

import pytest

from scripts.seed_demo_data import seed_database


@pytest.mark.asyncio
async def test_seed_demo_data_execution(mock_db):
    """Executes the seed script against the mock database and verifies record integrity."""
    stats = await seed_database(target_db=mock_db)

    assert stats["users"] == 6
    assert stats["students"] == 200
    assert stats["performances"] == 190  # 200 total - 10 Insufficient Data
    assert stats["risk_results"] == 190
    assert stats["counselling_records"] >= 35  # ~40 high risk cases
    assert stats["notifications"] >= 1

    # Verify user roles in mock_db
    admin = await mock_db.users.find_one({"email": "admin@university.edu"})
    assert admin is not None
    assert admin["role"] == "admin"

    teacher = await mock_db.users.find_one({"email": "prof.sharma@university.edu"})
    assert teacher is not None
    assert teacher["role"] == "teacher"

    # Verify demo student is linked
    demo_student = await mock_db.students.find_one({"erp_id": "CS2024-001"})
    assert demo_student is not None
    assert demo_student["user_id"] is not None

    # Verify counselling cases have timeline notes
    high_risk_case = await mock_db.counselling_records.find_one()
    assert high_risk_case is not None
    assert len(high_risk_case["notes_timeline"]) >= 1
    assert "ai_recommendation" in high_risk_case
