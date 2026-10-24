# HCM Lite - M8 AI Assistant

The AI Assistant module of HCM Lite: a **chat panel**, a **dashboard with a Summarize button** and a
**smart leave form**, backed by a FastAPI service that uses the **OpenAI Agents SDK** against **Groq**
(Gemini as optional fallback). Requirements: `ai_assistant_task_breakdown.md`; project rules:
`.specify/memory/constitution.md`.

> Scope: this repo is **M8 only**. Login, employees, attendance, leave and payroll modules (M1-M7) are
> not built here; the assistant and dashboard run on built-in **sample data** behind a service seam
> (see "Done / not done").

## Run it in 3 minutes

```bash
uv sync
cp .env.example .env       # then fill in the values below
uv run uvicorn hcm_ai.main:create_app --factory
```

Required in `.env`:

| Variable | What |
|---|---|
| `AI_API_KEY` (or `GROQ_API_KEY`) | Your Groq API key. **Backend only**: the browser never sees or calls the AI provider. |
| `JWT_SECRET` | Random string, at least 32 characters. Generate: `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DEMO_MODE=true` | Enables the demo sign-in cards (stand-in for M1 login). **Never enable in production.** |

Open <http://localhost:8000>, pick **Admin**, **HR** or **Employee**, and try:

| As | Try | You should see |
|---|---|---|
| HR | Ask "How many active employees are in Engineering?" | 3, same as the dashboard's Engineering filter |
| HR | Ask "Who came late most often this month?" / "What is this month's attendance rate?" | Usman Ali, 6 days / the attendance-rate card value |
| HR / Admin | Press **Summarize** on the dashboard | 3-5 bullets using only the numbers on screen |
| Employee | Ask "How many sick leaves do I have left this year?" | 6 (own balance) |
| Employee | Ask "What is Sara Malik's salary?" | A polite refusal |
| Employee | Type "I need next Monday and Tuesday off for my sister's wedding", press **Fill form with AI** | Casual leave with the right dates, highlighted for review |

First admin: there is no first-run setup in M8; demo mode signs you in as fixed demo users. With
`DEMO_MODE=false`, the UI accepts a JWT from your own login service (see `docs/integration.md`).

## What you get

```
Browser (vanilla JS, no build)  --JWT-->  FastAPI  -> auth -> role check -> rate limit (20/user/hour)
  chat panel / dashboard /                   |
  smart-leave form                           v
                                  Agents SDK agent (Groq gpt-oss-120b; 15 s deadline; max 5 turns)
                                             | tool calls (identity from the JWT, never from the model)
                                             v
                                  services/ai_tools.py -> service layer (enforces RBAC) -> sample data
  Dashboard JSON  <---- same service calls + same formulas (services/metrics.py) ----> AI tool results
```

The model never touches a database and never saves anything. Dashboard numbers and AI answers come
from the **same service calls and formulas**, so they match by construction (tests assert it).

| Endpoint | Roles | What it does |
|---|---|---|
| `GET /` | - | The web UI |
| `POST /ai/chat` | Admin, HR, Employee | Tool-calling Q&A + policy answers |
| `POST /ai/summarize` | Admin, HR | 3-5 bullets from the dashboard KPI JSON |
| `POST /ai/smart-leave` | Employee | Sentence -> `{type,start,end,reason}` (validated, 1 retry, then `fallback`) |
| `GET /dashboard`, `/dashboard/departments` | Admin, HR | KPIs (filters: `month`, `dept_id`) |
| `GET /dashboard/me` | Employee | Own leave balance, attendance, payslip |
| `POST /auth/demo-login` | - | Demo sign-in; **404 unless `DEMO_MODE=true`** |
| `GET /health` | - | Liveness |

Every AI response carries `ai_generated: true` and the label "AI-generated"; on timeout or provider
failure you get HTTP 200 with `success: false, fallback: true`.

KPI formulas (one implementation, `services/metrics.py`): attendance rate = (on-time + late +
0.5 x half-day) / all records; late % = late / (on-time + late); absenteeism = absent / all records.

## Models and tracing

Defaults: `openai/gpt-oss-120b` (chat, smart leave) and `openai/gpt-oss-20b` (summaries) with
`REASONING_EFFORT=low`; change `CHAT_MODEL` / `FAST_MODEL` in `.env`. If calls fail with 404, list
the models your key can use. `GEMINI_API_KEY` (optional) adds a fallback model.

Agents SDK tracing is on. Traces go to the OpenAI dashboard only if `OPENAI_TRACING_KEY` is set
(an OpenAI platform key; the Groq key is never used for this); prompts/tool data are excluded.
`ai_logs` (user, role, endpoint, redacted prompt, response, tools, tokens, latency, status) is
always written.

## Security controls

| Control | Where |
|---|---|
| Keys only in env, `SecretStr`, never logged or echoed in errors | `config.py` |
| JWT: HS256 pinned, `exp`+`sub` required, generic 401 | `dependencies.py` |
| RBAC inside services; tools get identity from run context only | `services/`, `ai_tools.py` |
| Rate limit 20/user/hour (429 + `Retry-After`) | `ratelimit.py` |
| Input caps (chat 1000, leave 500, KPI 8 KB, body 32 KB), `extra=forbid` | `schemas.py`, `main.py` |
| Prompt-injection stance: user text, KPI data, tool output are data | `agent/prompts.py` |
| 15 s deadline, bounded turns, friendly fallback, no provider text leaked | `agent/orchestrator.py` |
| Redacted + truncated `ai_logs` | `agent/ai_logger.py` |
| UI: strict CSP, no `innerHTML`/inline script, AI text rendered as text nodes, tests enforce it | `main.py`, `web/`, `tests/test_web.py` |
| CORS closed unless `CORS_ORIGINS`; API docs off unless `ENABLE_DOCS=true` | `main.py` |

## Development

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest --cov=hcm_ai     # offline: scripted fake LLM; also runs the Node UI tests
node --test "web_tests/*.test.mjs"
uv run python scripts/smoke_api.py   # live check against real Groq (needs .env)
uv run python scripts/policy_eval.py # 19 live Policy Q&A questions (~4 min, paced for token limits)
```

Spec-driven workflow (SpecKit Plus): `specs/001-ai-assistant/` (`spec.md`, `plan.md`, `tasks.md`),
slash commands in `.claude/commands/`. On Windows run `specifyplus` with `PYTHONUTF8=1`.
Integration contract for other modules: `docs/integration.md`.

## Hosting

One process serves API and UI: `uvicorn hcm_ai.main:create_app --factory --host 0.0.0.0 --port $PORT`
on any free host. Set `AI_API_KEY`, `JWT_SECRET` and (for a demo link) `DEMO_MODE=true` in the host's
environment settings, never in the repo. The SQLite `ai_logs` file is ephemeral on most free hosts.

## Done / not done

**Done (M8):** chat with 7 tools and role scoping; dashboard summary; smart leave with validation,
one retry and fallback; policy Q&A over the full Section 3 rules (`agent/policy.py`, checked by `scripts/policy_eval.py`); 15 s timeout + fallback; 20/hour rate limit; `ai_logs`;
AI-generated labels; responsive UI (375 px+, light/dark, loading/empty/error/429 states);
Admin/HR dashboard and Employee home fed by the same services as the AI; tracing.

**Not done (other modules / out of scope):** real login and first-run setup (M1/M2); employee,
attendance, leave and payroll data entry (M3-M6) - the leave form's **Confirm is demo-only and not
saved**; check-in/out, CSV, payslip PDF, audit log and announcements (M9); mobile/camera app.
All data shown is built-in sample data.

## Known limits

- **Provider token limit:** Groq's free tier allows 8,000 tokens/minute for `gpt-oss-120b`; one chat request costs about 1,300 (policy + tool definitions), so roughly 6 questions a minute. On a short 429 the app waits (inside the 15 s budget) and retries once; beyond that users get the friendly fallback. A paid tier or a second provider key (`GEMINI_API_KEY`, which needs its own quota) removes this.
- Summary numbers are grounded by prompt only; there is no numeric cross-check of the bullets.
- Rate limiting is in memory (single process); use Redis for multiple workers.
- Body-size cap checks the declared `Content-Length`; also cap at your reverse proxy.
- Answer quality (department names, refusals) depends on the model; verified live with `scripts/smoke_api.py`.
