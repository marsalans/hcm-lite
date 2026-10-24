# Development Tasks

Workflow: Claude Plan Mode per phase -> implement -> present -> wait for approval -> next phase.

## Phase 1: Scaffold
- [x] **T1:** `uv init --package hcm-ai`; `uv add` runtime deps (`fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic`, `pydantic-settings`, `pyjwt`, `openai-agents`, `python-dotenv`) and dev deps (`pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`).
- [x] **T2:** `.gitignore`, `.env.example` (`GROQ_API_KEY`, `GEMINI_API_KEY`, `JWT_SECRET`, `OPENAI_TRACING_KEY` optional, model names, `AI_TIMEOUT_SECONDS=15`, `AI_RATE_LIMIT_PER_HOUR=20`), `config.py` with `SecretStr`.
- [x] **T3:** SQLAlchemy `AILog` model (user_id, role, endpoint, prompt, response, tools_used, tokens_in, tokens_out, response_time_ms, status, created_at) + DB init.

## Phase 2: Security
- [x] **T4:** `dependencies.py`: JWT -> `UserContext`, `require_roles`.
- [x] **T5:** Rate limiter (20/user/hour, 429 + Retry-After).

## Phase 3: Tools
- [x] **T6:** Service `Protocol`s + in-memory mock implementation with real RBAC.
- [x] **T7:** 7 `@function_tool` functions in `services/ai_tools.py` using run-context `UserContext`.

## Phase 4: Agent
- [x] **T8:** Groq client + `OpenAIChatCompletionsModel` + Agents SDK config; tracing setup (OpenAI export if key, local processor always).
- [x] **T9:** Orchestrator: Agent, static policy prompt, `Runner.run` with `max_turns`, 15s `asyncio.timeout`, friendly fallback, `ai_logs` writer.

## Phase 5: Routes
- [x] **T10:** `POST /ai/chat`.
- [x] **T11:** `POST /ai/smart-leave` (Pydantic validation, 1 retry, fallback).
- [x] **T12:** `POST /ai/summarize` (Admin/HR, 3-5 bullets).

## Phase 6: Hardening
- [x] **T13:** Tests: RBAC matrix, rate limit, timeout, retry/fallback, injection, JWT edge cases.
- [x] **T14:** ruff + mypy clean; secrets scan; run the 4 judge scenarios live; README run instructions (`uv run uvicorn ...`).
