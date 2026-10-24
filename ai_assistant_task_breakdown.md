# Task Specification: Part 4 - AI Assistant (M8)

**Goal:** Build a secure, role-aware AI assistant that answers questions based *only* on real system data and company policies, assists with dashboard summarization, and enables smart form filling. 

## 1. Core Implementation Rules & Guardrails
*   **Technology:** Any hosted LLM API with tool-calling capabilities. *Our choice:* OpenAI Agents SDK + Groq (Gemini as optional fallback), with Agents SDK tracing.
*   **Security:** API keys (we use `GROQ_API_KEY` / `GEMINI_API_KEY`; the brief's generic name is `AI_API_KEY`) MUST live in the backend environment. The browser never calls the LLM directly.
*   **Data Integrity (Crucial):** 
    *   The LLM **never** queries the database directly. 
    *   Tools must reuse existing backend services and permission/scope checks (REST API logic).
    *   The AI never saves data on its own (read-only + structured output generation).
*   **UX/Reliability:**
    *   Timeout set to 15 seconds with a friendly fallback message.
    *   Rate limiting: ~20 requests per user per hour.
    *   All AI outputs must carry an "AI-generated" label.
    *   All calls must be logged in an `ai_logs` table/collection.

## 2. Feature Requirements

### A. Conversational Chat (`POST /ai/chat`)
*   **Trigger:** Chat panel in the frontend.
*   **Mechanism:** LLM selects a tool -> Backend executes the tool (respecting JWT user scope) -> LLM formats the response.
*   **Required Tools to Build:**
    1.  `get_headcount`
    2.  `get_attendance_summary`
    3.  `get_late_comers`
    4.  `get_leave_summary`
    5.  `get_my_leave_balance`
    6.  `get_payroll_summary`
    7.  `search_employees`

### B. Dashboard Summary
*   **Users:** Admin, HR.
*   **Trigger:** A "Summarize" button on the dashboard.
*   **Mechanism:** Sends the current JSON of KPI data (based on applied UI filters) to the LLM.
*   **Output:** Returns 3-5 insight bullets using *only* the provided numbers.

### C. Smart Leave Form
*   **Users:** Employee.
*   **Trigger:** Typing a natural language sentence (e.g., "Need next Monday and Tuesday off for a wedding").
*   **Mechanism:** LLM parses the intent and returns a structured JSON payload: `{ "type": string, "start": date, "end": date, "reason": string }`.
*   **Failsafe:** Validate JSON. If it fails, retry once, then gracefully fall back to showing the standard empty leave form. User must manually confirm the pre-filled form.

### D. Policy Q&A
*   **Users:** All roles.
*   **Mechanism:** Inject the business rules (from Section 3 of the brief) into the System Prompt.
*   **Constraint:** The model must ONLY answer from these rules. If asked outside the rules, it must reply that it does not know.

## 3. Evaluation Scenarios (Live Test Preparation)
We must ensure our implementation passes these specific judge tests:
1.  **HR:** "How many active employees are in [department]?" / "Who came late most often this month?" -> *Must perfectly match dashboard numbers.*
2.  **Employee:** "How many sick leaves do I have left this year?" -> *Must return exact own balance.*
3.  **Employee:** "What is [colleague]'s salary?" -> *Must politely refuse due to scope guards.*
4.  **Employee:** "I need next Monday and Tuesday off for my sister's wedding" -> *Must correctly pre-fill the form dates and select 'casual' leave.*