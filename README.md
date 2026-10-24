# HCM Lite - M8 AI Assistant

Role-aware AI assistant for HCM Lite: chat with tool calling, dashboard summaries and smart leave
pre-fill. Built with FastAPI, Pydantic v2 and the **OpenAI Agents SDK** pointed at **Groq**
(Gemini as optional fallback). Requirements: `ai_assistant_task_breakdown.md`; rules:
`.specify/memory/constitution.md`.

## How it works

```
Browser --JWT--> FastAPI /ai/*  -> auth -> role check -> rate limit (20/user/hour)
                      |
                      v
              Agents SDK agent (Groq gpt-oss-120b; 15s hard deadline; max 5 turns)
                      | tool calls (identity comes from the JWT, never from the model)
                      v
              services/ai_tools.py  ->  service layer (enforces RBAC, raises 403)
                      |
                      v
              HR services (in-memory mock today; swap for M3-M6 in routers/ai.py:get_services)
```

The LLM never touches the database and never writes business data. Only `ai_logs` is written.

| Endpoint | Roles | What it does |
|---|---|---|
| `POST /ai/chat` | Admin, HR, Employee | Tool-calling Q&A + policy answers |
| `POST /ai/summarize` | Admin, HR | 3-5 bullets from supplied KPI JSON |
| `POST /ai/smart-leave` | Employee | Natural language -> `{type,start,end,reason}` (validated, 1 retry, then `fallback`) |
| `GET /health` | none | Liveness |

Every AI response has `ai_generated: true` and `label: "AI-generated"`. On timeout or provider
failure you get HTTP 200 with `success: false, fallback: true`.

## Setup

```bash
uv sync
cp .env.example .env     # then fill GROQ_API_KEY and JWT_SECRET (>= 32 chars)
uv run uvicorn hcm_ai.main:create_app --factory --reload
```

Keys live only in `.env` (git-ignored). `GEMINI_API_KEY` (fallback model) and
`OPENAI_TRACING_KEY` (trace export) are optional.

### Try it

Production tokens come from M1 (Auth). For local testing mint one (dev only):

```bash
TOKEN=$(uv run python scripts/mint_token.py employee)
curl -s localhost:8000/ai/chat -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message":"How many sick leaves do I have left this year?"}'
```

Tokens must carry `sub` (user id), `role` (`Admin|HR|Employee`), `exp`, and `employee_id` for
Employees (HS256).

Live check of all endpoints against real Groq (needs `.env`): `uv run python scripts/smoke_api.py`.

## Models

Defaults are `openai/gpt-oss-120b` (chat, smart-leave) and `openai/gpt-oss-20b` (summaries), with
`REASONING_EFFORT=low`. Set `CHAT_MODEL`/`FAST_MODEL` in `.env` to change them; if calls fail with
404, list what your key can use with the Groq `/models` endpoint.

## Tracing

Agents SDK tracing is on. Traces are exported to the OpenAI dashboard only when
`OPENAI_TRACING_KEY` is set (an OpenAI platform key; your Groq key is never used for this).
Without it, export is off. Prompts and tool data are excluded from traces
(`trace_include_sensitive_data=False`). `ai_logs` (user, role, endpoint, redacted prompt, response,
tools used, tokens, latency, status) is always written.

## Security controls

| Control | Where |
|---|---|
| Keys only in env, `SecretStr`, never logged | `config.py` |
| JWT: HS256 pinned, `exp`+`sub` required, generic 401 | `dependencies.py` |
| RBAC inside services; tools get identity from run context only | `services/`, `ai_tools.py` |
| Rate limit 20/user/hour (429 + `Retry-After`) | `ratelimit.py` |
| Input caps (chat 1000, leave 500, KPI 8KB, body 32KB), `extra=forbid` | `schemas.py`, `main.py` |
| Prompt-injection stance: user text, KPI data, tool output are data | `agent/prompts.py` |
| 15s deadline, bounded turns, friendly fallback, no provider text leaked | `agent/orchestrator.py` |
| Prompt/response redaction + truncation in `ai_logs` | `agent/ai_logger.py` |
| CORS closed unless `CORS_ORIGINS` set; API docs off unless `ENABLE_DOCS=true` | `main.py` |

## Spec-driven workflow (SpecKit Plus)

Planning documents live in `specs/001-ai-assistant/` (`spec.md`, `plan.md`, `tasks.md`); the
project rules are in `.specify/memory/constitution.md`. Slash commands (`/sp.plan`, `/sp.tasks`,
`/sp.implement`, `/sp.analyze`, ...) are in `.claude/commands/`. On Windows run `specifyplus` with
`PYTHONUTF8=1`. Integration contract for the other modules: `docs/integration.md`.

## Development

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest --cov=hcm_ai          # offline: a scripted fake LLM server, no network
```

## Known limits

- HR data is mock until M3-M6 are wired in (`routers/ai.get_services`).
- Summary numbers are grounded by prompt only; there is no numeric cross-check.
- Rate limiting is in memory (single process); use Redis for multiple workers.
- Body-size cap checks the declared `Content-Length`; also cap at your reverse proxy.
- LLM answer quality (e.g. department name -> id, refusals) is verified only by live runs.
