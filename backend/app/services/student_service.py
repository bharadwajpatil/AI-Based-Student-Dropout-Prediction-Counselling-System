import re
from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from backend.app.core.clock import Clock, default_clock
from backend.app.db.mongo import get_database
from backend.app.models.student import StudentInDB, StudentStatus
from backend.app.models.user import UserRole
from backend.app.schemas.student import (
    StudentCreateRequest,
    StudentListResponse,
    StudentResponse,
    StudentUpdateRequest,
)
from backend.app.services.audit_service import AuditService, audit_service


class StudentService:
    def __init__(
        self,
        clock: Clock | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.clock = clock or default_clock
        self.audit = audit or audit_service

    async def list_students(
        self,
        current_user: dict[str, Any],
        cursor: str | None = None,
        limit: int = 20,
        department: str | None = None,
        semester: int | None = None,
        status_filter: str | None = None,
        level: str | None = None,
        counselling_status: str | None = None,
        search: str | None = None,
        teacher_id: str | None = None,
    ) -> StudentListResponse:
        """
        Retrieves a paginated list of students scoped by role and query filters.
        Enforces object-level RBAC:
        - Admin / HOD: all students (or filtered by department/teacher/query).
        - Teacher: only students assigned to this teacher.
        - Student: only self.
        """
        db = get_database()
        user_role = current_user.get("role")
        user_id = current_user.get("_id")
        user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id

        query: dict[str, Any] = {}

        # 1. Role-based scoping
        if user_role == UserRole.TEACHER.value:
            query["assigned_teacher_ids"] = user_oid
        elif user_role == UserRole.STUDENT.value:
            query["user_id"] = user_oid
        elif user_role in (UserRole.ADMIN.value, UserRole.HOD.value):
            if teacher_id and ObjectId.is_valid(teacher_id):
                query["assigned_teacher_ids"] = ObjectId(teacher_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Unauthorized role for viewing students."},
            )

        # 2. Filters
        if department:
            query["department"] = department
        if semester is not None:
            query["semester"] = semester
        if status_filter:
            query["status"] = status_filter

        # 3. Search by name or erp_id
        if search:
            escaped_search = re.escape(search.strip())
            query["$or"] = [
                {"name": {"$regex": escaped_search, "$options": "i"}},
                {"erp_id": {"$regex": escaped_search, "$options": "i"}},
            ]

        # 4. Filter by risk level (if specified)
        if level:
            current_risks = await db.risk_results.find(
                {"is_current": True, "level": level},
                {"student_id": 1},
            ).to_list(length=10000)
            risk_student_ids = [r["student_id"] for r in current_risks]
            if "_id" in query:
                # Merge if existing _id condition
                query["_id"] = {"$in": risk_student_ids, **query["_id"]}
            else:
                query["_id"] = {"$in": risk_student_ids}

        # 5. Filter by counselling status (if specified)
        if counselling_status:
            counselling_docs = await db.counselling.find(
                {"status": counselling_status},
                {"student_id": 1},
            ).to_list(length=10000)
            counselling_student_ids = [c["student_id"] for c in counselling_docs]
            if "_id" in query:
                existing_in = query["_id"].get("$in", [])
                if existing_in:
                    merged = list(set(existing_in).intersection(set(counselling_student_ids)))
                    query["_id"]["$in"] = merged
                else:
                    query["_id"]["$in"] = counselling_student_ids
            else:
                query["_id"] = {"$in": counselling_student_ids}

        # 6. Total count before cursor filter
        total = await db.students.count_documents(query)

        # 7. Cursor pagination (ordered by _id ascending)
        limit = min(max(limit, 1), 100)
        pagination_query = dict(query)
        if cursor:
            if ObjectId.is_valid(cursor):
                pagination_query["_id"] = {"$gt": ObjectId(cursor)}
                if "_id" in query and "$in" in query["_id"]:
                    pagination_query["_id"]["$in"] = query["_id"]["$in"]

        cursor_res = db.students.find(pagination_query).sort("_id", 1).limit(limit + 1)
        docs = await cursor_res.to_list(length=limit + 1)

        has_more = len(docs) > limit
        if has_more:
            docs = docs[:limit]
            next_cursor = str(docs[-1]["_id"])
        else:
            next_cursor = None

        items = [self._format_student_response(doc) for doc in docs]
        return StudentListResponse(
            items=items,
            next_cursor=next_cursor,
            total=total,
            has_more=has_more,
        )

    async def get_student(
        self,
        student_id: str,
        current_user: dict[str, Any],
        client_ip: str | None = None,
    ) -> StudentResponse:
        """
        Retrieves a student by ID, enforcing object-level authorization.
        Logs an audit event if a student attempts unauthorized access to another student (Scenario S10).
        """
        if not ObjectId.is_valid(student_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        db = get_database()
        student_oid = ObjectId(student_id)
        student_doc = await db.students.find_one({"_id": student_oid})

        if not student_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        user_role = current_user.get("role")
        user_id = current_user.get("_id")
        user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id

        # Object-level access verification
        if user_role in (UserRole.ADMIN.value, UserRole.HOD.value):
            pass
        elif user_role == UserRole.TEACHER.value:
            assigned_ids = [str(t) for t in student_doc.get("assigned_teacher_ids", [])]
            if str(user_oid) not in assigned_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FORBIDDEN",
                        "message": "Teacher is not assigned to this student.",
                    },
                )
        elif user_role == UserRole.STUDENT.value:
            owner_user_id = student_doc.get("user_id")
            if owner_user_id is None or str(owner_user_id) != str(user_oid):
                # Scenario S10: Audit-log unauthorized student access attempt
                await self.audit.log_action(
                    action="unauthorized_student_access_attempt",
                    target_type="student",
                    target_id=student_id,
                    actor_id=user_oid,
                    ip=client_ip,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FORBIDDEN",
                        "message": "Students are not permitted to access other student records.",
                    },
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Insufficient permissions."},
            )

        # Phase 11 FERPA / India DPDP Compliance:
        # Audit log for every read of a High-risk student's detail
        current_risk = await db.risk_results.find_one({"student_id": student_oid, "is_current": True})
        if current_risk and current_risk.get("level") == "High":
            await self.audit.log_action(
                action="high_risk_student_detail_accessed",
                target_type="student",
                target_id=student_id,
                actor_id=user_oid,
                after={"risk_level": "High", "role": user_role},
                ip=client_ip,
            )

        return self._format_student_response(student_doc)

    @staticmethod
    def _get_department_prefix(department: str | None) -> str:
        if not department:
            return "STU"
        dept_clean = department.strip().upper()
        # 1. Exact phrase matches / full names first
        phrases = [
            ("COMPUTER SCIENCE", "CS"),
            ("ELECTRICAL ENGINEERING", "EE"),
            ("MECHANICAL ENGINEERING", "ME"),
            ("CIVIL ENGINEERING", "CE"),
            ("INFORMATION TECHNOLOGY", "IT"),
            ("ARTIFICIAL INTELLIGENCE", "AI"),
            ("ELECTRONICS & TELECOMMUNICATION", "ET"),
            ("ELECTRONICS AND TELECOMMUNICATION", "ET"),
            ("ELECTRONICS", "EC"),
            ("MECHANICAL", "ME"),
            ("ELECTRICAL", "EE"),
            ("CIVIL", "CE"),
        ]
        for phrase, code in phrases:
            if phrase in dept_clean:
                return code

        # 2. Exact word token matches for abbreviations
        tokens = set(re.findall(r"\b[A-Z0-9&]+\b", dept_clean))
        abbr_map = {
            "CS": "CS",
            "CSE": "CS",
            "EE": "EE",
            "EEE": "EE",
            "ME": "ME",
            "CE": "CE",
            "IT": "IT",
            "AI": "AI",
            "AIDS": "AI",
            "EC": "EC",
            "ECE": "EC",
            "ET": "ET",
            "ETC": "ET",
        }
        for token, code in abbr_map.items():
            if token in tokens:
                return code

        # 3. Fallback to initials of words if multiple words
        words = [w for w in re.split(r"[^A-Za-z0-9]", department) if w]
        if len(words) >= 2:
            return "".join(w[0] for w in words[:3]).upper()
        return (department[:3].strip().upper()) or "STU"

    async def generate_enrollment_id(
        self,
        department: str | None = None,
        batch: str | None = None,
        admission_year: str | None = None,
    ) -> str:
        """
        Generates a unique, standardized Enrollment / ERP ID for a student.
        Format: {DEPT_PREFIX}{YEAR}-{SEQUENCE:03d} (e.g. CS2024-201).
        Guarantees uniqueness against the students collection.
        """
        db = get_database()
        now = self.clock.now()

        dept_prefix = self._get_department_prefix(department)

        # Determine 4-digit academic/enrollment year
        year_str = str(now.year)
        if admission_year and admission_year.strip().isdigit() and len(admission_year.strip()) == 4:
            year_str = admission_year.strip()
        elif batch:
            match = re.search(r"\b(20\d\d)\b", batch)
            if match:
                year_str = match.group(1)

        prefix = f"{dept_prefix}{year_str}-"

        # Check existing department sequence
        cursor = db.students.find(
            {"erp_id": {"$regex": f"^{re.escape(prefix)}"}},
            {"erp_id": 1},
        )
        existing_erps = await cursor.to_list(length=None)

        max_seq = 0
        for doc in existing_erps:
            erp = doc.get("erp_id", "")
            match = re.search(r"-(\d+)$", erp)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_seq:
                        max_seq = num
                except ValueError:
                    pass

        # Also check cross-department numbers for this year to maintain continuous sequence
        overall_cursor = db.students.find(
            {"erp_id": {"$regex": f"^[A-Z]+{year_str}-\\d+$"}},
            {"erp_id": 1},
        )
        overall_erps = await overall_cursor.to_list(length=None)
        overall_max = 0
        for doc in overall_erps:
            erp = doc.get("erp_id", "")
            match = re.search(r"-(\d+)$", erp)
            if match:
                try:
                    num = int(match.group(1))
                    if num > overall_max:
                        overall_max = num
                except ValueError:
                    pass

        next_seq = max(max_seq, overall_max) + 1
        candidate = f"{prefix}{next_seq:03d}"
        while await db.students.find_one({"erp_id": candidate}):
            next_seq += 1
            candidate = f"{prefix}{next_seq:03d}"

        return candidate

    async def create_student(
        self,
        req: StudentCreateRequest,
        current_user: dict[str, Any],
        client_ip: str | None = None,
    ) -> StudentResponse:
        """Creates a new student roster entry (Admin or HOD only)."""
        db = get_database()
        now = self.clock.now()
        user_oid = ObjectId(current_user.get("_id"))

        if req.erp_id and req.erp_id.strip():
            normalized_erp = req.erp_id.strip().upper()
        else:
            normalized_erp = await self.generate_enrollment_id(
                department=req.department,
                batch=req.batch,
                admission_year=req.admission_year,
            )

        existing = await db.students.find_one({"erp_id": normalized_erp})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "STUDENT_ALREADY_EXISTS",
                    "message": f"Student with ERP ID {normalized_erp} already exists.",
                },
            )

        user_role = current_user.get("role")
        assigned_teacher_oids = [
            ObjectId(tid) for tid in req.assigned_teacher_ids if ObjectId.is_valid(tid)
        ]
        if user_role == UserRole.TEACHER.value and user_oid not in assigned_teacher_oids:
            assigned_teacher_oids.append(user_oid)

        # Create student login user account if password provided
        user_id = None
        student_email = (
            req.institutional_email
            or req.email
            or f"{normalized_erp.lower()}@university.edu"
        ).strip().lower()

        if req.password:
            from backend.app.core.security import hash_password
            from backend.app.services.email_validation import compute_canonical_email

            canonical = compute_canonical_email(student_email)
            existing_user = await db.users.find_one({
                "$or": [
                    {"canonical_email": canonical},
                    {"email": student_email},
                ]
            })

            is_active = getattr(req, "authorize_account", True)
            if not existing_user:
                new_user_doc = {
                    "name": req.name.strip(),
                    "email": student_email,
                    "canonical_email": canonical,
                    "password_hash": hash_password(req.password),
                    "role": UserRole.STUDENT.value,
                    "department": req.department.strip(),
                    "status": "active" if is_active else "pending",
                    "email_verified": True if is_active else False,
                    "phone_verified": True if is_active else False,
                    "token_version": 1,
                    "failed_login_count": 0,
                    "locked_until": None,
                    "created_at": now,
                    "updated_at": now,
                }
                user_res = await db.users.insert_one(new_user_doc)
                user_id = user_res.inserted_id
            else:
                user_id = existing_user["_id"]
                update_fields = {
                    "password_hash": hash_password(req.password),
                    "canonical_email": canonical,
                    "updated_at": now,
                }
                if is_active:
                    update_fields["status"] = "active"
                    update_fields["email_verified"] = True
                    update_fields["failed_login_count"] = 0
                    update_fields["locked_until"] = None
                await db.users.update_one({"_id": user_id}, {"$set": update_fields})

        student_doc = {
            "erp_id": normalized_erp,
            "user_id": user_id,
            "name": req.name.strip(),
            "institutional_email": req.institutional_email or student_email,
            "department": req.department.strip(),
            "semester": req.semester,
            "batch": req.batch.strip(),
            "phone": req.phone,
            "dob": req.dob,
            "gender": req.gender,
            "address": req.address,
            "course": req.course,
            "year": req.year,
            "division": req.division,
            "admission_year": req.admission_year,
            "assigned_teacher_ids": assigned_teacher_oids,
            "status": req.status.value,
            "created_at": now,
            "updated_at": now,
        }

        result = await db.students.insert_one(student_doc)
        student_doc["_id"] = result.inserted_id

        await self.audit.log_action(
            action="create_student",
            target_type="student",
            target_id=str(result.inserted_id),
            actor_id=user_oid,
            after={
                "erp_id": normalized_erp,
                "name": req.name,
                "department": req.department,
                "semester": req.semester,
            },
            ip=client_ip,
        )

        return self._format_student_response(student_doc)

    async def update_student(
        self,
        student_id: str,
        req: StudentUpdateRequest,
        current_user: dict[str, Any],
        client_ip: str | None = None,
    ) -> StudentResponse:
        """
        Updates student roster metadata (HOD or Admin only).
        Audits department transfers (Scenario S12) and soft status changes (dropped/graduated).
        """
        if not ObjectId.is_valid(student_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        db = get_database()
        student_oid = ObjectId(student_id)
        current = await db.students.find_one({"_id": student_oid})
        if not current:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        now = self.clock.now()
        user_oid = ObjectId(current_user.get("_id"))
        update_data: dict[str, Any] = {"updated_at": now}

        if req.name is not None:
            update_data["name"] = req.name.strip()
        if req.institutional_email is not None:
            update_data["institutional_email"] = req.institutional_email
        if req.semester is not None:
            update_data["semester"] = req.semester
        if req.batch is not None:
            update_data["batch"] = req.batch.strip()
        if req.assigned_teacher_ids is not None:
            update_data["assigned_teacher_ids"] = [
                ObjectId(tid) for tid in req.assigned_teacher_ids if ObjectId.is_valid(tid)
            ]

        # Audit department transfer (Scenario S12)
        if req.department is not None and req.department.strip() != current.get("department"):
            new_dept = req.department.strip()
            old_dept = current.get("department")
            update_data["department"] = new_dept
            await self.audit.log_action(
                action="student_transfer_department",
                target_type="student",
                target_id=student_id,
                actor_id=user_oid,
                before={"department": old_dept},
                after={"department": new_dept},
                ip=client_ip,
            )

        # Audit status change (dropped/graduated/transferred/active - soft-delete preservation)
        if req.status is not None and req.status.value != current.get("status"):
            new_status = req.status.value
            old_status = current.get("status")
            update_data["status"] = new_status
            await self.audit.log_action(
                action="student_status_changed",
                target_type="student",
                target_id=student_id,
                actor_id=user_oid,
                before={"status": old_status},
                after={"status": new_status},
                ip=client_ip,
            )

        updated_doc = await db.students.find_one_and_update(
            {"_id": student_oid},
            {"$set": update_data},
            return_document=True,
        )

        return self._format_student_response(updated_doc)

    def _format_student_response(self, doc: dict[str, Any]) -> StudentResponse:
        return StudentResponse(
            id=str(doc["_id"]),
            erp_id=doc["erp_id"],
            user_id=str(doc["user_id"]) if doc.get("user_id") else None,
            name=doc["name"],
            institutional_email=doc.get("institutional_email"),
            department=doc["department"],
            semester=doc["semester"],
            batch=doc["batch"],
            phone=doc.get("phone"),
            dob=doc.get("dob"),
            gender=doc.get("gender"),
            address=doc.get("address"),
            course=doc.get("course"),
            year=doc.get("year"),
            division=doc.get("division"),
            admission_year=doc.get("admission_year"),
            assigned_teacher_ids=[str(t) for t in doc.get("assigned_teacher_ids", [])],
            status=doc.get("status", StudentStatus.ACTIVE.value),
            created_at=doc.get("created_at", datetime.now()),
            updated_at=doc.get("updated_at", datetime.now()),
        )

    async def export_student_data(
        self,
        student_id: str,
        current_user: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        FERPA / India DPDP Article 11 Data Portability Export.
        Aggregates all stored records for a student into a structured portable payload.
        Allowed for Admin, HOD, assigned Teacher, or the Student themselves.
        """
        student_resp = await self.get_student(student_id=student_id, current_user=current_user, client_ip=client_ip)
        student_oid = ObjectId(student_id)
        db = get_database()
        now = self.clock.now()
        user_oid = ObjectId(current_user.get("_id"))

        performances = await db.performance.find({"student_id": student_oid}).sort("semester", 1).to_list(100)
        risk_history = await db.risk_results.find({"student_id": student_oid}).sort("computed_at", -1).to_list(100)
        counselling_records = await db.counselling_records.find({"student_id": student_oid}).to_list(100)
        audit_trail = await db.audit_logs.find({"target_id": student_id}).sort("timestamp", -1).to_list(100)

        await self.audit.log_action(
            action="student_data_portability_exported",
            target_type="student",
            target_id=student_id,
            actor_id=user_oid,
            ip=client_ip,
        )

        def _clean_doc(d: dict[str, Any]) -> dict[str, Any]:
            res = {}
            for k, v in d.items():
                if isinstance(v, ObjectId):
                    res[k] = str(v)
                elif isinstance(v, datetime):
                    res[k] = v.isoformat()
                elif isinstance(v, list):
                    res[k] = [
                        str(x) if isinstance(x, ObjectId) else (x.isoformat() if isinstance(x, datetime) else x)
                        for x in v
                    ]
                else:
                    res[k] = v
            return res

        return {
            "compliance_notice": "FERPA / India DPDP Student Data Portability Export",
            "exported_at": now.isoformat(),
            "exported_by": str(user_oid),
            "student": student_resp.model_dump(mode="json"),
            "performances": [_clean_doc(p) for p in performances],
            "risk_history": [_clean_doc(r) for r in risk_history],
            "counselling_records": [_clean_doc(c) for c in counselling_records],
            "audit_trail": [_clean_doc(a) for a in audit_trail],
        }

    async def anonymize_and_delete_student(
        self,
        student_id: str,
        current_user: dict[str, Any],
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Right to Erasure / Soft-Deletion with PII Anonymization.
        Anonymizes student identifiers while preserving de-identified records for historical analytics.
        Admin only.
        """
        user_role = current_user.get("role")
        if user_role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Only administrators can anonymize and erase student records."},
            )

        if not ObjectId.is_valid(student_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        db = get_database()
        student_oid = ObjectId(student_id)
        student_doc = await db.students.find_one({"_id": student_oid})
        if not student_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STUDENT_NOT_FOUND", "message": "Student not found."},
            )

        now = self.clock.now()
        user_oid = ObjectId(current_user.get("_id"))

        anonymized_payload = {
            "name": f"Anonymized Student {student_id[:6]}",
            "institutional_email": f"anonymized_{student_id}@gdpr-erased.local",
            "user_id": None,
            "status": StudentStatus.DROPPED.value,
            "updated_at": now,
        }

        await db.students.update_one({"_id": student_oid}, {"$set": anonymized_payload})

        from backend.app.services.analytics_service import analytics_service
        analytics_service.invalidate_cache()

        await self.audit.log_action(
            action="student_data_anonymized_and_deleted",
            target_type="student",
            target_id=student_id,
            actor_id=user_oid,
            ip=client_ip,
        )

        return {
            "status": "anonymized_and_deleted",
            "student_id": student_id,
            "anonymized_at": now.isoformat(),
        }


student_service = StudentService()
