from sqlalchemy import select
from sqlalchemy.orm import Session

from hcm_ai.db import Base, make_engine
from hcm_ai.models import AILog


def test_ailog_roundtrip() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(
            AILog(
                user_id=1,
                role="Employee",
                endpoint="chat",
                prompt="hi",
                tools_used=["get_my_leave_balance"],
                status="ok",
            )
        )
        s.commit()
        row = s.scalars(select(AILog)).one()
    assert row.tools_used == ["get_my_leave_balance"]
    assert row.created_at is not None
