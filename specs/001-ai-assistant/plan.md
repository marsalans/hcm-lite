# Architecture & Implementation Plan

Layout (`src/hcm_ai/`): `config.py`, `main.py`, `dependencies.py`, `db.py`, `models.py`, `schemas.py`, `ratelimit.py`, `services/{interfaces.py,mock_impl.py,ai_tools.py}`, `agent/{client.py,prompts.py,orchestrator.py,tracing.py}`, `routers/ai.py`; tests in `tests/`.

## Phase 1: Environment & Scaffold (uv + SpecKit Plus)
1.  `uv init --package hcm-ai`, Python 3.12, `uv add fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings pyjwt openai-agents python-dotenv`; `uv add --dev pytest pytest-asyncio httpx ruff mypy`. Commit `uv.lock`.
2.  `.gitignore` (`.env`, `*.db`, `.venv`), `.env.example` (placeholders only), `config.py` using `pydantic-settings` + `SecretStr`.
3.  SpecKit Plus: keep `.specify/memory/constitution.md` and `specs/001-ai-assistant/{spec,plan,tasks}.md` as the working set; tick tasks as completed.
4.  SQLite (`sqlalchemy` 2.0 style) and `AILog` model.

## Phase 2: Security & Context
1.  `dependencies.py`: `get_current_user` (OAuth2PasswordBearer-style Bearer, `jwt.decode` with `algorithms=["HS256"]`, required `exp`) -> `UserContext`.
2.  `require_roles(...)` dependency for role-gated routes.
3.  `ratelimit.py`: 20/user/hour sliding window (in-memory deque per user; Redis-ready interface); shared dependency on all `/ai/*`.

## Phase 3: Tooling Layer
1.  `services/interfaces.py`: `Protocol`s for the HR services the tools need (headcount, attendance, leave, payroll, employees). `mock_impl.py` implements them with in-memory data so M1-M7 can swap in later without touching tools.
2.  RBAC lives in the service functions (raise `PermissionDenied` -> mapped to 403/`forbidden`).
3.  `ai_tools.py`: 7 `@function_tool` functions taking `RunContextWrapper[UserContext]`; Pydantic-validated args (month regex, `max_length`); compact JSON output, capped rows.

## Phase 4: Agent Orchestration (Agents SDK + Groq)
1.  `agent/client.py`: `AsyncOpenAI(base_url=GROQ, api_key=..., timeout=12, max_retries=1)`; `OpenAIChatCompletionsModel`; `set_default_openai_api("chat_completions")`; `set_default_openai_client(client, use_for_tracing=False)`.
2.  `agent/tracing.py`: enable tracing; if `OPENAI_TRACING_KEY` set -> `set_tracing_export_api_key`; always add local `TracingProcessor` collecting tools used / tokens for `ai_logs`; sensitive data off.
3.  `orchestrator.py`: `Agent[UserContext]` with static policy prompt and the 7 tools; `Runner.run(agent, input, context=ctx, max_turns=5, run_config=RunConfig(workflow_name="hcm-ai", trace_include_sensitive_data=False, trace_metadata=...))` under `asyncio.timeout(15)`; optional Gemini fallback model on provider error; friendly fallback on timeout.
4.  `log_ai_call` helper writes `ai_logs` in a `finally` (redact emails/long digit strings from prompt, truncate).

## Phase 5: API Routes
1.  `POST /ai/chat` (Admin/HR/Employee).
2.  `POST /ai/summarize` (Admin/HR): single Agent run, no tools, bullet-count check.
3.  `POST /ai/smart-leave` (Employee): `output_type`/JSON validation with 1 retry then fallback.
4.  All responses carry `ai_generated`/`label`.

## Phase 6: Hardening & Verification
1.  pytest: RBAC matrix per tool, rate limit, timeout fallback (mock provider), smart-leave retry/fallback, injection refusals, JWT edge cases (expired, wrong alg, missing claims).
2.  `ruff`, `mypy`, a secrets scan, and manual run of the 4 judge scenarios against live Groq.

## Implementation notes (as built)
- Run context is `AgentDeps(user, services, today)`; tools read identity only from it.
- `ai_logs` tool names/tokens come from a `RunHooks` collector (works on timeouts); tracing only feeds the OpenAI dashboard.
- Models: tool chat and smart-leave use `CHAT_MODEL`; summarize uses `FAST_MODEL`; optional Gemini fallback.
- "Today" is computed in `APP_TIMEZONE` (default Asia/Karachi) so "next Monday" is right on UTC hosts.
- App is a factory: `uvicorn hcm_ai.main:create_app --factory`.
- HR data is an in-memory mock behind `routers/ai.get_services`; replace with M3-M6 services.
