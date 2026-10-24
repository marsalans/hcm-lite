# Prompt for Claude (SpecKit Plus Execution)

**Role:** Staff Python Backend Engineer executing a SpecKit Plus workflow for HCM Lite Module 8 (AI Assistant). Scope: `ai_assistant_task_breakdown.md` only.

**Instructions:**
1.  Use Plan Mode for each phase; present a short plan, implement after approval.
2.  Source files: `.specify/memory/constitution.md`, `spec.md`, `plan.md`, `tasks.md`, `gemini.md`, `ai_assistant_task_breakdown.md`.
3.  Use the **OpenAI Agents SDK** (`openai-agents`) with Groq via `AsyncOpenAI(base_url="https://api.groq.com/openai/v1")` + `OpenAIChatCompletionsModel`. Tracing enabled per the constitution.
4.  `uv` only. FastAPI + Pydantic V2, typed, ruff/mypy clean.
5.  Follow RBAC and security rules in the constitution. Tools call the service layer only; no raw DB queries by the LLM.
6.  Work phase by phase from `tasks.md`; stop for approval after each phase; tick completed tasks.
7.  Keep token use low: concise prompts, compact tool output, read only the files needed.
