import json
from datetime import date

import pytest
from agents import set_tracing_disabled

from hcm_ai.agent.client import build_models
from hcm_ai.agent.orchestrator import FALLBACK_MESSAGE, execute_agent_chat
from hcm_ai.config import Settings
from hcm_ai.schemas import Role, UserContext
from hcm_ai.services.interfaces import AgentDeps
from hcm_ai.services.mock_impl import build_mock_services
from tests.mock_llm import MockLLM, completion, last_tool_message

TODAY = date(2026, 10, 23)
HR = UserContext(user_id=101, role=Role.HR, employee_id=1)
BILAL = UserContext(user_id=102, role=Role.EMPLOYEE, employee_id=2)


@pytest.fixture(autouse=True)
def _no_tracing() -> None:
    set_tracing_disabled(True)


def settings(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


def deps(user: UserContext) -> AgentDeps:
    return AgentDeps(user=user, services=build_mock_services(TODAY), today=TODAY)


async def test_tool_round_trip_for_hr() -> None:
    llm = MockLLM(
        completion(tool_calls=[("get_headcount", {})], tokens=(100, 10)),
        completion("There are 6 active employees.", tokens=(150, 8)),
    )
    s = settings()
    out = await execute_agent_chat(
        deps(HR),
        "How many active employees?",
        settings=s,
        models=build_models(s, groq_client=llm.client()),
    )
    assert out.status == "ok"
    assert out.text == "There are 6 active employees."
    assert out.tools_used == ("get_headcount",)
    assert (out.tokens_in, out.tokens_out) == (250, 18)
    assert json.loads(last_tool_message(llm))["active_total"] == 6
    system = llm.requests[0]["messages"][0]["content"]
    assert "User role: HR" in system and "2026-10-23" in system
    assert llm.requests[0]["temperature"] == 0


async def test_employee_is_denied_staff_tool_through_the_sdk() -> None:
    llm = MockLLM(
        completion(tool_calls=[("get_headcount", {})]),
        completion("I can't share that."),
    )
    s = settings()
    out = await execute_agent_chat(
        deps(BILAL),
        "How many employees?",
        settings=s,
        models=build_models(s, groq_client=llm.client()),
    )
    assert last_tool_message(llm) == '{"error":"forbidden"}'
    assert out.status == "ok" and out.tools_used == ("get_headcount",)


async def test_employee_own_balance_ignores_model_supplied_identity() -> None:
    llm = MockLLM(
        completion(tool_calls=[("get_my_leave_balance", {"employee_id": 3})]),
        completion("You have 6 sick days left."),
    )
    s = settings()
    await execute_agent_chat(
        deps(BILAL),
        "sick leaves left?",
        settings=s,
        models=build_models(s, groq_client=llm.client()),
    )
    assert json.loads(last_tool_message(llm))["sick"]["remaining"] == 6


async def test_timeout_returns_friendly_message() -> None:
    llm = MockLLM(2.0)
    s = settings(ai_timeout_seconds=0.2)
    out = await execute_agent_chat(
        deps(HR), "hi", settings=s, models=build_models(s, groq_client=llm.client())
    )
    assert out.status == "timeout" and out.text == FALLBACK_MESSAGE
    assert out.elapsed_ms < 1500


async def test_falls_back_to_gemini_when_groq_fails() -> None:
    groq, gemini = MockLLM(500), MockLLM(completion("from gemini"))
    s = settings(gemini_api_key="g")
    out = await execute_agent_chat(
        deps(HR),
        "hi",
        settings=s,
        models=build_models(s, groq_client=groq.client(), gemini_client=gemini.client()),
    )
    assert out.status == "ok" and out.text == "from gemini"
    assert gemini.requests[0]["model"] == s.gemini_model


async def test_both_providers_failing_gives_error_without_leaking() -> None:
    groq, gemini = MockLLM(500), MockLLM(503)
    s = settings(gemini_api_key="g")
    out = await execute_agent_chat(
        deps(HR),
        "hi",
        settings=s,
        models=build_models(s, groq_client=groq.client(), gemini_client=gemini.client()),
    )
    assert out.status == "error" and out.text == FALLBACK_MESSAGE
    assert "boom" not in out.text


async def test_tool_loop_is_bounded_by_max_turns() -> None:
    looping = [completion(tool_calls=[("get_headcount", {})]) for _ in range(10)]
    llm = MockLLM(*looping)
    s = settings(agent_max_turns=2)
    out = await execute_agent_chat(
        deps(HR), "loop", settings=s, models=build_models(s, groq_client=llm.client())
    )
    assert out.status == "error" and len(llm.requests) <= 3


async def test_no_gemini_model_without_key() -> None:
    assert len(build_models(settings())) == 1
    assert len(build_models(settings(gemini_api_key="g"))) == 2
