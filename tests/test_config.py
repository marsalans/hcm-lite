import pytest
from pydantic import ValidationError

from hcm_ai.config import Settings


def test_defaults_and_secret_masking() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.ai_timeout_seconds == 15
    assert s.ai_rate_limit_per_hour == 20
    assert "test-groq-key" not in repr(s)


def test_rejects_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_rejects_empty_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", " ")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_rejected_secret_is_not_echoed_in_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "short-but-secret")
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "short-but-secret" not in str(exc.value)
