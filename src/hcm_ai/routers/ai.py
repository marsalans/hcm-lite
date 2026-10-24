import json
import re
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo

from agents import Model
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import ValidationError

from hcm_ai.agent.ai_logger import log_ai_call
from hcm_ai.agent.client import build_models
from hcm_ai.agent.orchestrator import (
    AgentOutcome,
    execute_agent_chat,
    merge_outcomes,
    plain_agent,
    run_agent,
)
from hcm_ai.agent.prompts import SUMMARY_INSTRUCTIONS, smart_leave_instructions
from hcm_ai.config import Settings, get_settings
from hcm_ai.ratelimit import ai_user
from hcm_ai.schemas import (
    ChatRequest,
    ChatResponse,
    Role,
    SmartLeave,
    SmartLeaveRequest,
    SmartLeaveResponse,
    SummarizeRequest,
    SummarizeResponse,
    UserContext,
)
from hcm_ai.services.interfaces import AgentDeps, HRServices
from hcm_ai.services.mock_impl import build_mock_services

router = APIRouter(prefix="/ai", tags=["ai"])

ModelProvider = Callable[[bool], list[Model]]

AnyUser = Annotated[UserContext, Depends(ai_user(Role.ADMIN, Role.HR, Role.EMPLOYEE))]
StaffUser = Annotated[UserContext, Depends(ai_user(Role.ADMIN, Role.HR))]
EmployeeUser = Annotated[UserContext, Depends(ai_user(Role.EMPLOYEE))]

_JSON_MODE = {"response_format": {"type": "json_object"}}
_BULLET_RE = re.compile(r"^\s*[-*•]\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")
_MIN_BULLETS, _MAX_BULLETS = 3, 5
_MIN_BUDGET_SECONDS = 0.5


@lru_cache
def _mock_services(today: date) -> HRServices:
    return build_mock_services(today)


def get_today(settings: Annotated[Settings, Depends(get_settings)]) -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def get_services(today: Annotated[date, Depends(get_today)]) -> HRServices:
    """Swap for the real M3-M6 service bundle when those modules exist."""
    return _mock_services(today)


def get_model_provider(settings: Annotated[Settings, Depends(get_settings)]) -> ModelProvider:
    return lambda fast: build_models(settings, fast=fast)


Services = Annotated[HRServices, Depends(get_services)]
Today = Annotated[date, Depends(get_today)]
Provider = Annotated[ModelProvider, Depends(get_model_provider)]
Config = Annotated[Settings, Depends(get_settings)]


@router.post("/chat")
async def chat(
    body: ChatRequest,
    background: BackgroundTasks,
    user: AnyUser,
    services: Services,
    today: Today,
    provider: Provider,
    settings: Config,
) -> ChatResponse:
    deps = AgentDeps(user=user, services=services, today=today)
    out = await execute_agent_chat(deps, body.message, settings=settings, models=provider(False))
    background.add_task(log_ai_call, user, "chat", body.message, out)
    ok = out.status == "ok"
    return ChatResponse(success=ok, fallback=not ok, answer=out.text)


def _parse_bullets(text: str) -> list[str]:
    found = (m.group(1) for line in text.splitlines() if (m := _BULLET_RE.match(line)))
    return list(found)[:_MAX_BULLETS]


@router.post("/summarize")
async def summarize(
    body: SummarizeRequest,
    background: BackgroundTasks,
    user: StaffUser,
    services: Services,
    today: Today,
    provider: Provider,
    settings: Config,
) -> SummarizeResponse:
    deps = AgentDeps(user=user, services=services, today=today)
    # "<" is escaped so KPI text cannot close the data delimiter.
    kpi_json = json.dumps(body.kpis, separators=(",", ":")).replace("<", "\\u003c")
    prompt = f"<kpis>{kpi_json}</kpis>"
    factory = plain_agent("hcm-summary", SUMMARY_INSTRUCTIONS)

    outcome: AgentOutcome | None = None
    bullets: list[str] = []
    started = time.monotonic()
    for _ in range(2):  # first try + exactly one retry
        remaining = settings.ai_timeout_seconds - (time.monotonic() - started)
        if remaining <= _MIN_BUDGET_SECONDS:
            break
        attempt = await run_agent(
            factory,
            prompt,
            deps,
            "summarize",
            settings=settings,
            models=provider(True),
            timeout_seconds=remaining,
        )
        outcome = merge_outcomes(outcome, attempt)
        if attempt.status != "ok":
            break
        bullets = _parse_bullets(attempt.text)
        if len(bullets) >= _MIN_BULLETS:
            break
        bullets = []

    if outcome is None:
        outcome = AgentOutcome(text="", status="timeout")
    if not bullets:
        if outcome.status == "ok":
            outcome = replace(outcome, status="invalid")
        background.add_task(log_ai_call, user, "summarize", prompt, outcome)
        return SummarizeResponse(success=False, fallback=True)
    summary = "\n".join(f"- {b}" for b in bullets)
    background.add_task(log_ai_call, user, "summarize", prompt, replace(outcome, text=summary))
    return SummarizeResponse(summary=summary, bullets=bullets)


def _parse_leave(text: str) -> SmartLeave:
    return SmartLeave.model_validate_json(_FENCE_RE.sub("", text.strip()))


def _short_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first["loc"]) or "output"
    return f"{where}: {first['msg']}"[:120]


@router.post("/smart-leave")
async def smart_leave(
    body: SmartLeaveRequest,
    background: BackgroundTasks,
    user: EmployeeUser,
    services: Services,
    today: Today,
    provider: Provider,
    settings: Config,
) -> SmartLeaveResponse:
    deps = AgentDeps(user=user, services=services, today=today)
    factory = plain_agent("hcm-smart-leave", smart_leave_instructions(today))

    outcome: AgentOutcome | None = None
    parsed: SmartLeave | None = None
    prompt = body.text
    started = time.monotonic()
    for _ in range(2):  # first try + exactly one retry
        remaining = settings.ai_timeout_seconds - (time.monotonic() - started)
        if remaining <= _MIN_BUDGET_SECONDS:
            break
        attempt = await run_agent(
            factory,
            prompt,
            deps,
            "smart-leave",
            settings=settings,
            models=provider(False),
            timeout_seconds=remaining,
            extra_body=_JSON_MODE,
        )
        outcome = merge_outcomes(outcome, attempt)
        if attempt.status != "ok":
            break
        try:
            parsed = _parse_leave(attempt.text)
            break
        except ValidationError as exc:
            hint = f"Previous reply invalid ({_short_error(exc)}). Return only corrected JSON."
            prompt = f"{body.text}\n\n{hint}"

    if outcome is None:
        outcome = AgentOutcome(text="", status="timeout")
    if parsed is None:
        if outcome.status == "ok":
            outcome = replace(outcome, status="invalid")
        background.add_task(log_ai_call, user, "smart-leave", body.text, outcome)
        return SmartLeaveResponse(success=False, fallback=True)
    background.add_task(
        log_ai_call, user, "smart-leave", body.text, replace(outcome, text=parsed.model_dump_json())
    )
    return SmartLeaveResponse(data=parsed)
