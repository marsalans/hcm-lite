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
- [x] **T7:** 7 `@function_tool` functions in `services/ai_tools.py` using run-context `AgentDeps` (user + services).

## Phase 4: Agent
- [x] **T8:** Groq client + `OpenAIChatCompletionsModel` + Agents SDK config; tracing setup (OpenAI export only if `OPENAI_TRACING_KEY`; otherwise off; `ai_logs` data from run hooks).
- [x] **T9:** Orchestrator: Agent, static policy prompt, `Runner.run` with `max_turns`, 15s `asyncio.timeout`, friendly fallback, `ai_logs` writer.

## Phase 5: Routes
- [x] **T10:** `POST /ai/chat`.
- [x] **T11:** `POST /ai/smart-leave` (Pydantic validation, 1 retry, fallback).
- [x] **T12:** `POST /ai/summarize` (Admin/HR, 3-5 bullets).

## Phase 6: Hardening
- [x] **T13:** Tests: RBAC matrix, rate limit, timeout, retry/fallback, injection, JWT edge cases.
- [x] **T14:** ruff + mypy clean; secrets scan; run the 4 judge scenarios live; README run instructions (`uv run uvicorn ...`).

## Phase 7: Integration readiness & polish
- [x] **T15:** Docs sync (constitution, plan, tasks, README) with what was built; adopt SpecKit Plus layout.
- [x] **T16:** Refusal wording for other people's pay / private data (prompt rule + test + live check).
- [x] **T17:** `docs/integration.md` contract + reusable service contract tests for the real M3-M6 services.
- [x] **T18:** Dependency audit (`pip-audit`): no known vulnerabilities; no upgrades needed.
- [x] **T19:** Full verification (ruff, mypy, pytest, coverage, SpecKit prerequisites check, live smoke) and commit.

## Phase 8: Frontend (required) + dashboard
- [x] **T20:** Docs: constitution (frontend rules), spec (F/G/H), plan, tasks; README, integration doc, CLAUDE.md.
- [x] **T21:** `services/metrics.py` with the shared KPI formulas.
- [x] **T22:** Service contract + mock: `dept_id` filters, percentages, leave days by type.
- [x] **T23:** AI tools: optional `dept_id`, rates in results (judge question: attendance rate).
- [x] **T24:** `services/dashboard.py` and `/dashboard*` endpoints (role-scoped).
- [x] **T25:** Demo login (`DEMO_MODE`), `AI_API_KEY` alias.
- [x] **T26:** Security headers/CSP middleware; static UI mount.
- [x] **T27:** UI shell, sign-in, API client, state handling.
- [x] **T28:** Dashboard UI: filters, KPI cards, charts, Summarize.
- [x] **T29:** Employee home + smart-leave form (pre-fill, review, confirm, fallback).
- [x] **T30:** Chat panel (suggestions, loading/429/fallback/error states).
- [x] **T31:** Tests: pytest + `node --test`; UI source lint.
- [x] **T32:** Browser verification (desktop, 375px, dark) with real Groq.
- [x] **T33:** Final checks, README done/not-done, commits.

## Phase 9: Complete Policy Q&A
- [x] **T34:** Docs: spec D, plan, constitution token budget, README.
- [x] **T35:** `agent/policy.py` (full Section 3 + permissions + metrics) wired into the system prompt.
- [x] **T36:** Offline tests: budget, required facts, code/doc agreement, static prefix.
- [x] **T37:** `scripts/policy_eval.py` live eval; iterate wording until all PASS.
- [x] **T38:** Full checks (ruff, mypy, pytest, node, smoke) and local commit.
- [x] **T39:** Wait out short provider 429s once within the deadline (found by the live eval; Groq free tier = 8,000 tokens/min).
