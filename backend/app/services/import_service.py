import csv
import io
from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from backend.app.core.clock import Clock, default_clock
from backend.app.db.mongo import get_database
from backend.app.models.import_job import ImportStatus
from backend.app.models.student import StudentStatus
from backend.app.schemas.import_job import ImportJobResponse
from backend.app.services.audit_service import AuditService, audit_service

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ROWS = 10000


class ImportService:
    def __init__(
        self,
        clock: Clock | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.clock = clock or default_clock
        self.audit = audit or audit_service

    async def create_import_job(
        self,
        file: UploadFile,
        current_user: dict[str, Any],
    ) -> str:
        """
        Creates an initial import job entry in the database.
        """
        db = get_database()
        now = self.clock.now()
        user_id = current_user.get("_id")
        user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id

        filename = file.filename or "unknown.csv"
        job_doc = {
            "created_by": user_oid,
            "filename": filename,
            "status": ImportStatus.PROCESSING.value,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "errors": [],
            "processed_cursor": 0,
            "created_at": now,
        }
        res = await db.import_jobs.insert_one(job_doc)
        return str(res.inserted_id)

    async def process_file(
        self,
        job_id: str,
        file_bytes: bytes,
        filename: str,
        current_user: dict[str, Any],
        client_ip: str | None = None,
        resume_from: int = 0,
    ) -> ImportJobResponse:
        """
        Processes bulk student/performance data from CSV or XLSX.
        Enforces:
        - Max 10 MB / 10 000 rows.
        - UTF-8 / UTF-8 BOM / Latin-1 encoding detection.
        - CSV Formula Injection defense (Scenario S15).
        - In-file duplicate detection.
        - Row-level error isolation (Scenario S3).
        - Idempotent upserts.
        - Resumable cursor (Scenario S4).
        """
        db = get_database()
        job_oid = ObjectId(job_id)

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            err = [{"row": 0, "erp_id": "", "reason": "File exceeds maximum size of 10 MB."}]
            await db.import_jobs.update_one(
                {"_id": job_oid},
                {"$set": {"status": ImportStatus.FAILED.value, "errors": err}},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "FILE_TOO_LARGE", "message": "File exceeds 10 MB limit."},
            )

        # 1. Parse rows into structured dictionaries
        try:
            raw_rows = self._parse_file_to_rows(file_bytes, filename)
        except Exception as e:
            err = [{"row": 0, "erp_id": "", "reason": f"Failed to parse file: {str(e)}"}]
            await db.import_jobs.update_one(
                {"_id": job_oid},
                {"$set": {"status": ImportStatus.FAILED.value, "errors": err}},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "PARSE_ERROR", "message": f"Could not parse file: {str(e)}"},
            )

        total_rows = len(raw_rows)
        if total_rows > MAX_ROWS:
            err = [{"row": 0, "erp_id": "", "reason": f"File contains {total_rows} rows, exceeding 10,000 maximum."}]
            await db.import_jobs.update_one(
                {"_id": job_oid},
                {"$set": {"status": ImportStatus.FAILED.value, "errors": err}},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "TOO_MANY_ROWS", "message": "File exceeds 10,000 rows limit."},
            )

        # Update initial total
        await db.import_jobs.update_one(
            {"_id": job_oid},
            {"$set": {"total": total_rows, "status": ImportStatus.PROCESSING.value}},
        )

        user_id = current_user.get("_id")
        user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id

        succeeded = 0
        failed = 0
        errors: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, int, str]] = set()

        now = self.clock.now()

        # 2. Iterate and validate rows
        valid_rows: list[tuple[int, dict[str, Any]]] = []
        for idx, row in enumerate(raw_rows, start=1):
            if idx <= resume_from:
                continue

            row_errors, clean_data = self._validate_and_sanitize_row(idx, row, seen_keys)
            if row_errors:
                failed += len(row_errors)
                errors.extend(row_errors)
                continue

            valid_rows.append((idx, clean_data))

        # 3. Batch process valid rows
        if valid_rows:
            all_erp_ids = list({data["erp_id"] for _, data in valid_rows})
            existing_students = await db.students.find({"erp_id": {"$in": all_erp_ids}}).to_list(length=None)
            student_map = {s["erp_id"]: s for s in existing_students}

            students_to_insert = []
            for _, data in valid_rows:
                erp_id = data["erp_id"]
                if erp_id in student_map:
                    curr_s = student_map[erp_id]
                    # Check if student details actually changed
                    has_changes = (
                        curr_s.get("name") != data["name"]
                        or curr_s.get("department") != data["department"]
                        or curr_s.get("semester") != data["semester"]
                        or curr_s.get("batch") != data["batch"]
                        or (
                            data.get("institutional_email")
                            and curr_s.get("institutional_email") != data.get("institutional_email")
                        )
                    )
                    if has_changes:
                        s_oid = curr_s["_id"]
                        await db.students.update_one(
                            {"_id": s_oid},
                            {
                                "$set": {
                                    "name": data["name"],
                                    "department": data["department"],
                                    "semester": data["semester"],
                                    "batch": data["batch"],
                                    "institutional_email": data.get("institutional_email")
                                    or curr_s.get("institutional_email"),
                                    "updated_at": now,
                                }
                            },
                        )
                else:
                    new_oid = ObjectId()
                    new_doc = {
                        "_id": new_oid,
                        "erp_id": erp_id,
                        "user_id": None,
                        "name": data["name"],
                        "institutional_email": data.get("institutional_email"),
                        "department": data["department"],
                        "semester": data["semester"],
                        "batch": data["batch"],
                        "assigned_teacher_ids": [],
                        "status": StudentStatus.ACTIVE.value,
                        "created_at": now,
                        "updated_at": now,
                    }
                    students_to_insert.append(new_doc)
                    student_map[erp_id] = new_doc

            if students_to_insert:
                await db.students.insert_many(students_to_insert)

            # Performance records batching
            all_student_oids = [s["_id"] for s in student_map.values()]
            existing_perfs = await db.performance.find({"student_id": {"$in": all_student_oids}}).to_list(length=None)
            perf_map = {(p["student_id"], p["semester"], p["academic_year"]): p for p in existing_perfs}

            perfs_to_insert = []
            for _, data in valid_rows:
                if any(
                    data.get(k) is not None
                    for k in ("attendance", "marks", "backlogs", "assignments", "engagement")
                ):
                    s_oid = student_map[data["erp_id"]]["_id"]
                    sem = data["semester"]
                    ay = data.get("academic_year", "2025-26")
                    perf_key = (s_oid, sem, ay)

                    if perf_key in perf_map:
                        curr_p = perf_map[perf_key]
                        # Check if performance values actually changed
                        perf_changed = (
                            curr_p.get("attendance") != data.get("attendance")
                            or curr_p.get("classes_held") != data.get("classes_held")
                            or curr_p.get("marks") != data.get("marks")
                            or curr_p.get("backlogs") != data.get("backlogs")
                            or curr_p.get("assignments") != data.get("assignments")
                            or curr_p.get("engagement") != data.get("engagement")
                        )
                        if perf_changed:
                            await db.performance.update_one(
                                {"_id": curr_p["_id"]},
                                {
                                    "$set": {
                                        "attendance": data.get("attendance"),
                                        "classes_held": data.get("classes_held"),
                                        "marks": data.get("marks"),
                                        "backlogs": data.get("backlogs"),
                                        "assignments": data.get("assignments"),
                                        "engagement": data.get("engagement"),
                                        "version": curr_p.get("version", 1) + 1,
                                        "updated_by": user_oid,
                                        "updated_at": now,
                                    }
                                },
                            )
                    else:
                        new_perf = {
                            "_id": ObjectId(),
                            "student_id": s_oid,
                            "semester": sem,
                            "academic_year": ay,
                            "attendance": data.get("attendance"),
                            "classes_held": data.get("classes_held"),
                            "marks": data.get("marks"),
                            "backlogs": data.get("backlogs"),
                            "assignments": data.get("assignments"),
                            "engagement": data.get("engagement"),
                            "version": 1,
                            "updated_by": user_oid,
                            "updated_at": now,
                        }
                        perfs_to_insert.append(new_perf)
                        perf_map[perf_key] = new_perf

            if perfs_to_insert:
                await db.performance.insert_many(perfs_to_insert)

            succeeded += len(valid_rows)

        # 4. Finalize Job
        final_status = ImportStatus.COMPLETED.value
        await db.import_jobs.update_one(
            {"_id": job_oid},
            {
                "$set": {
                    "status": final_status,
                    "succeeded": succeeded,
                    "failed": failed,
                    "errors": errors,
                    "processed_cursor": total_rows,
                }
            },
        )

        await self.audit.log_action(
            action="bulk_import_students",
            target_type="import_job",
            target_id=job_id,
            actor_id=user_oid,
            after={"total": total_rows, "succeeded": succeeded, "failed": failed},
            ip=client_ip,
        )

        # Emit SSE import.progress event (Scenario S3)
        from backend.app.realtime.broker import event_broker
        from backend.app.realtime.events import AppEvent

        await event_broker.publish(
            AppEvent(
                event_type="import.progress",
                target_user_ids={str(user_oid)},
                data={
                    "job_id": job_id,
                    "processed": total_rows,
                    "total": total_rows,
                    "succeeded": succeeded,
                    "failed": failed,
                    "status": final_status,
                },
            )
        )

        job_doc = await db.import_jobs.find_one({"_id": job_oid})
        return self._format_job_response(job_doc)

    async def get_import_job(
        self,
        job_id: str,
        current_user: dict[str, Any],
    ) -> ImportJobResponse:
        """Retrieves import job progress and error report."""
        if not ObjectId.is_valid(job_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": "Import job not found."},
            )

        db = get_database()
        job_oid = ObjectId(job_id)
        job = await db.import_jobs.find_one({"_id": job_oid})
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": "Import job not found."},
            )

        return self._format_job_response(job)

    def _parse_file_to_rows(self, file_bytes: bytes, filename: str) -> list[dict[str, str]]:
        """Parses CSV or XLSX bytes into a list of row dicts."""
        lower_name = filename.lower()
        if lower_name.endswith(".xlsx"):
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            header_row = next(rows_iter, None)
            if not header_row:
                return []
            headers = [str(h).strip().lower() if h is not None else "" for h in header_row]

            rows: list[dict[str, str]] = []
            for row in rows_iter:
                if not any(row):
                    continue
                row_dict = {}
                for h, val in zip(headers, row):
                    if h:
                        row_dict[h] = str(val).strip() if val is not None else ""
                rows.append(row_dict)
            return rows

        else:
            # CSV Handling with UTF-8 BOM and encoding fallbacks
            text = None
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    text = file_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue

            if text is None:
                raise ValueError("Unsupported or unreadable file encoding.")

            f = io.StringIO(text)
            reader = csv.DictReader(f)
            rows = []
            for r in reader:
                # Normalize keys to lower-case stripped
                cleaned_row = {k.strip().lower(): (v.strip() if v else "") for k, v in r.items() if k}
                rows.append(cleaned_row)
            return rows

    def _sanitize_string(self, val: str | None) -> str:
        """Strips leading formula trigger characters (=, +, -, @) to prevent CSV injection (Scenario S15)."""
        if not val:
            return ""
        stripped = val.strip()
        while stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
            stripped = stripped[1:].strip()
        return stripped

    def _validate_and_sanitize_row(
        self,
        row_num: int,
        row: dict[str, str],
        seen_keys: set[tuple[str, int, str]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Validates individual row, neutralizing CSV formula injection (Scenario S15)
        and isolating errors (Scenario S3).
        """
        errors: list[dict[str, Any]] = []
        clean: dict[str, Any] = {}

        raw_erp = self._sanitize_string(row.get("erp_id"))
        if not raw_erp:
            errors.append({"row": row_num, "erp_id": "", "reason": "Missing required 'erp_id'."})
            return errors, clean

        erp_id = raw_erp.upper()
        clean["erp_id"] = erp_id

        name = self._sanitize_string(row.get("name"))
        if not name:
            errors.append({"row": row_num, "erp_id": erp_id, "reason": "Missing required 'name'."})
        clean["name"] = name

        department = self._sanitize_string(row.get("department"))
        if not department:
            errors.append({"row": row_num, "erp_id": erp_id, "reason": "Missing required 'department'."})
        clean["department"] = department

        # Semester validation
        raw_sem = self._sanitize_string(row.get("semester"))
        try:
            semester = int(raw_sem)
            if not (1 <= semester <= 12):
                errors.append(
                    {"row": row_num, "erp_id": erp_id, "reason": f"Semester must be between 1 and 12, got {raw_sem}."}
                )
            clean["semester"] = semester
        except ValueError:
            errors.append({"row": row_num, "erp_id": erp_id, "reason": f"Invalid semester value '{raw_sem}'."})
            clean["semester"] = 1

        batch = self._sanitize_string(row.get("batch"))
        if not batch:
            errors.append({"row": row_num, "erp_id": erp_id, "reason": "Missing required 'batch'."})
        clean["batch"] = batch

        clean["institutional_email"] = self._sanitize_string(row.get("institutional_email")) or None
        academic_year = self._sanitize_string(row.get("academic_year")) or "2025-26"
        clean["academic_year"] = academic_year

        # Check duplicate within the same import file
        dedup_key = (erp_id, clean["semester"], academic_year)
        if dedup_key in seen_keys:
            errors.append(
                {
                    "row": row_num,
                    "erp_id": erp_id,
                    "reason": f"Duplicate record for {erp_id} in semester {clean['semester']} within the import file.",
                }
            )
        else:
            seen_keys.add(dedup_key)

        # Performance fields
        clean["attendance"] = self._parse_float_field(row.get("attendance"), "attendance", row_num, erp_id, errors)
        clean["classes_held"] = self._parse_int_field(row.get("classes_held"), "classes_held", row_num, erp_id, errors)

        # Consistency: classes_held required if attendance is provided
        if clean["attendance"] is not None and clean["classes_held"] is None:
            errors.append(
                {"row": row_num, "erp_id": erp_id, "reason": "classes_held is required when attendance is provided."}
            )

        clean["marks"] = self._parse_float_field(row.get("marks"), "marks", row_num, erp_id, errors)
        clean["backlogs"] = self._parse_int_field(row.get("backlogs"), "backlogs", row_num, erp_id, errors, max_val=50)
        clean["assignments"] = self._parse_float_field(row.get("assignments"), "assignments", row_num, erp_id, errors)
        clean["engagement"] = self._parse_float_field(row.get("engagement"), "engagement", row_num, erp_id, errors)

        return errors, clean

    def _parse_float_field(
        self,
        val: str | None,
        field_name: str,
        row_num: int,
        erp_id: str,
        errors: list[dict[str, Any]],
    ) -> float | None:
        if not val or not val.strip():
            return None
        clean_v = val.strip().lstrip("'")
        try:
            f = float(clean_v)
            if not (0.0 <= f <= 100.0):
                errors.append(
                    {"row": row_num, "erp_id": erp_id, "reason": f"{field_name} must be between 0 and 100, got {f}."}
                )
                return None
            return f
        except ValueError:
            errors.append(
                {"row": row_num, "erp_id": erp_id, "reason": f"Invalid numeric value for {field_name}: '{val}'."}
            )
            return None

    def _parse_int_field(
        self,
        val: str | None,
        field_name: str,
        row_num: int,
        erp_id: str,
        errors: list[dict[str, Any]],
        max_val: int | None = None,
    ) -> int | None:
        if not val or not val.strip():
            return None
        clean_v = val.strip().lstrip("'")
        try:
            i = int(clean_v)
            if i < 0:
                errors.append({"row": row_num, "erp_id": erp_id, "reason": f"{field_name} must be >= 0, got {i}."})
                return None
            if max_val is not None and i > max_val:
                errors.append(
                    {"row": row_num, "erp_id": erp_id, "reason": f"{field_name} exceeds max {max_val}, got {i}."}
                )
                return None
            return i
        except ValueError:
            errors.append(
                {"row": row_num, "erp_id": erp_id, "reason": f"Invalid integer value for {field_name}: '{val}'."}
            )
            return None

    def _format_job_response(self, doc: dict[str, Any]) -> ImportJobResponse:
        return ImportJobResponse(
            id=str(doc["_id"]),
            created_by=str(doc["created_by"]),
            filename=doc["filename"],
            status=doc["status"],
            total=doc.get("total", 0),
            succeeded=doc.get("succeeded", 0),
            failed=doc.get("failed", 0),
            errors=doc.get("errors", []),
            created_at=doc.get("created_at", datetime.now()),
        )


import_service = ImportService()
