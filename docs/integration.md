# Integrating the AI Assistant (M8) with the HCM Lite modules

For the people building M1-M7 and the frontend. The AI layer is a thin conversational shell:
**all data and all permission checks live in your services**; the model only chooses tools.

## 1. Auth (M1) - token contract

M8 verifies JWTs; M1 issues them. Same `JWT_SECRET` on both sides.

| Claim | Required | Notes |
|---|---|---|
| `sub` | yes | user id as a string of digits |
| `role` | yes | exactly `Admin`, `HR` or `Employee` (case-sensitive) |
| `exp` | yes | expiry (unix seconds); expired = 401 |
| `employee_id` | for `Employee` | integer; Admin/HR may omit it |

Algorithm is pinned to **HS256**. Send `Authorization: Bearer <token>`.

## 2. Services (M3-M6) - what to implement

Protocols are in `src/hcm_ai/services/interfaces.py`. Every method receives the verified
`UserContext` first and must enforce scope itself (raise `PermissionDenied` / `NotFound` from
`services/errors.py`; the tools turn these into a safe `forbidden` / short error for the model).

| Method | Admin / HR | Employee |
|---|---|---|
| `employees.headcount(user, dept_id)` | allowed; unknown dept -> `NotFound` | `PermissionDenied` |
| `employees.search(user, query)` | id, name, department, designation, status (never pay) | name + department only, active people |
| `attendance.summary(user, start, end)` | org-wide (`scope="org"`) | own only (`scope="self"`) |
| `attendance.late_comers(user, "YYYY-MM")` | ranked by late days | `PermissionDenied` |
| `leave.my_balance(user)` | own (needs an employee profile, else `NotFound`) | own |
| `leave.summary(user, dept_id)` | allowed; unknown dept -> `NotFound` | `PermissionDenied` |
| `payroll.summary(user, "YYYY-MM", employee_id=None)` | org totals, or one employee if `employee_id` given | own payslip only; another `employee_id` -> `PermissionDenied`; future month -> `NotFound` |

Business rules the numbers must follow (the model quotes them): office 09:00 with 15 min grace,
half-day under 5h, quotas annual 14 / sick 8 / casual 10 (unpaid unlimited), gross = 1.5x basic.
Counts must equal the dashboard's, since judges compare them.

### Swap in the real services

1. Build an `HRServices(employees=..., attendance=..., leave=..., payroll=...)` from your classes.
2. Return it from `get_services()` in `src/hcm_ai/routers/ai.py` (currently the in-memory mock).
3. Point the `services` fixture in `tests/test_service_contract.py` at your implementation (seed at
   least one Employee with a profile, a second employee, two departments; adjust the constants at
   the top of that file) and run `uv run pytest tests/test_service_contract.py`. All tests must pass
   before the AI layer goes in front of real data.

## 3. Frontend - HTTP contract

All three endpoints are `POST`, JSON, Bearer auth. Every success **and** fallback body carries
`ai_generated: true` and `label: "AI-generated"`: **render the label** next to AI output.

| Endpoint | Roles | Request | Response (`200`) |
|---|---|---|---|
| `/ai/chat` | Admin, HR, Employee | `{"message": str <= 1000}` | `{success, fallback, answer, ai_generated, label}` |
| `/ai/summarize` | Admin, HR | `{"kpis": {...}}` (<= 8KB, depth <= 3, strings <= 100 chars) | `{success, fallback, summary, bullets[3-5], ...}` |
| `/ai/smart-leave` | Employee | `{"text": str <= 500}` | `{success, fallback, data: {type, start, end, reason} \| null, ...}` |

- `type` is one of `annual | sick | casual | unpaid`; dates are `YYYY-MM-DD`.
- **`fallback: true`** (timeout, provider failure, unusable output): show `answer` for chat; for
  summarize hide the panel or show a retry; for smart-leave **open the normal empty leave form**.
  The pre-filled form must always be confirmed by the user - the AI never saves anything.
- Send the dashboard's current filtered KPI JSON to `/ai/summarize`; the model only uses those numbers.

| Status | Meaning | UI handling |
|---|---|---|
| 401 | missing/invalid/expired token | re-login |
| 403 | role not allowed for this endpoint | hide the feature for that role |
| 413 | body over 32KB | shorten input |
| 422 | invalid body (empty, too long, extra fields) | fix the request |
| 429 | 20 AI requests/user/hour used | read `Retry-After` (seconds) and wait |

CORS: add the frontend origin to `CORS_ORIGINS` in `.env` (comma-separated). It is closed by default.

## 4. Operations

- Keys only in `.env` (`GROQ_API_KEY`, `JWT_SECRET`; optional `GEMINI_API_KEY`, `OPENAI_TRACING_KEY`).
- Run: `uv run uvicorn hcm_ai.main:create_app --factory`.
- Every call writes one row to `ai_logs` (redacted prompt, tools used, tokens, latency, status).
- Check live behaviour any time with `uv run python scripts/smoke_api.py`.
