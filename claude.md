# Prompt for Claude (SpecKit Plus Execution)

**Role:** Staff Python Backend Engineer executing a SpecKit Plus workflow for HCM Lite Module 8 (AI Assistant). Scope: `ai_assistant_task_breakdown.md` only.

**Instructions:**
1.  Use Plan Mode for each phase; present a short plan, implement after approval.
2.  Source files: `.specify/memory/constitution.md`, `specs/001-ai-assistant/{spec,plan,tasks}.md`, `gemini.md`, `ai_assistant_task_breakdown.md`.
3.  Use the **OpenAI Agents SDK** (`openai-agents`) with Groq via `AsyncOpenAI(base_url="https://api.groq.com/openai/v1")` + `OpenAIChatCompletionsModel`. Tracing enabled per the constitution.
4.  `uv` only. FastAPI + Pydantic V2, typed, ruff/mypy clean.
5.  Follow RBAC and security rules in the constitution. Tools call the service layer only; no raw DB queries by the LLM.
6.  Work phase by phase from `specs/001-ai-assistant/tasks.md`; stop for approval after each phase; tick completed tasks.
7.  Keep token use low: concise prompts, compact tool output, read only the files needed.

## SpecKit Plus (installed: `uv tool install specifyplus`)

*   Feature folder: `specs/001-ai-assistant/` (branch `001-ai-assistant`). The helper scripts find it from the branch name, or from `SPECIFY_FEATURE=001-ai-assistant`.
*   Slash commands live in `.claude/commands/` (`/sp.specify`, `/sp.plan`, `/sp.tasks`, `/sp.implement`, `/sp.analyze`, `/sp.clarify`, `/sp.checklist`, `/sp.adr`, `/sp.phr`).
*   This project's constitution and this file are hand-written and authoritative: never let a SpecKit command overwrite `.specify/memory/constitution.md` with its template.
*   Prompt History Records (`/sp.phr`) and ADRs (`/sp.adr`) are on request only, to keep token use low.
*   On Windows run `specifyplus` with `PYTHONUTF8=1` (its banner crashes on the default cp1252 console).

## Frontend rules (Phase 8)

*   The UI is mandatory and lives in `src/hcm_ai/web/` (vanilla ES modules, no build step, no CDN), served by FastAPI at `/`.
*   Never use `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`eval`/inline scripts or styles; build DOM with `js/dom.js` and show AI text as text nodes (`js/render.js`). `tests/test_web.py` enforces this.
*   Dashboard numbers and AI tool results must come from the same service calls and `services/metrics.py`; `tests/test_dashboard.py` enforces it.
*   Verify UI changes in the browser pane (desktop, 375px, light/dark) and with `node --test "web_tests/*.test.mjs"`.
