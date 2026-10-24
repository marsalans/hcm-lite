# Integrating the AI Assistant (M8) with the HCM Lite modules

For anyone connecting real M1-M7 modules. The AI layer is a thin conversational shell:
**all data and all permission checks live in your services**; the model only chooses tools. A
reference UI ships with this repo (`src/hcm_ai/web/`), so you can see everything working on sample data.

## 1. Auth (M1) - token contract

M8 verifies JWTs; M1 issues them. Same `JWT_SECRET` on both sides.

| Claim | Required | Notes |
|---|---|---|
| `sub` | yes | user id as a string of digits |
| `role` | yes | exactly `Admin`, `HR` or `Employee` (case-sensitive) |
| `exp` | yes | expiry (unix seconds); expired = 401 |
| `employee_id` | for `Employee` | integer; Admin/HR may omit it |
| `name` | no | shown in the UI top bar if present |

Algorithm is pinned to **HS256**. Send `Authorization: Bearer <token>`.

The UI signs in with demo cards only when `DEMO_MODE=true` (`POST /auth/demo-login`). With it off, the
sign-in screen takes a pasted JWT; replace that with a redirect to your login page when M1 exists.
**Never enable `DEMO_MODE` in production.**

## 2. Services (M3-M6) - what to implement

Protocols are in `src/hcm_ai/services/interfaces.py`. Every method receives the verified
`UserContext` first and must enforce scope itself (raise `PermissionDenied` / `NotFound` from
`services/errors.py`; tools turn these into a safe `forbidden` / short error for the model, and the
dashboard routes map them to 403 / 404).

| Method | Admin / HR | Employee |
|---|---|---|
| `employees.headcount(user, dept_id)` | allowed; unknown dept -> `NotFound` | `PermissionDenied` |
| `employees.search(user, query)` | id, name, department, designation, status (never pay) | name + department only, active people |
| `attendance.summary(user, start, end, dept_id=None)` | org-wide (`scope="org"`) or one department (`"department"`) | own only (`scope="self"`); `dept_id` -> `PermissionDenied` |
| `attendance.late_comers(user, "YYYY-MM", dept_id=None)` | ranked by late days | `PermissionDenied` |
| `leave.my_balance(user)` | own (needs an employee profile, else `NotFound`) | own |
| `leave.summary(user, dept_id)` | rows with `pending`, `approved_days`, `approved_days_by_type`; unknown dept -> `NotFound` | `PermissionDenied` |
| `payroll.summary(user, "YYYY-MM", employee_id=None, dept_id=None)` | org, department or one employee | own payslip only; another `employee_id` or any `dept_id` -> `PermissionDenied`; future month -> `NotFound` |

`AttendanceSummary` derives `attendance_rate_pct`, `late_pct` and `absenteeism_pct` itself from the
counts using `services/metrics.py`; return the four counts (`on_time`, `late`, `half_day`, `absent`)
and the rates come for free and match the dashboard. If you track `missing_checkout` / `on_leave`,
extend `metrics.py` (brief formula: `(present + late + missing_checkout + 0.5 x half_day) /
(working-day records - on_leave)`).

Business rules the numbers must follow: office 09:00 with 15 min grace, half-day under 5h, quotas
annual 14 / sick 8 / casual 10 (unpaid unlimited), gross = 1.5x basic.

### Swap in the real services

1. Build an `HRServices(employees=..., attendance=..., leave=..., payroll=...)` from your classes.
2. Return it from `get_services()` in `src/hcm_ai/routers/deps.py` (currently the in-memory mock).
3. Point the `services` fixture in `tests/test_service_contract.py` at your implementation (seed at
   least one Employee with a profile, a second employee, two departments; adjust the constants at the
   top of that file) and run `uv run pytest tests/test_service_contract.py`. All tests must pass.
4. `tests/test_dashboard.py` asserts dashboard numbers equal the AI tools' numbers; keep it green.

## 3. Frontend - HTTP contract

All AI endpoints are `POST`, JSON, Bearer auth. Every success **and** fallback body carries
`ai_generated: true` and `label: "AI-generated"`: **render the label** next to AI output.

| Endpoint | Roles | Request | Response (`200`) |
|---|---|---|---|
| `/ai/chat` | Admin, HR, Employee | `{"message": str <= 1000}` | `{success, fallback, answer, ai_generated, label}` |
| `/ai/summarize` | Admin, HR | `{"kpis": {...}}` (<= 8KB, depth <= 4, strings <= 100 chars) | `{success, fallback, summary, bullets[3-5], ...}` |
| `/ai/smart-leave` | Employee | `{"text": str <= 500}` | `{success, fallback, data: {type, start, end, reason} \| null, ...}` |
| `GET /dashboard?month=YYYY-MM&dept_id=` | Admin, HR | - | `{kpis: {...}}`: send `kpis` **unchanged** to `/ai/summarize` |
| `GET /dashboard/departments` | Admin, HR | - | `[{id, name}]` for the filter |
| `GET /dashboard/me` | Employee | - | `{month, leave, attendance, payslip}` |

- `type` is one of `annual | sick | casual | unpaid`; dates are `YYYY-MM-DD`.
- **`fallback: true`** (timeout, provider failure, unusable output): show `answer` for chat; for
  summarize show a retry; for smart-leave **show the normal empty leave form**. The pre-filled form
  must always be confirmed by the user: the AI never saves anything.

| Status | Meaning | UI handling |
|---|---|---|
| 401 | missing/invalid/expired token | back to sign-in |
| 403 | role not allowed | hide the feature for that role |
| 413 | body over 32KB | shorten input |
| 422 | invalid body or filter | fix the request |
| 429 | 20 AI requests/user/hour used | read `Retry-After` (seconds), show a countdown |

CORS is closed by default; add the origin to `CORS_ORIGINS` if the UI is served elsewhere. The bundled
UI is same-origin and sends a strict CSP, so it needs no CORS and loads nothing from a CDN.

## 4. Operations

- Keys only in `.env` (`AI_API_KEY` or `GROQ_API_KEY`, `JWT_SECRET`; optional `GEMINI_API_KEY`, `OPENAI_TRACING_KEY`).
- Run: `uv run uvicorn hcm_ai.main:create_app --factory`.
- Every call writes one row to `ai_logs` (redacted prompt, tools used, tokens, latency, status).
- Live check any time with `uv run python scripts/smoke_api.py`.
