# AI-Based Student Dropout Prediction & Counselling System — Implementation Plan

> **Audience:** an autonomous coding agent. Execute phases in order. Each phase has a goal, tasks, edge cases, and an **exit gate** (tests that must pass before moving on). Do not skip gates.

**Stack:** React + TypeScript + Tailwind (frontend) · FastAPI (backend) · MongoDB (Motor/Beanie or PyMongo) · JWT auth · SMTP/SendGrid email · Twilio (or any provider) SMS · Gemini API for counselling text.

---

## 0. Ground Rules (apply to every phase)

1. **Backend is the source of truth.** Risk is computed server-side only. The frontend never calculates risk.
2. **Pure risk engine.** `risk_engine.py` has no DB, network, or clock access. Input dict in → result dict out. This makes it exhaustively testable.
3. **Never store secrets or raw tokens.** Hash passwords (bcrypt/argon2). Store only SHA-256 hashes of reset tokens, OTPs, and refresh tokens.
4. **Never leak existence of accounts.** Login, forgot-password, and resend endpoints return generic responses.
5. **Every write is validated** with Pydantic models; reject unknown fields (`extra="forbid"`).
6. **Config via env vars** (`python-dotenv` / `pydantic-settings`). Provide `.env.example`. No secrets in git.
7. **Every external call** (SMTP, SMS, Gemini, DNS) sits behind an interface with a timeout, retry with backoff, and a test fake.
8. **Time is injected** (a `Clock` dependency) so expiry/lockout tests don't use `sleep`.
9. Write tests alongside code, not afterwards.

### Suggested repo layout

```text
repo/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           # config, security, clock, logging, rate_limit
│   │   ├── db/             # mongo client, indexes, migrations
│   │   ├── models/         # Pydantic/Beanie documents
│   │   ├── schemas/        # request/response DTOs
│   │   ├── routers/        # auth, students, performance, risk, counselling, admin, events
│   │   ├── services/       # auth_service, email_validation, notifier (email/sms), counselling_service, import_service
│   │   ├── risk/           # risk_engine.py, config.py (weights/thresholds), explain.py
│   │   ├── integrations/   # smtp.py, sms.py, gemini.py, dns_checker.py (all behind interfaces)
│   │   └── jobs/           # background tasks (recompute, import, digest)
│   ├── tests/              # unit/ integration/ scenarios/
│   └── pyproject.toml
├── frontend/
│   └── src/ (components, pages, features, hooks, api, styles, tests)
├── docker-compose.yml      # mongo, backend, frontend, mailhog (dev email)
└── IMPLEMENTATION_PLAN.md
```

---

## Phase 1 — Foundation & Environment

**Goal:** runnable skeleton with DB, config, health checks, CI.

Tasks
- `docker-compose.yml`: MongoDB (with replica set enabled so transactions work), backend, frontend, **MailHog** for catching dev emails.
- FastAPI app with `/health` (checks Mongo ping), structured JSON logging, request-ID middleware, global exception handler returning `{error: {code, message, details}}`.
- CORS restricted to configured frontend origin.
- Mongo connection with startup retry; create all indexes on startup (idempotent).
- Lint/format/type-check (ruff, mypy, eslint, prettier), GitHub Actions running tests.

Edge cases
- Mongo not ready at boot → retry with backoff, then fail loudly.
- Missing env var → app refuses to start with a clear message (never silently default secrets).

**Exit gate:** `docker compose up` works; `/health` green; CI passes on empty tests.

---

## Phase 2 — Data Model (MongoDB)

**Goal:** all collections, validators, and indexes.

### Collections

**users**
```json
{
  "_id": "ObjectId",
  "name": "str",
  "email": "str (normalized, lowercase)",
  "email_verified": false,
  "phone_e164": "+91XXXXXXXXXX | null",
  "phone_verified": false,
  "password_hash": "str",
  "role": "student | teacher | hod | admin",
  "status": "pending_verification | pending_approval | active | locked | disabled",
  "failed_login_count": 0,
  "locked_until": "datetime | null",
  "token_version": 0,
  "created_at": "datetime", "updated_at": "datetime", "last_login_at": "datetime | null"
}
```
Indexes: unique `email`; unique sparse `phone_e164`; `role`.

**students** (the *roster*; may exist before the user registers)
```json
{ "_id": "ObjectId", "erp_id": "MET101", "user_id": "ObjectId | null",
  "name": "str", "institutional_email": "str | null",
  "department": "AI&DS", "semester": 8, "batch": "2022-26",
  "assigned_teacher_ids": ["ObjectId"], "status": "active | transferred | dropped | graduated",
  "created_at": "datetime", "updated_at": "datetime" }
```
Indexes: unique `erp_id`; `department+semester`; `assigned_teacher_ids`; `user_id`.

**performance** (one document per student **per semester**; history kept)
```json
{ "_id": "ObjectId", "student_id": "ObjectId", "semester": 8, "academic_year": "2025-26",
  "attendance": 72, "classes_held": 120, "marks": 65, "backlogs": 1,
  "assignments": 80, "engagement": 55,
  "version": 3, "updated_by": "ObjectId", "updated_at": "datetime" }
```
Indexes: unique `(student_id, semester, academic_year)`.
Any numeric field may be `null` (= not yet recorded). `version` is for optimistic concurrency.

**risk_results** (append-only history; latest flagged `is_current`)
```json
{ "_id": "ObjectId", "student_id": "ObjectId", "performance_id": "ObjectId",
  "score": 25.1, "level": "Low | Medium | High | Insufficient Data",
  "confidence": 0.8, "watchlist": false,
  "factors": [{"name":"attendance","risk":36.0,"weight":0.30,"contribution":10.8}],
  "overrides_applied": ["attendance_below_50"],
  "engine_version": "1.0.0", "inputs_hash": "sha256", "computed_at": "datetime", "is_current": true }
```
Indexes: `(student_id, is_current)`, `(student_id, computed_at desc)`, `level`.
`inputs_hash` lets recompute be **idempotent** (same inputs + engine version → no new row).

**counselling**
```json
{ "_id": "ObjectId", "student_id": "ObjectId", "teacher_id": "ObjectId", "risk_result_id": "ObjectId",
  "risk_level": "High", "ai_recommendation": "str", "ai_source": "gemini | template",
  "notes": "str", "status": "pending | in_progress | follow_up | resolved",
  "follow_up_date": "datetime | null", "created_at": "datetime", "updated_at": "datetime" }
```

**auth_tokens** (email verification, password reset, SMS OTP)
```json
{ "_id": "ObjectId", "user_id": "ObjectId", "purpose": "verify_email | reset_password | verify_phone | reset_sms",
  "token_hash": "sha256", "channel": "email | sms", "attempts": 0, "max_attempts": 5,
  "expires_at": "datetime", "used_at": "datetime | null", "created_at": "datetime" }
```
TTL index on `expires_at` (cleanup). Index `(user_id, purpose)`.

**refresh_tokens**: `{user_id, token_hash, family_id, expires_at, revoked_at, user_agent, ip}`.
**notifications**: `{user_id, type, payload, read_at, created_at}`.
**audit_logs**: `{actor_id, action, target_type, target_id, before, after, ip, at}` (append-only).
**import_jobs**: `{created_by, filename, status, total, succeeded, failed, errors[], created_at}`.
**disposable_domains**: `{domain}` (seeded from an open blocklist, refreshable).

Edge cases
- Student exists in roster but no user yet → allowed (roster first, account later).
- Student transfers department mid-semester → keep `_id`, update department, write audit log, history untouched.
- Duplicate `erp_id` differing only by case/whitespace → normalize (`strip().upper()`) before insert.

**Exit gate:** index creation idempotent; schema validation tests (bad types, out-of-range) fail correctly.

---

## Phase 3 — Authentication & Account Security

**Goal:** register, verify email/phone, login, refresh, logout, forgot/reset password via email **or SMS**.

### 3.1 Registration

Endpoint: `POST /auth/register` → `{name, email, password, phone?, role, erp_id?}`

Rules
- **Student:** must supply `erp_id`; it must exist in the roster, be unclaimed (`user_id == null`), and the email must match `institutional_email` if one is on file. This blocks fake/impersonated student accounts.
- **Teacher / HOD:** account created as `pending_approval`; an admin must approve. Never allow self-registration as `admin`.
- Password policy: ≥ 10 chars, reject top-common-passwords list, reject if contains email local part. Show strength meter on the UI.
- Account is `pending_verification` until the email is verified. Unverified users cannot log in.

### 3.2 Verifying that an email is genuine (layered; be honest about what each layer proves)

| Layer | Library / method | Catches |
|---|---|---|
| 1. Syntax + normalisation | `email-validator` (`check_deliverability=False` here), lowercase, strip, reject > 254 chars | typos, malformed input |
| 2. Domain DNS | `dnspython`: MX lookup (fallback to A record per RFC 5321); 3 s timeout | non-existent domains |
| 3. Disposable-domain blocklist | `disposable_domains` collection, also check subdomains | mailinator-style throwaways |
| 4. Role/alias rejection | block `admin@`, `info@`, `noreply@`, `test@` etc. for personal accounts | shared/dummy mailboxes |
| 5. Optional deliverability API | `EmailVerifier` interface (ZeroBounce/Abstract/Kickbox adapter, off by default) | non-existent mailboxes, catch-alls |
| 6. **Ownership proof (the only real proof)** | one-time verification link **and** 6-digit fallback code sent to the address | fake-but-valid addresses |

Only layer 6 proves the person controls the mailbox. Layers 1–5 are cheap pre-filters. Account stays unusable until layer 6 passes.

Edge cases
- DNS timeout/transient failure → **do not reject**; fall through to ownership proof, log a warning (avoids blocking real users when DNS is flaky).
- `user+tag@gmail.com`: store as typed for sending, but compute a `canonical_email` (strip `+tag`, and dots for gmail) for uniqueness checks to prevent duplicate abuse.
- Unicode/IDN domains → punycode-normalise.
- Verification link clicked twice → second click returns "already verified" (idempotent, not an error).
- Verification token expired (24 h) → `POST /auth/resend-verification` (rate limited: 3/hour/user, 10/hour/IP).
- User registers with someone else's email → owner never clicks link; account stays unverified and is auto-purged after 7 days. Existing verified account with same email → generic response ("If this is new, check your inbox"), never "email taken" (prevents enumeration).

### 3.3 Phone verification (needed for SMS fallback)

- Validate with `phonenumbers` → E.164 only; reject VOIP/invalid ranges if provider lookup is enabled.
- Send 6-digit OTP via SMS provider; store hash; 10-min expiry; max 5 attempts; then invalidate and require a new send.
- Phone is optional at registration, but **required to use SMS recovery**. Prompt users to add/verify it after first login.

### 3.4 Login

`POST /auth/login` → access JWT (15 min) in memory on the client + refresh token in **httpOnly, Secure, SameSite=Strict cookie** (7 days, rotated every use).

- Generic error `"Invalid email or password"` for unknown user, wrong password, or unverified email (unverified gets a separate, safe hint only *after* correct password).
- Lockout: 5 consecutive failures → `locked_until = now + 15 min` (exponential on repeats). Also IP-based rate limit (e.g. 20/min).
- Constant-time behaviour: when the user doesn't exist, still run a dummy bcrypt verify so response time doesn't leak existence.
- JWT claims: `sub, role, token_version, exp, jti`. Backend rejects if `token_version` mismatches DB (enables instant revocation).
- Refresh-token **reuse detection**: if a rotated-out token is reused → revoke the entire `family_id` and force re-login.
- RBAC dependency `require_role(...)` plus **object-level checks** (teacher only sees assigned students; student only sees self).

### 3.5 Forgot / Reset password — email first, SMS fallback

`POST /auth/forgot-password` → `{identifier, channel?: "email"|"sms"}` (identifier = email or phone)

Decision logic
1. Always respond `200 {"message":"If an account exists, we've sent instructions."}` regardless of outcome. Equalise timing.
2. Look up user. If none → do nothing (still generic response).
3. Channel selection:
   - `channel="email"` (default) → send to the **verified** email on file.
   - `channel="sms"` (user explicitly picks "Send SMS instead") → allowed only if `phone_verified == true`.
   - **Automatic fallback to SMS** if email is unavailable: email unverified, hard-bounced, or provider reports permanent failure — and a verified phone exists.
   - Neither channel available → generic response + write audit log; UI tells user to contact admin/HOD (manual reset flow below).
4. Email: single-use link containing a 32-byte URL-safe random token (stored as hash), expiry **15 min**.
   SMS: 6-digit OTP (cryptographically random), expiry **10 min**, 5 attempts max.
5. Rate limit: 3 requests/hour per account, 10/hour per IP, 1 per 60 s (UI shows countdown). Cap SMS per number/day to prevent SMS-pumping cost abuse; optional CAPTCHA after 2 requests.
6. Only the newest token per purpose is valid — issuing a new one invalidates older ones.

`POST /auth/reset-password` → `{token | (identifier+otp), new_password}`
- Verify hash match, not expired, not used, attempts < max. Mark used atomically (`find_one_and_update` with `used_at: null` filter) to defeat double-submit races.
- Apply password policy; reject reuse of the last 3 passwords.
- On success: bump `token_version`, revoke all refresh tokens, clear lockout, send a "Your password was changed" notice to email (and SMS if configured).
- Receiving a reset email proves mailbox ownership → may also set `email_verified = true`.

Manual fallback: HOD/Admin can trigger `POST /admin/users/{id}/force-reset` (audited), which sends a link to the verified channel — admins never see or set passwords.

Edge cases
- Email provider outage → queue with retries (3 attempts, exponential backoff); after final failure mark `channel_failed` and auto-offer SMS.
- SMS delivery receipts/webhook: mark undelivered, allow resend.
- Attacker spams victim's email → rate limits + generic responses; victim's account is never locked by reset requests.
- Link prefetched by email security scanners (GET consumes token?) → reset link opens a **page**; consumption happens only on `POST` with new password.
- Phone number reassigned to a new owner → require re-verification every 12 months or after SIM-change signal, and notify email on any phone change.
- Changing email/phone requires current password **and** OTP to both old and new contact.

**Exit gate:** all auth tests in §10 green; manual run against MailHog shows verification + reset emails; SMS adapter tested with fake provider.

---

## Phase 4 — Student, Performance & Import APIs

Endpoints (all RBAC + object-level scoped)
- `GET/POST/PATCH /students`, `GET /students/{id}` (HOD/Admin: any; Teacher: assigned only; Student: self).
- `PUT /students/{id}/performance/{semester}` with `If-Match: <version>` header.
- `POST /students/import` (CSV/XLSX) → creates `import_jobs`, processed in background; `GET /imports/{id}` for progress.
- Pagination (cursor-based), filtering (department, semester, level, counselling status), search by name/ERP.

Validation
- `attendance`, `marks`, `assignments`, `engagement`: 0–100 float or `null`. `backlogs`: int 0–50. `semester`: 1–12.
- `classes_held` required if `attendance` is provided (so sample size is known).

Edge cases
- **Concurrent edits:** two teachers update the same record → second gets `409 Conflict` with current version; UI shows a merge prompt.
- **Bulk import:** idempotent upsert by `erp_id` + semester; row-level errors collected (don't abort whole file); max 10 MB / 10 000 rows; reject formulas starting with `= + - @` (CSV injection); detect encoding (UTF-8 BOM); report duplicates within the file.
- Student marked `dropped/graduated` → excluded from active dashboards but history preserved; never hard-delete (soft delete + audit).
- Teacher unassigned from student while viewing → next request 403; UI handles gracefully.
- Marks edited retroactively → writes audit log with before/after and triggers recompute.

**Exit gate:** CRUD + RBAC matrix tests pass; import test with 5 000 rows incl. 50 bad rows completes with correct report.

---

## Phase 5 — Risk Engine (the core)

**Goal:** deterministic, explainable, versioned. Score 0–100, higher = riskier.

### 5.1 Component risks (each 0–100)

| Component | Formula | Notes |
|---|---|---|
| attendance | `clamp((90 − attendance) / 50 × 100)` | 90%+ → 0, 40% or less → 100 |
| marks | `clamp((75 − marks) / 45 × 100)` | 75+ → 0, 30 or less → 100 |
| backlogs | `min(backlogs × 25, 100)` | 4+ → 100 |
| assignments | `clamp((80 − assignments) / 60 × 100)` | 80+ → 0, 20 or less → 100 |
| trend | `drop = prev_marks − marks`; `clamp(drop / 20 × 100)` (no risk if marks rose) | needs previous semester |
| engagement | `100 − engagement` | optional signal (LMS/logins/participation) |

### 5.2 Weights (sum = 1.00; keep in `risk/config.py`, never hard-coded in logic)

`attendance 0.30 · marks 0.25 · backlogs 0.15 · trend 0.12 · assignments 0.10 · engagement 0.08`

### 5.3 Missing data

- Compute over **available** components only; renormalise: `score = Σ(risk × w) / Σ(w available)`.
- `confidence = Σ(w available)`. If `confidence < 0.50` → level `"Insufficient Data"` (no High/Low claim), UI shows "Needs data".
- Attendance with `classes_held < 20` (or < 25 % of the semester) → treat attendance as unavailable (too small a sample to judge).

### 5.4 Overrides (applied after the weighted score)

| Rule | Effect |
|---|---|
| attendance < 50 | `score = max(score, 70)` → High |
| backlogs ≥ 4 | `score = max(score, 70)` |
| backlogs ≥ 2 | `score = max(score, 40)` |
| trend risk ≥ 80 (marks fell ≥ 16 pts) | set `watchlist = true` even if level is Low |

Always list applied overrides in `overrides_applied` so the UI can explain *why*.

### 5.5 Levels, rounding, stability

- Round score to **1 decimal (half-up)** *before* classifying. `0–39.9 Low · 40–69.9 Medium · 70–100 High`. (So 39.95 → 40.0 → Medium.)
- **Hysteresis:** upgrading is immediate; downgrading requires the score to be at least **3 points below** the threshold (High→Medium needs < 67; Medium→Low needs < 37). Prevents flapping on noisy data.
- Output includes sorted `factors` (top contributors first) for explainability.
- `engine_version` bumps whenever weights/thresholds change; old results remain readable.

### 5.6 Triggering

- Recompute automatically on any performance create/update/import row (background task, debounced per student 2 s).
- Idempotent via `inputs_hash`.
- Write new `risk_results` row, flip previous `is_current=false` in the **same transaction**.
- If level changed (or became High) → emit event (Phase 8) and create `counselling` stub with status `pending`.

Edge cases
- Non-numeric/NaN/Infinity → rejected at validation, engine also guards (`math.isfinite`).
- Values > 100 or < 0 slipping in → engine clamps defensively and logs.
- Backlogs reduced after re-exam → score drops; hysteresis still applies.
- Previous semester missing (first semester / transfer) → trend unavailable, not zero-risk (affects confidence).

**Exit gate:** engine unit tests (§10.2) 100 % branch coverage; property tests (Hypothesis): score always in [0,100]; monotonic — lowering attendance never lowers score.

---

## Phase 6 — AI Counselling Module

**Goal:** helpful, safe recommendations that never block the workflow.

Flow: `risk_result → build structured prompt → Gemini → validate → save → show to teacher`.

- Prompt includes **only** risk level, top factors, trend, semester, department. **Do not send name, email, phone, or ERP ID** (minimise PII). Use an anonymous token.
- Ask Gemini for **JSON output** (`summary`, `actions[]`, `follow_up_in_days`, `escalate_to_hod: bool`); validate with Pydantic; on invalid JSON retry once, then fall back.
- **Template fallback** (rule-based text per factor) used when: Gemini timeout (8 s), quota/429, safety block, invalid output, or no API key. Mark `ai_source: "template"`.
- Cache by `inputs_hash` so unchanged data doesn't re-bill.
- Guardrails: system prompt forbids medical/psychiatric diagnoses; if output mentions self-harm keywords or the teacher's notes do, flag `escalate_to_hod` and show a "refer to professional counsellor" banner.
- Prompt-injection safety: teacher notes are passed as quoted data, never as instructions.
- Counselling workflow: `pending → in_progress → follow_up → resolved`; follow-up reminders via notifications; resolved cases reopen automatically if risk rises again.

Edge cases
- Concurrent teacher notes on the same case → append-only note entries instead of overwriting.
- AI recommendation generated for an outdated risk result → show "based on data from <date>" and offer regenerate.

**Exit gate:** tests with Gemini mocked: success, timeout, malformed JSON, 429 — all yield a usable recommendation.

---

## Phase 7 — Analytics & Dashboards (API)

- `GET /analytics/overview`: totals, counts by level, counselling pending (single aggregation pipeline using `$facet`).
- `GET /analytics/distribution`, `/attendance-vs-risk`, `/marks-vs-risk`, `/by-department`, `/by-semester`, `/trend?student_id=` (risk over time).
- All queries scoped by role (teacher → assigned students; HOD → own department; admin → all).
- Short cache (30–60 s) invalidated by risk-change events.
- Reports: CSV/PDF export of high-risk students (background job for > 1 000 rows).

Edge cases: empty department → zeros not errors; "Insufficient Data" students shown as their own bucket, never mixed into Low.

---

## Phase 8 — Real-Time & Background Processing

- **SSE (or WebSocket) channel** `/events`, authenticated, scoped per user. Events: `risk.changed`, `counselling.assigned`, `import.progress`, `notification.new`.
- Reconnect with `Last-Event-ID` so no events are lost during short disconnects; heartbeat every 25 s.
- Background tasks via FastAPI `BackgroundTasks` for small work; **ARQ/Celery + Redis** (optional) for imports/reports. Jobs are idempotent and retry-safe.
- Notifications: in-app always; email for High-risk transitions to the assigned teacher (batched into a daily digest to avoid spam; immediate only for new High).
- Race protection: use MongoDB transactions or `find_one_and_update` with version filters for risk flip + counselling stub creation.

Edge cases
- 3 000 simultaneous updates from an import → debounce per student, process in chunks of 200, emit one aggregated `import.progress` rather than 3 000 events.
- User has 5 tabs open → each gets events; UI dedupes by event ID.
- Server restart mid-import → job resumes from last committed chunk (store cursor in `import_jobs`).

---

## Phase 9 — Frontend (React + TypeScript + Tailwind)

### 9.1 Design language — "warm, friendly, calm"

Tailwind tokens (extend theme):

```ts
colors: {
  cream:  { 50:'#FFFBF5', 100:'#FFF4E6' },        // page background
  clay:   { 400:'#E08E6B', 500:'#D2734E', 600:'#B85C3A' }, // primary (terracotta)
  sand:   { 200:'#EADBC8', 300:'#DCC7AC' },        // borders
  sage:   { 400:'#8FB39A', 600:'#5E8C6E' },        // low risk / success
  amber:  { 400:'#F2B84B', 600:'#C98A12' },        // medium risk
  rose:   { 400:'#E5787A', 600:'#C2474A' },        // high risk / danger
  ink:    { 700:'#4A3B32', 900:'#2B211B' }         // warm dark text (never pure black)
},
fontFamily: { sans: ['Inter','system-ui'], display: ['"Poppins"','Inter','sans-serif'] },
borderRadius: { xl:'0.9rem', '2xl':'1.25rem' },
boxShadow: {
  soft: '0 1px 2px rgba(74,59,50,.06), 0 2px 6px rgba(74,59,50,.05)',
  lift: '0 4px 12px rgba(74,59,50,.10), 0 2px 4px rgba(74,59,50,.06)'
}
```
Dark mode: warm charcoal (`#1F1A17`) background with the same accent hues desaturated 10 %.

### 9.2 Interaction rules

- **Shadows:** small and soft only (`shadow-soft` at rest).
- **Hover on cards/rows/buttons:** `hover:shadow-lift hover:-translate-y-0.5 transition duration-200 ease-out`.
- **Buttons:** primary clay; `active:scale-[.98]`; focus ring `ring-2 ring-clay-400/50 ring-offset-2`; loading spinner replaces label (width stays fixed, no layout jump).
- **Entry animation:** fade + 8 px slide-up (`animate-fade-up`, 250 ms), staggered 40 ms for list/card grids.
- **Numbers:** KPI counters count up over 600 ms on first load only.
- **Charts:** Recharts with animated draw-in (600 ms), warm palette, tooltips with soft shadow; risk colors always paired with an icon/label (not color alone).
- **Risk badge:** `Low` sage, `Medium` amber, `High` rose with subtle pulse **only** for newly escalated cases; `Insufficient Data` neutral sand.
- **Skeleton loaders** (shimmer) for tables/cards — no blank flashes. Friendly empty states with illustration + one clear action.
- **Toasts:** slide in from top-right, auto-dismiss 4 s, pause on hover.
- **Respect `prefers-reduced-motion`:** disable transforms/animations (keep opacity fades only).
- Accessibility: WCAG AA contrast on cream backgrounds, keyboard navigable, visible focus, ARIA labels, `aria-live` for toasts and real-time updates.
- Responsive: mobile-first; tables collapse to cards under 640 px.

### 9.3 Pages & components

| Area | Contents |
|---|---|
| Auth | Login, Register (role-aware; student asks for ERP ID), Verify-email (link + code entry), Forgot password (email default; **"Send SMS instead"** link; resend countdown), Reset password (strength meter), Verify-phone |
| Student | Profile, marks/attendance charts, risk status with explained factors ("why am I at this level?"), counselling recommendations (read-only), supportive tone |
| Teacher | Assigned students table (filter/sort/search), student detail (risk history chart, factors, AI recommendation, notes timeline, status stepper), data-entry form with conflict handling |
| HOD/Admin | KPI cards, charts (distribution, dept/semester analysis, attendance/marks vs risk), user management & approvals, bulk import with progress bar + error report download, reports, audit log viewer |
| Shared | Notification bell (real-time), role-based nav, 403/404 pages, session-expired modal |

### 9.4 Frontend behaviour & edge cases

- Access token kept **in memory** (not localStorage); silent refresh via cookie; single in-flight refresh promise shared by concurrent requests (avoid refresh stampede).
- Axios/fetch interceptor: 401 → refresh once → retry; if it fails → redirect to login preserving the intended route.
- Route guards by role; UI hides disallowed actions but **never relies on hiding** (backend enforces).
- Forms: React Hook Form + Zod mirroring backend rules; server field errors mapped back onto inputs; disable submit while pending; debounce email-availability hints (must not reveal existence — show only format/domain problems).
- Optimistic UI only for notes; performance edits wait for server (version conflicts → show diff dialog).
- Offline/slow network banner; SSE reconnect with backoff; stale-data indicator.
- Large tables virtualised (≥ 500 rows); server-side pagination.
- Time zones: store UTC, display local.
- Sanitise any rendered AI/teacher text (no `dangerouslySetInnerHTML`).

**Exit gate:** Vitest + React Testing Library for components; Playwright e2e for happy paths (§10.4); Lighthouse a11y ≥ 95.

---

## Phase 10 — Testing Strategy

### 10.1 Layers
- Unit (risk engine, validators, token utils) · Integration (FastAPI + real Mongo via testcontainers) · Scenario tests (below) · E2E (Playwright + MailHog) · Load (Locust: 500 concurrent dashboard users, 5 000-row import) · Security (OWASP checklist, `bandit`, `pip-audit`, `npm audit`).
- Coverage target: ≥ 90 % backend, 100 % branch on `risk/`.

### 10.2 Risk-engine scenario tests (deterministic — expected values pre-computed from §5)

Use `pytest.mark.parametrize`. Tolerance ±0.1.

| # | Scenario | Input | Expected |
|---|---|---|---|
| R1 | Typical borderline student (Rahul) | att 72, marks 65, backlogs 1, assign 80; trend & engagement null | components: att 36.0, marks 22.2, backlog 25, assign 0 → weighted 20.1 ÷ 0.80 = **25.1 → Low**, confidence 0.80 |
| R2 | Multi-factor collapse | att 55, marks 40 (prev 55), backlogs 3, assign 30, engagement 20 | att 70, marks 77.8, backlog 75, assign 83.3, trend 75, eng 80 → **75.4 → High**, no override needed |
| R3 | Hidden decline (great attendance, falling marks) | att 95, marks 70 (prev 88), backlogs 0, assign 90, engagement 70 | score ≈ **16.0 → Low** **but `watchlist = true`** (trend 90 ≥ 80) |
| R4 | Override: attendance collapse only | att 48, marks 85, backlogs 0, assign 95, engagement 80 | weighted ≈ 26.8 → override floor → **70.0 → High**, `overrides_applied=["attendance_below_50"]` |
| R5 | Insufficient data | att 60 only, everything else null | confidence 0.30 → **"Insufficient Data"**, no numeric level |
| R6 | Tiny attendance sample | att 40 but `classes_held = 8`, marks 80, assign 85 | attendance ignored (too few classes) → Low; reason noted in factors |
| R7 | Rounding boundary | craft inputs giving 39.95 | rounds to 40.0 → **Medium** |
| R8 | Hysteresis up/down | scores in sequence 69.0 → 70.4 → 68.9 → 66.9 | Medium → **High** → **High (held)** → **Medium** |
| R9 | Backlog floor | backlogs 2, everything else perfect | weighted ≈ 3.75 → floor **40 → Medium** |
| R10 | Improvement | marks rose 50 → 80 | trend risk 0 (never negative); score drops accordingly |
| R11 | Extremes | att 0, marks 0, backlogs 10, assign 0, eng 0, prev marks 100 | all components 100 → **100.0**, clamped |
| R12 | Perfect student | att 100, marks 100, backlogs 0, assign 100, eng 100 | **0.0 → Low** |
| R13 | Bad input | att 120 / −5 / NaN / "abc" | API → `422`; engine called directly clamps and logs, never crashes |
| R14 | Idempotency | recompute twice with same inputs | one `risk_results` row; second call returns existing |
| R15 | Engine version change | bump weights | new row with new `engine_version`; old rows untouched |

### 10.3 Real-time / system scenarios (integration)

| # | Scenario | Expectation |
|---|---|---|
| S1 | Teacher updates attendance 82 → 48 | within 2 s: new risk row (High via override), `risk.changed` SSE to assigned teacher + HOD, counselling stub `pending`, AI recommendation generated or template fallback |
| S2 | Two teachers edit same student simultaneously | one succeeds, other gets `409` with latest version; no lost update; one audit entry each for successful writes |
| S3 | Bulk import 5 000 rows (50 invalid, 100 duplicates of existing) | job completes; 4 850 upserted idempotently; error report lists 50 rows with reasons; SSE progress monotonic; re-uploading same file creates 0 new risk rows |
| S4 | Import killed mid-way (restart server) | resumes from stored cursor; no duplicate rows |
| S5 | New semester begins, only 2 weeks of data | attendance sample too small → no false High; confidence reflects it; dashboards show "Needs data" |
| S6 | Student flaps around threshold across 5 edits (68, 70.5, 69, 68, 66) | level changes at most High once and Medium once; notifications not spammed (max 1 per transition) |
| S7 | Gemini down/timeout | counselling still produced from template within 10 s; `ai_source="template"`; no 500 |
| S8 | Gemini returns invalid JSON then valid on retry | stored valid recommendation; one retry logged |
| S9 | Teacher unassigned mid-session | next API call 403; SSE stream stops delivering that student's events |
| S10 | Student tries `GET /students/{other_id}/risk` | `403` (or `404`), audit-logged |
| S11 | Student marked `dropped` | excluded from active KPIs; history intact; no new counselling stubs |
| S12 | Student transfers department | dept analytics move; old department's history unaffected; audit entry |
| S13 | Dashboard under 500 concurrent users | p95 < 500 ms for overview; no DB connection exhaustion |
| S14 | Counselling case resolved, then risk rises again | case auto-reopens as `pending`, teacher notified |
| S15 | CSV with `=cmd|' /C calc'!A0` in a name cell | cell neutralised/rejected; export escapes leading `= + - @` |

### 10.4 Auth scenario tests

| # | Scenario | Expectation |
|---|---|---|
| A1 | Register with `x@mailinator.com` | rejected (disposable) |
| A2 | Register with `x@nonexistent-domain-12345.xyz` | rejected (no MX/A) |
| A3 | DNS resolver times out | not rejected; proceeds to verification; warning logged |
| A4 | Register student with unknown/claimed `erp_id` | rejected generically; claimed ID can't be re-claimed |
| A5 | Register with already-verified email | generic response; **no** "email exists" leak; owner receives a "someone tried to register" notice |
| A6 | `User+tag@Gmail.com` vs `user@gmail.com` | treated as same canonical identity |
| A7 | Login before verifying email | blocked after correct password with "verify your email" hint |
| A8 | 5 wrong passwords | account locked 15 min; correct password during lock still fails; after clock advance, succeeds |
| A9 | Login timing, unknown vs known user | response-time difference within noise (dummy hash executed) |
| A10 | Teacher registers | `pending_approval`; cannot log in until admin approves; admin approval audited |
| A11 | Forgot password, unknown email | identical 200 response and similar latency; nothing sent |
| A12 | Forgot password, verified email | one email in MailHog; link valid 15 min |
| A13 | Reset link used twice / after expiry / after a newer link issued | 2nd use, expired, and superseded tokens all fail with generic error |
| A14 | Concurrent double-submit of same reset token | exactly one succeeds |
| A15 | Email provider fails permanently, verified phone exists | auto-fallback: SMS OTP sent; response still generic |
| A16 | User picks "Send SMS instead", phone unverified | no SMS; generic response; audit log |
| A17 | SMS OTP wrong 5× | token invalidated; new request required; rate limits apply |
| A18 | SMS request flood (20 requests / 1 min) | throttled; per-number/day cap enforced |
| A19 | Successful reset | old JWTs and refresh tokens rejected (`token_version` bump); "password changed" notice sent |
| A20 | Refresh-token reuse (stolen token) | whole token family revoked; both parties logged out |
| A21 | Reset to one of last 3 passwords / weak password | rejected with specific policy message |
| A22 | Email security scanner issues GET on reset link | token NOT consumed (only POST consumes) |
| A23 | Role escalation attempt (`role: "admin"` in register body / JWT tampering) | rejected; signature check fails |

### 10.5 Frontend E2E (Playwright)
Register → open MailHog message → verify → login → dashboard; forgot password via email; forgot password via SMS (fake provider); teacher edits marks → sees live risk badge update without refresh; import file with errors → progress bar → download error report; keyboard-only login; reduced-motion mode.

**Exit gate:** all suites green in CI; load test thresholds met; security scan has no high findings.

---

## Phase 11 — Security, Privacy & Hardening

- HTTPS/HSTS, secure headers (CSP, X-Content-Type-Options, frame-ancestors none), strict CORS.
- Rate limiting (per IP and per account) with Redis or in-memory fallback; request size limits.
- NoSQL-injection defence: Pydantic-typed inputs only; never pass raw dicts from clients into Mongo queries; reject keys starting with `$`.
- Student data is sensitive (education records, potentially covered by FERPA/GDPR/India DPDP): encrypt at rest, minimise PII to third parties, role-scoped access, retention policy, data export/delete workflow, audit logs for every read of a High-risk student's detail.
- Dependency scanning, secrets scanning in CI, backups (daily `mongodump`, tested restore).
- Fairness note: risk results are **decision support**, not decisions. UI copy must say so; expose factor explanations; allow teachers to add context/override notes (overrides audited, never silently change the score).

---

## Phase 12 — Deployment & Operations

- Dockerfiles (multi-stage), env-specific configs, MongoDB Atlas or replica-set self-host, managed email (SES/SendGrid with SPF/DKIM/DMARC configured) and SMS provider.
- CI/CD: test → build → deploy; DB index migrations run before app start; rollback plan.
- Observability: structured logs with request IDs, metrics (latency, risk-compute time, email/SMS failure rate, Gemini fallback rate), alerts on failures.
- Seed script: demo admin, teachers, 200 synthetic students spanning all risk levels (for demos and load tests).

---

## Phase 13 — Future (do not build now; keep seams ready)

Real ML models (Logistic Regression → Random Forest → XGBoost → ANN) behind a `RiskModel` interface that returns the same result shape, so rule-based and ML can run **side-by-side (shadow mode)** and be compared before switching. Also: parent communication, mobile app, advanced analytics, historical cohort comparison.

---

## Definition of Done (whole project)

- [ ] All phase exit gates passed.
- [ ] Registration verifies email ownership; disposable/fake domains rejected.
- [ ] Forgot password sends email to the verified owner; SMS available as explicit choice and automatic fallback.
- [ ] Risk results are deterministic, explainable, versioned, and stored in MongoDB history.
- [ ] Real-time updates reach dashboards within 2 s of a data change.
- [ ] Scenario tables R1–R15, S1–S15, A1–A23 implemented as automated tests.
- [ ] UI is warm, accessible, animated subtly, and respects reduced-motion.
- [ ] README with setup, env variables, and architecture diagram.

## Suggested Agent Working Order (per phase)

1. Read the phase → 2. write failing tests from the scenario tables → 3. implement → 4. run gate → 5. commit with message `phase-N: <summary>` → 6. note any deviations in `DECISIONS.md` → proceed.
