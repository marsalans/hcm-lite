import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from hcm_ai.agent.ai_logger import log_ai_call, redact
from hcm_ai.agent.orchestrator import AgentOutcome
from hcm_ai.db import Base, make_engine
from hcm_ai.models import AILog
from hcm_ai.schemas import Role, UserContext

USER = UserContext(user_id=5, role=Role.HR, employee_id=1)


@pytest.fixture
def factory() -> sessionmaker[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.mark.parametrize(
    "secret",
    [
        "mail me at jane.doe@example.com",
        "Authorization: Bearer abc.def.ghi",
        "key gsk_abcdefghijklmnop1234",
        "token eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM",
        "cnic 4210112345678",
    ],
)
def test_redact(secret: str) -> None:
    out = redact(secret)
    assert "[redacted]" in out
    for leaked in ("jane.doe", "abc.def.ghi", "gsk_abc", "SflKxw", "4210112345678"):
        assert leaked not in out


def test_row_written_with_truncation_and_redaction(factory: sessionmaker[Session]) -> None:
    outcome = AgentOutcome(
        text="x" * 5000,
        status="ok",
        tools_used=("get_headcount",),
        tokens_in=12,
        tokens_out=3,
        elapsed_ms=420,
    )
    log_ai_call(USER, "chat", "mail a@b.com " + "y" * 900, outcome, session_factory=factory)
    with factory() as s:
        row = s.scalars(select(AILog)).one()
    assert (row.user_id, row.role, row.endpoint, row.status) == (5, "HR", "chat", "ok")
    assert len(row.prompt) == 500 and "a@b.com" not in row.prompt
    assert row.response is not None and len(row.response) == 2000
    assert row.tools_used == ["get_headcount"]
    assert (row.tokens_in, row.tokens_out, row.response_time_ms) == (12, 3, 420)


def test_failure_outcomes_are_logged_too(factory: sessionmaker[Session]) -> None:
    log_ai_call(USER, "chat", "q", AgentOutcome(text="sorry", status="timeout"), factory)
    with factory() as s:
        assert s.scalars(select(AILog)).one().status == "timeout"


def test_logger_failure_is_swallowed() -> None:
    def broken() -> Session:
        raise RuntimeError("db down")

    log_ai_call(USER, "chat", "q", AgentOutcome(text="a", status="ok"), session_factory=broken)
