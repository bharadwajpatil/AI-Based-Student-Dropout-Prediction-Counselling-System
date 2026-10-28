import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

logger = logging.getLogger("student-dropout-system.db.indexes")


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """
    Creates all collection indexes idempotently on application startup.
    Ensures unique constraints, compound query indexes, and TTL expiration indexes.
    """
    logger.info("Initializing database indexes across all collections (idempotent)...")

    # 1. users
    await db.users.create_indexes(
        [
            IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
            IndexModel(
                [("phone_e164", ASCENDING)],
                unique=True,
                sparse=True,
                name="idx_users_phone_sparse_unique",
            ),
            IndexModel([("role", ASCENDING)], name="idx_users_role"),
        ]
    )

    # 2. students
    await db.students.create_indexes(
        [
            IndexModel([("erp_id", ASCENDING)], unique=True, name="idx_students_erp_id_unique"),
            IndexModel(
                [("department", ASCENDING), ("semester", ASCENDING)],
                name="idx_students_dept_semester",
            ),
            IndexModel(
                [("assigned_teacher_ids", ASCENDING)], name="idx_students_assigned_teachers"
            ),
            IndexModel([("user_id", ASCENDING)], sparse=True, name="idx_students_user_id_sparse"),
        ]
    )

    # 3. performance
    await db.performance.create_indexes(
        [
            IndexModel(
                [
                    ("student_id", ASCENDING),
                    ("semester", ASCENDING),
                    ("academic_year", ASCENDING),
                ],
                unique=True,
                name="idx_perf_student_sem_year_unique",
            ),
        ]
    )

    # 4. risk_results
    await db.risk_results.create_indexes(
        [
            IndexModel(
                [("student_id", ASCENDING), ("is_current", ASCENDING)],
                name="idx_risk_student_is_current",
            ),
            IndexModel(
                [("student_id", ASCENDING), ("computed_at", DESCENDING)],
                name="idx_risk_student_computed_desc",
            ),
            IndexModel([("level", ASCENDING)], name="idx_risk_level"),
        ]
    )

    # 5. counselling
    await db.counselling.create_indexes(
        [
            IndexModel([("student_id", ASCENDING)], name="idx_counselling_student_id"),
            IndexModel([("teacher_id", ASCENDING)], name="idx_counselling_teacher_id"),
            IndexModel([("status", ASCENDING)], name="idx_counselling_status"),
        ]
    )

    # 6. auth_tokens (TTL on expires_at)
    await db.auth_tokens.create_indexes(
        [
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="idx_auth_tokens_ttl_expires_at",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("purpose", ASCENDING)],
                name="idx_auth_tokens_user_purpose",
            ),
        ]
    )

    # 7. refresh_tokens (TTL on expires_at)
    await db.refresh_tokens.create_indexes(
        [
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="idx_refresh_tokens_ttl_expires_at",
            ),
            IndexModel([("token_hash", ASCENDING)], name="idx_refresh_tokens_token_hash"),
            IndexModel([("family_id", ASCENDING)], name="idx_refresh_tokens_family_id"),
        ]
    )

    # 8. notifications
    await db.notifications.create_indexes(
        [
            IndexModel(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="idx_notifications_user_created_desc",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("read_at", ASCENDING)],
                name="idx_notifications_user_read",
            ),
        ]
    )

    # 9. audit_logs (append-only)
    await db.audit_logs.create_indexes(
        [
            IndexModel(
                [("target_type", ASCENDING), ("target_id", ASCENDING)],
                name="idx_audit_logs_target",
            ),
            IndexModel(
                [("actor_id", ASCENDING), ("at", DESCENDING)],
                name="idx_audit_logs_actor_at_desc",
            ),
        ]
    )

    # 10. import_jobs
    await db.import_jobs.create_indexes(
        [
            IndexModel(
                [("created_by", ASCENDING), ("created_at", DESCENDING)],
                name="idx_import_jobs_user_created_desc",
            ),
        ]
    )

    # 11. disposable_domains
    await db.disposable_domains.create_indexes(
        [
            IndexModel([("domain", ASCENDING)], unique=True, name="idx_disposable_domain_unique"),
        ]
    )

    # 12. subjects
    await db.subjects.create_indexes(
        [
            IndexModel(
                [("code", ASCENDING), ("department", ASCENDING)],
                unique=True,
                name="idx_subjects_code_dept_unique",
            ),
            IndexModel([("assigned_teacher_id", ASCENDING)], name="idx_subjects_teacher"),
            IndexModel([("department", ASCENDING), ("semester", ASCENDING)], name="idx_subjects_dept_sem"),
        ]
    )

    # 13. subject_marks
    await db.subject_marks.create_indexes(
        [
            IndexModel(
                [("student_id", ASCENDING), ("subject_id", ASCENDING), ("semester", ASCENDING)],
                unique=True,
                name="idx_marks_student_subject_sem_unique",
            ),
            IndexModel([("student_id", ASCENDING)], name="idx_marks_student"),
            IndexModel([("subject_id", ASCENDING)], name="idx_marks_subject"),
        ]
    )

    # 14. study_plans
    await db.study_plans.create_indexes(
        [
            IndexModel([("student_id", ASCENDING)], unique=True, name="idx_study_plans_student_unique"),
        ]
    )

    logger.info("All collection indexes created/verified successfully.")
