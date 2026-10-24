# Architectural Blueprint - Gemini 3.1 Pro

**Role:** Lead Systems Architect
**Date:** October 25, 2026 (Hackathon Crunch Time)

> **Revision (Claude review):** Orchestration now uses the OpenAI Agents SDK (`openai-agents`) rather than a hand-written `openai` loop, to get tool-calling, `max_turns` and built-in tracing. See `.specify/memory/constitution.md` for the authoritative rules.

## Strategic Decisions
1.  **Provider Pivot:** Shifted from native Gemini SDK to OpenAI Agent SDK pointing to Groq's API. This fulfills the user's desire to use the `openai` SDK standard while leveraging Groq's blazing-fast inference for rapid tool-calling loops, crucial for beating the 15-second timeout requirement.
2.  **State Management:** Designed the JWT context injection (`UserContext`) so that the Agent cannot accidentally leak data. The underlying Python functions act as the hard boundary.
3.  **Resilience Architecture:** Explicitly mapped a Pydantic validation retry loop for the Smart Leave feature to ensure structured output compliance without endless hallucinations.
4.  **SpecKit Integration:** Generated the exact directory structure and markdown files required to guide Claude Pro through a disciplined, token-efficient implementation phase.
> **Status (Claude):** All six phases implemented and verified offline (114 tests, 96% coverage). Live Groq behaviour still needs a run of `scripts/smoke_api.py` with a real `.env`.
