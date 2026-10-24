"""Whole-app tests through create_app(): lifespan, middleware, docs, CORS, error hygiene."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from agents import set_tracing_disabled
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect

import hcm_ai.db as db
from hcm_ai.agent.client import build_models
from hcm_ai.config import Settings, get_settings
from hcm_ai.main import create_app
from hcm_ai.ratelimit import SlidingWindowLimiter, get_rate_limiter
from hcm_ai.routers import ai
from tests.conftest import JWT_SECRET, make_token
from tests.mock_llm import MockLLM, completion

HR = {"Authorization": f"Bearer {make_token(sub=101, role='HR', employee_id=1)}"}


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    set_tracing_disabled(True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
    db._engine = None
    db._session_factory = None


def test_lifespan_creates_table_and_health_is_open() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert db._engine is not None
        assert "ai_logs" in inspect(db._engine).get_table_names()


def test_docs_hidden_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(create_app()) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404


def test_docs_can_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_DOCS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        assert client.get("/openapi.json").status_code == 200


def test_cors_closed_by_default_and_open_for_configured_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = {"Origin": "https://hr.example.com"}
    with TestClient(create_app()) as client:
        assert "access-control-allow-origin" not in client.get("/health", headers=origin).headers
    monkeypatch.setenv("CORS_ORIGINS", "https://hr.example.com, https://b.example.com")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get("/health", headers=origin)
        assert r.headers["access-control-allow-origin"] == "https://hr.example.com"
        evil = client.get("/health", headers={"Origin": "https://evil.example.com"})
        assert "access-control-allow-origin" not in evil.headers


def test_oversized_body_is_413_before_auth_or_llm() -> None:
    with TestClient(create_app()) as client:
        r = client.post("/ai/chat", content="x" * 40_000, headers=HR)
        assert r.status_code == 413


def test_garbage_content_length_is_400() -> None:
    with TestClient(create_app()) as client:
        r = client.post("/ai/chat", content="{}", headers={**HR, "content-length": "abc"})
        assert r.status_code == 400


def test_unexpected_error_returns_generic_body() -> None:
    app = create_app()

    def boom() -> None:
        raise RuntimeError("secret internals: gsk_abcdefghijklmnop")

    app.dependency_overrides[ai.get_services] = boom
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post("/ai/chat", json={"message": "hi"}, headers=HR)
    assert r.status_code == 500
    assert "secret" not in r.text and "gsk_" not in r.text


def test_secrets_never_reach_responses_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    llm = MockLLM(500, 502, 503)
    app = create_app()
    settings = get_settings()
    app.dependency_overrides[ai.get_model_provider] = lambda: (
        lambda fast: build_models(settings, fast=fast, groq_client=llm.client())
    )
    with TestClient(app) as client:
        r = client.post("/ai/chat", json={"message": "hi"}, headers=HR)
    assert r.json()["fallback"] is True
    haystack = r.text + caplog.text
    for secret in ("test-groq-key", JWT_SECRET, "boom"):
        assert secret not in haystack


def test_chat_through_real_app_logs_one_row() -> None:
    llm = MockLLM(completion("hello"))
    app = create_app()
    settings = get_settings()
    app.dependency_overrides[ai.get_model_provider] = lambda: (
        lambda fast: build_models(settings, fast=fast, groq_client=llm.client())
    )
    with TestClient(app) as client:
        r = client.post("/ai/chat", json={"message": "hi"}, headers=HR)
        assert r.json()["answer"] == "hello" and r.json()["ai_generated"] is True


# ---- timezone ----


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz: object = None) -> "_FrozenDatetime":  # type: ignore[override]
        base = datetime(2026, 10, 25, 22, 0, tzinfo=UTC)  # Sunday 22:00 UTC = Monday in Karachi
        return base.astimezone(tz) if tz else base  # type: ignore[return-value,arg-type]


@pytest.mark.parametrize(
    ("tz", "expected"), [("Asia/Karachi", "2026-10-26"), ("UTC", "2026-10-25")]
)
def test_today_uses_configured_timezone(
    monkeypatch: pytest.MonkeyPatch, tz: str, expected: str
) -> None:
    monkeypatch.setattr(ai, "datetime", _FrozenDatetime)
    monkeypatch.setenv("APP_TIMEZONE", tz)
    get_settings.cache_clear()
    assert ai.get_today(get_settings()).isoformat() == expected
    assert ZoneInfo(tz)


def test_unknown_timezone_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_timezone="Mars/Olympus")  # type: ignore[call-arg]


# ---- limiter memory ----


def test_limiter_sweeps_stale_users() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(5, 100, lambda: now[0])
    for uid in range(1500):
        limiter.check(uid)
    assert limiter.tracked_users() == 1500
    now[0] = 500.0
    limiter.check(9999)
    assert limiter.tracked_users() == 1
