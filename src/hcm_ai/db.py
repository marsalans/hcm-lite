from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from hcm_ai.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **kwargs)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _factory() -> sessionmaker[Session]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = make_engine(get_settings().database_url)
        _session_factory = sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def init_db() -> None:
    from hcm_ai import models  # noqa: F401  (register tables)

    _factory()
    assert _engine is not None  # noqa: S101
    Base.metadata.create_all(_engine)


def new_session() -> Session:
    return _factory()()


def get_db() -> Iterator[Session]:
    with _factory()() as session:
        yield session
