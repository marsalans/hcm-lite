import logging
import re
from collections.abc import Callable

from sqlalchemy.orm import Session

from hcm_ai.agent.orchestrator import AgentOutcome
from hcm_ai.db import new_session
from hcm_ai.models import AILog
from hcm_ai.schemas import UserContext

log = logging.getLogger(__name__)

_PROMPT_MAX = 500
_RESPONSE_MAX = 2000

_REDACTIONS = (
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"),
    re.compile(r"\b(?:gsk_|AIza|sk-)[\w-]{10,}"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\d{9,}"),
)


def redact(text: str) -> str:
    for pattern in _REDACTIONS:
        text = pattern.sub("[redacted]", text)
    return text


def log_ai_call(
    user: UserContext,
    endpoint: str,
    prompt: str,
    outcome: AgentOutcome,
    session_factory: Callable[[], Session] = new_session,
) -> None:
    """Persist one ai_logs row. Never raises: a logging failure must not break the response."""
    try:
        with session_factory() as session:
            session.add(
                AILog(
                    user_id=user.user_id,
                    role=user.role.value,
                    endpoint=endpoint,
                    prompt=redact(prompt)[:_PROMPT_MAX],
                    response=redact(outcome.text)[:_RESPONSE_MAX],
                    tools_used=list(outcome.tools_used),
                    tokens_in=outcome.tokens_in,
                    tokens_out=outcome.tokens_out,
                    response_time_ms=outcome.elapsed_ms,
                    status=outcome.status,
                )
            )
            session.commit()
    except Exception:
        log.exception("failed to write ai_logs row")
