# Project Architectural & Engineering Decisions

## Phase 1 Decisions

1. **MongoDB Connectivity & Transactions**:
   - The project uses MongoDB Atlas replica set (`rs-primary` / `rs-secondary`), enabling multi-document ACID transactions without requiring local Docker replica set hacks.
   - For containerized local development, `docker-compose.yml` provides a single-node replica set configuration (`rs0`).
   - A connection retry loop with exponential backoff handles transient DNS resolution latencies gracefully before failing loudly.

2. **Injected Time Abstraction (`Clock`)**:
   - Implemented `backend/app/core/clock.py` with `Clock` ABC, `SystemClock`, and `TestClock`.
   - All components requiring time (auth tokens, lockout, rate limiting) will accept a `Clock` dependency, avoiding `sleep` in tests.

3. **Error Handling Contract**:
   - All errors conform strictly to `{error: {code, message, details}}`.
   - `HTTPException` maps to `HTTP_<status_code>` or custom codes.
   - `RequestValidationError` maps to `VALIDATION_ERROR` with structured field paths.
   - Unhandled exceptions map to `INTERNAL_SERVER_ERROR` hiding sensitive internals in production.

4. **Request Correlation**:
   - `RequestIDMiddleware` guarantees that every request has a correlated `X-Request-ID` attached to contextvars for structured JSON logging and returned in response headers.

## Phase 2 Decisions

1. **Pydantic V2 BSON Modeling (`MongoBaseModel` & `PyObjectId`)**:
   - Standardized on `MongoBaseModel` with `extra="forbid"` across all models (Ground Rule 5) to protect against parameter injection.
   - `PyObjectId` accepts both native `bson.ObjectId` and valid 24-character hex strings, returning string representations for clean JSON API contracts while `to_mongo()` recursively converts to native BSON `ObjectId` for database persistence.

2. **Collection Index Strategy & TTL**:
   - Implemented compound indexes for frequent query patterns (`department+semester`, `(student_id, is_current)`, `(user_id, created_at desc)`).
   - Configured MongoDB TTL indexes with `expireAfterSeconds=0` on `auth_tokens.expires_at` and `refresh_tokens.expires_at` for automatic database-level document cleanup.
   - Verified that `create_indexes()` is strictly idempotent using `IndexModel`.

3. **Normalization & Domain Rules**:
   - `students.erp_id` is automatically stripped and converted to uppercase on validation (`MET101`).
   - Emails are lowercased and stripped.
   - Phone numbers strictly validate the `+` prefix for E.164 compliance.
   - `performance` documents enforce that `classes_held` must be present whenever `attendance` is provided.

## Phase 3 Decisions

1. **Multi-Layer Genuine Email Verification & Anti-Enumeration**:
   - Implemented layers 1–4 pre-filtering: `email-validator` normalization, `dnspython` MX/A resolution (with RFC 5321 A fallback), disposable email domain blocking, and role-based mailbox rejection.
   - Canonical email deduplication strips subaddressing tags (`+tag`) and normalizes Gmail dots to prevent duplicate abuse (Scenario A6).
   - Registrations with existing verified emails and forgot-password requests always return generic responses with equalized execution timing to defeat account enumeration (Scenarios A5, A11).
   - If someone registers with an already-verified email, a silent notification notice is dispatched to the genuine mailbox owner.

2. **Timing Attack & Brute-Force Defense**:
   - Login attempts for nonexistent users execute a precomputed dummy bcrypt verification (`DUMMY_BCRYPT_HASH`) ensuring response times remain constant regardless of account existence (Scenario A9).
   - 5 consecutive failed logins trigger exponential lockout (`locked_until = now + 15 min`).
   - Rate limiters throttle IP floods (20/min for login, 10/hour for password reset) and per-number SMS caps (5/day) to prevent cost abuse (Scenarios A8, A18).

3. **Session Security & Refresh Token Rotation**:
   - Access tokens (15-min lifetime) carry `token_version`. Modifying user passwords or detecting compromise increments `token_version`, immediately invalidating outstanding access tokens without database session lookups.
   - Refresh tokens are delivered via `httpOnly`, `Secure`, `SameSite=Strict` cookies.
   - Refresh token rotation tracks token families (`family_id`). If an already-rotated token is reused (indicating a stolen token), the entire token family is revoked immediately and `token_version` is bumped (Scenario A20).

4. **Multi-Channel Password Recovery & Automatic SMS Fallback**:
   - Single-use password reset tokens (32-byte URL-safe string or 6-digit numeric OTP) are stored exclusively as SHA-256 hashes.
   - Atomic consumption via `find_one_and_update({"_id": token_id, "used_at": None}, {"$set": {"used_at": now}})` eliminates double-submit race conditions (Scenario A14).
   - Password reset defaults to email. If email delivery permanently fails and the user possesses a verified phone number, the system automatically falls back to sending an SMS OTP (Scenario A15).
   - Reset endpoint enforces password history, rejecting reuse of the last 3 passwords (Scenario A21).

## Phase 4 Decisions

1. **RBAC & Object-Level Scoping for Students**:
   - `GET /students` and `GET /students/{id}` strictly enforce object-level authorization: HOD and Admin can view any student; Teachers can only view assigned students (`assigned_teacher_ids`); Students can only view their own record.
   - If a student user attempts to query another student's record (`GET /students/{other_id}`), a `403 Forbidden` is returned and an audit log entry is recorded with `action: unauthorized_student_access_attempt` (Scenario S10).

2. **Optimistic Concurrency Control (`If-Match`) for Performance**:
   - `PUT /students/{id}/performance/{semester}` requires the `If-Match: <version>` header when updating existing performance documents.
   - If two teachers attempt to edit the same record concurrently, the second write receives a `409 Conflict` with error code `CONCURRENT_MODIFICATION` providing the current version and record details to prompt for user merge (Scenario S2).
   - Atomic conditional updates increment `version` and write before/after state to `audit_logs`.

3. **CSV Formula Injection Neutralization**:
   - In `import_service.py`, cells starting with dangerous spreadsheet formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) are automatically sanitized by stripping leading trigger characters to prevent CSV formula execution (Scenario S15).

4. **High-Throughput Bulk Import & Error Isolation**:
   - `POST /students/import` processes up to 10 MB / 10,000 rows supporting both CSV (with UTF-8, UTF-8 BOM, Latin-1 detection) and XLSX files.
   - Employs pre-fetching and batch inserts (`insert_many`) combined with duplicate detection within the file.
   - Skips redundant no-op database updates on idempotent re-uploads of unchanged data, reducing runtime from minutes to milliseconds while preserving document versions.
   - Row-level errors are isolated into `errors: [{row, erp_id, reason}]` so malformed rows do not abort the valid rows (Scenario S3, Phase 4 Exit Gate).

## Phase 5 Decisions

1. **Pure Functional Risk Engine (`backend/app/risk/risk_engine.py`)**:
   - `compute_student_risk` is a pure function taking `RiskInputs`, an injected `Clock`, and optional `previous_risk_level`, containing zero database, network, or system clock calls (Ground Rule 4).
   - Half-up rounding via `decimal.Decimal.quantize(ROUND_HALF_UP)` guarantees unambiguous boundary resolution (e.g., 39.95 -> 40.0 -> Medium).
   - Defensive clamping strictly restricts raw and weighted risk sub-scores to `[0.0, 100.0]`.
   - Missing data renormalisation: when optional factors (marks, backlogs, trend, assignments, LMS engagement) are omitted, weights are redistributed proportionally across present factors to keep total weight = 1.0. Missing attendance raises a strict `ValueError`.
   - Override floors: active backlogs >= 4 enforce an unconditional risk floor of 75.0 (High Risk); attendance < 50% enforces a floor of 80.0 (High Risk).
   - Hysteresis stability: upward risk transitions are immediate, whereas downward transitions require a 3-point margin buffer (High -> Medium requires score < 67.0; Medium -> Low requires score < 37.0) to eliminate flapping around thresholds (40.0 and 70.0).

2. **Idempotent Risk Recomputation & Hash Tracking**:
   - `backend/app/risk/service.py` calculates a canonical SHA-256 `inputs_hash` over all inputs and engine version. Unchanged inputs bypass database writes and return the existing current assessment (Scenario R13).
   - Assessments maintain version history with atomic `is_current` status flips.
   - When an assessment evaluates to High Risk, an automated counselling session stub is created in `counselling_records` with top 3 contributing factors and actionable suggestions.

3. **Property-Based Testing & 100% Branch Coverage**:
   - Maintained 100% branch and statement coverage across all modules in `backend/app/risk/`.
   - Validated invariant guarantees using Hypothesis property tests (score bounded in [0, 100], strictly monotonic attendance sensitivity).

## Phase 6 Decisions

1. **PII Minimisation & Anonymised Prompts (`backend/app/counselling/prompt.py`)**:
   - Prompt payloads strictly exclude sensitive student identifiers (no name, email, phone, or ERP ID).
   - Generates deterministic anonymous tokens (`STUDENT-ANON-<hash>`), passing only academic context (department, semester, risk level, contributing factors, historical trajectory).
   - Observational teacher notes are enclosed inside `<teacher_notes>` tags with explicit prompt-injection defense disclaimers to prevent role or system instruction hijacking.

2. **Resilient AI Pipeline with Automatic Fallback (`backend/app/counselling/client.py` & `fallback.py`)**:
   - Configured `GeminiClient` with an 8.0 s timeout, structured JSON schema enforcement, and one-time automatic retry on malformed JSON outputs (Scenario S8).
   - Catches timeouts, quota exhaustion (HTTP 429), safety filter blocks, and missing API keys, falling back seamlessly to deterministic, factor-driven template recommendations (`ai_source: "template"`).
   - Service operations never fail with HTTP 500 when external AI providers are degraded or unavailable (Scenario S7, Phase 6 Exit Gate).

3. **Crisis Detection & Medical Diagnosis Guardrails (`backend/app/counselling/guardrails.py`)**:
   - Automated regex matching catches self-harm and crisis phrases in faculty notes or AI outputs, immediately setting `escalate_to_hod = True`, `refer_to_counsellor = True`, and adding urgent campus wellness contact directives.
   - Forbids clinical/psychiatric diagnostic terminology, sanitizing diagnostic claims into pedagogical and mentorship support framing.

4. **Workflow State Stepper & Append-Only Timeline (`backend/app/counselling/service.py`)**:
   - Supports case lifecycle: `pending -> in_progress -> follow_up -> resolved`.
   - Teacher meeting notes are recorded via atomic `$push` operations to `notes_timeline`, preventing concurrent overwrite collisions.
   - Resolved cases automatically reopen with status `pending` and timeline system notes if subsequent performance updates elevate a student's risk back to High (Scenario S14).
   - Detects outdated recommendations (`is_outdated: true`) whenever current risk evaluations differ from the assessment that generated the recommendation.

## Phase 7 Decisions

1. **Single-Pass Aggregation Pipeline (`$facet`) (`backend/app/services/analytics_service.py`)**:
   - Executes multi-dimensional analytics in a single MongoDB query, calculating active student count, risk tier buckets, pending counselling cases, watchlist count, and metric averages.
   - Unassessed or incomplete student records are strictly routed into an "Insufficient Data" bucket, never aggregated into Low risk.
   - Students with inactive status (`dropped`, `graduated`) are excluded from active KPI counters (Scenario S11).
   - Empty departments or zero-match queries return zeroed counts and null averages without 500 errors.

2. **Role-Based Object Scoping**:
   - Admin possesses campus-wide query visibility with optional department filtering.
   - HOD accounts are bound to their assigned department.
   - Teachers only view analytics aggregated over students assigned to them (`assigned_teacher_ids`).
   - Student users are denied access to institutional dashboard endpoints (403 Forbidden).

3. **Scatter Correlation & Trajectory Trend**:
   - Pearson correlation coefficient $r$ is calculated for attendance-vs-risk and marks-vs-risk, defensively guarding against zero variance.
   - `GET /analytics/trend` presents student semester-by-semester historical trajectory with object-level authorization checks.

4. **Spreadsheet Formula Injection Neutralization (`backend/app/services/analytics_service.py`)**:
   - In `export_high_risk_csv`, cells beginning with formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) are prefixed with `'` to prevent DDE/CSV formula execution in spreadsheet software (Scenario S15).

5. **Short-Term TTL Caching with Event Invalidation**:
   - Implemented 30-second in-memory caching keyed by user role, id, and query parameters to ensure overview responses remain sub-500ms under concurrent load (Scenario S13).
   - Recomputing risk in `RiskService` automatically invokes `invalidate_cache()` to ensure dashboards reflect data changes immediately.
## Phase 8 Decisions

1. **In-Memory SSE Event Broker & Bounded Buffer Reconnection (`backend/app/realtime/broker.py`)**:
   - `EventBroker` maintains an in-memory pub-sub registry with an ordered bounded ring buffer (500 events) storing past events with monotonic identifiers.
   - Upon reconnection with standard SSE `Last-Event-ID` header (or query param), the broker replays missed events before streaming live events.
   - Background heartbeat loop emits comment frames (`: ping\n\n`) every 25 seconds to prevent reverse-proxy, firewall, or NAT gateway timeouts.
   - Streaming endpoint (`GET /events`) supports standard `Authorization: Bearer <token>` header as well as `?token=` query parameter for native browser `EventSource` compatibility.

2. **Delivery-Time Dynamic Authorization (Scenario S9)**:
   - Event visibility is evaluated dynamically at delivery time, querying the live database state rather than caching permissions at connection establishment.
   - If a faculty member is unassigned from a student mid-session, ongoing SSE stream connection remains open for heartbeats and global alerts, but student-specific events (`risk.changed`, `student.updated`) are immediately dropped at delivery time without requiring stream reconnection.

3. **Risk Flapping Suppression & Notification Anti-Spam (Scenarios S1 & S6)**:
   - Risk recomputation (`RiskService.recompute_student_risk`) triggers `risk.changed` SSE events and writes to `db.notifications` only when the evaluated `level` changes compared to previous assessment.
   - In conjunction with Phase 5 hysteresis thresholds (downgrade buffer margin of 3 points), minor flapping performance updates around thresholds (40.0 and 70.0) do not cause repetitive alert spam.

4. **Background Import Real-Time Progress Streaming (Scenario S3)**:
   - Bulk CSV import (`ImportService.import_students_csv`) publishes incremental `import.progress` SSE events (`processed`, `total`, `successful`, `failed`, `is_complete`) scoped specifically to the initiating user's ID.
   - Allows frontend import dialogs to render smooth progress indicators without polling.

## Phase 9 Decisions

1. **Design Tokens & Warm Visual Identity**:
   - Implemented Tailwind tokens specified in §9.1: cream backgrounds (`#FFFBF5`), clay primary terracotta (`#D2734E`), sand borders (`#EADBC8`), sage for low risk (`#5E8C6E`), amber for medium risk (`#F2B84B`), rose for high risk (`#E5787A`), and warm ink typography (`#2B211B`), avoiding sterile corporate blues or harsh blacks.
   - Dark mode utilizes warm charcoal backgrounds (`#1F1A17`) with desaturated accents.
   - Typography uses Inter for body and Poppins for headings.
   - Respects `prefers-reduced-motion` across animated KPI counters, toasts, and card transitions.

2. **Accessible Risk Representation & WCAG AA**:
   - Risk tiers are represented with the `RiskBadge` component which always combines color with unambiguous icons (CheckCircle, AlertTriangle, ShieldAlert, HelpCircle) and clear text labels, ensuring accessibility for color-blind users.
   - High-risk escalation includes subtle pulsing animations without layout shifts.

3. **Role-Scoped Dashboard Architectures**:
   - Admin & HOD views prioritize institutional KPI metrics (enrolled, high-risk ratio, pending counselling, watchlist count) and prioritized high-risk cohort actions.
   - Teacher views emphasize assigned mentorship cohorts, pending meetings, and rapid performance editing.
   - Student view provides supportive, non-alarmist health framing focused on attendance consistency and direct mentor contacts.

4. **Real-Time Integration & Background Import Feedback**:
   - Centralized `useRealtime` hook connects to SSE `/api/v1/events?token=<jwt>` with exponential reconnection backoff.
   - Bulk CSV import dialog displays real-time progress bars and processed/successful/failed metrics driven by `import.progress` events.
   - Real-time toast notifications alert faculty when student risk tiers escalate or new counselling assignments arrive.

5. **Optimistic Concurrency Control (OCC) in Performance Editing**:
   - Performance update modals supply the `If-Match: "<version>"` header, intercepting HTTP 409 and 412 conflicts gracefully with instructive toast alerts when concurrent updates occur.

## Phase 10 Decisions

1. **End-to-End Integration Verification (`backend/tests/test_e2e_verification.py`)**:
   - `test_e2e_refresh_token_rotation_and_reuse_revocation`: Simulates an active token reuse attack; verifies that submitting a previously consumed refresh token revokes the entire user token family immediately, increments the user `token_version`, and rejects any subsequent access token generation attempts.
   - `test_e2e_complete_faculty_and_student_lifecycle`: Exercises full cross-system lifecycle:
     - Admin registers students; faculty queries assigned student roster.
     - Performance update is recorded with OCC `If-Match` version checking.
     - Conflicting stale versions are rejected with HTTP 409 Conflict.
     - Pure risk engine determines Low risk initially.
     - Escalating attendance drop (< 50%) activates deterministic override floor, transitioning the student to High Risk.
     - High risk transition creates an automated counselling case stub and pushes an in-app notification to the assigned faculty.
     - AI recommendation is generated (with automatic fallback to template recommendation if external LLM endpoints are unreachable).
     - Case transitions to `in_progress` and meeting notes are added to the append-only timeline.
     - Single-pass `$facet` analytics reflects active student counts and risk tiers.
     - CSV export successfully neutralizes spreadsheet formula injection.

2. **Static Application Security Testing (Bandit Audit)**:
   - Automated scan across all backend source code (`backend/app`) identified **0 High** and **0 Medium** severity vulnerabilities across 6,726 lines of code.

3. **High-Concurrency Load Simulation (`load_tests/locustfile.py`)**:
   - Created automated Locust load suite simulating 500 concurrent authenticated faculty and administrator users.
   - Models realistic user behavior: dashboard aggregation metrics, cursor-paginated student listings, risk evaluations, and high-risk report downloads.

4. **API Versioning & Backward Compatibility**:
   - Mounted all routers under `/api/v1` and root prefix in `backend/app/main.py` ensuring client version flexibility.

## Phase 11 Decisions

1. **Security Headers Middleware (`backend/app/core/middleware.py`)**:
   - Enforces OWASP-recommended security headers across all incoming requests and responses:
     - `X-Content-Type-Options: nosniff` (defends against MIME-confusion attacks).
     - `X-Frame-Options: DENY` and `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self';` (neutralizes clickjacking and iframe nesting).
     - `X-XSS-Protection: 0` (modern standard to avoid buggy legacy browser auditor exploits).
     - `Referrer-Policy: strict-origin-when-cross-origin`.
     - `Permissions-Policy: camera=(), microphone=(), geolocation=()`.
     - HSTS (`Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`) applied under HTTPS or production configuration.

2. **NoSQL Injection Defense**:
   - `NoSQLInjectionMiddleware` inspects all incoming query string parameters and JSON request bodies recursively.
   - Any key beginning with `$` (MongoDB operator prefix) or containing `.` (nested path injection) is rejected immediately with HTTP 400 Bad Request (`PROHIBITED_INPUT_KEY`).
   - Downstream endpoints and database queries exclusively consume typed Pydantic models, preventing raw dictionary parameter passing.

3. **Request Body Size Limits & DoS Protection**:
   - `RequestSizeLimitMiddleware` inspects `Content-Length` headers before streaming or buffering payloads:
     - Standard JSON endpoints are capped at 2MB (`MAX_REQUEST_SIZE_BYTES`).
     - Bulk CSV/Excel file import routes (`/imports` and `/students/import`) are capped at 15MB (`MAX_UPLOAD_SIZE_BYTES`).
     - Requests exceeding thresholds are rejected with HTTP 413 `PAYLOAD_TOO_LARGE`.

4. **Sliding Window Rate Limiting**:
   - `RateLimitingMiddleware` implements an in-memory sliding window rate limiter tracking client IP addresses.
   - Enforces stricter per-minute limits on sensitive authentication endpoints (`/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`).
   - Emits RFC-compliant `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` response headers, returning HTTP 429 Too Many Requests with a `Retry-After` header when limits are exceeded.

5. **FERPA / India DPDP Student Privacy Compliance & Access Audits**:
   - **High-Risk Access Auditing**: Every access to a High-risk student's details (`GET /students/{id}`) records an immutable audit log entry (`high_risk_student_detail_accessed`) with actor, role, timestamp, and IP to comply with educational privacy standards.
   - **Data Portability (Right of Access)**: Implemented `GET /api/v1/students/{id}/export-data`, allowing authorized personnel or the student themselves to export all demographics, performance history, risk assessments, counselling records, and audit logs as a portable JSON document.
   - **Right to Erasure (Soft Anonymization)**: Implemented `DELETE /api/v1/students/{id}` for administrators, replacing identifiable PII (name, email) with anonymized tokens while preserving de-identified academic structure for institutional cohort statistics.

6. **Fairness & Decision Support Advisory**:
   - Explicitly added `decision_support_advisory` to `RiskResultResponse` and rendered prominent notice banners in `StudentDetailPage` and counselling cards confirming that risk assessments are decision-support aids for faculty mentorship rather than automated determinations.

## Phase 12 Decisions

1. **Multi-Stage Containerization (`backend/Dockerfile` & `frontend/Dockerfile`)**:
   - **Backend**: Implemented multi-stage Python 3.11 build isolating build-essential dependencies from final runtime. Executes with a non-root user (`appuser:appgroup`), includes integrated curl healthchecks on `/health`, and runs multi-worker Uvicorn.
   - **Frontend**: Utilizes Node 20 builder stage compiled into an Alpine Nginx server image.
   - **Nginx Reverse Proxy & SPA Fallback (`frontend/nginx.conf`)**: Injects `try_files $uri $uri/ /index.html` to eliminate 404 errors during client-side route refreshes, and proxies `/api` and `/events` SSE stream connections without buffering (`proxy_buffering off; chunked_transfer_encoding off`).

2. **Synthetic Dataset Generation & Seeding (`scripts/seed_demo_data.py`)**:
   - Creates institutional accounts across all primary personas: Super Admin, Computer Science HOD, Electrical Engineering HOD, Assigned Faculty (2 members), and a Demo Student.
   - Generates 200 synthetic students across realistic risk distribution:
     - 50% Low Risk
     - 25% Medium Risk
     - 20% High Risk (combining attendance floor triggers, backlog overrides, and compound score declines)
     - 5% Insufficient Data (newly matriculated students without recorded semesters)
   - Pre-computes deterministic risk scores, automated counselling cases, AI recommendations with template fallbacks, and chronological timeline entries.
   - Supports both standalone CLI execution and test fixture injection (`target_db=mock_db`).

3. **System Documentation & Architecture Guide (`README.md`)**:
   - Generated comprehensive project documentation including full Mermaid architectural flowchart, Docker Compose instructions, manual local development workflows, environment variable directory, test suite execution instructions, and ethical decision-support disclaimers.




