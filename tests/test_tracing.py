import pytest

from hcm_ai.agent import tracing
from hcm_ai.config import Settings


def settings(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


def test_export_enabled_only_with_tracing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr(tracing, "set_tracing_export_api_key", lambda k: calls.update(key=k))
    monkeypatch.setattr(tracing, "set_trace_processors", lambda p: calls.update(processors=p))

    assert tracing.configure_tracing(settings(openai_tracing_key="sk-trace-123456789")) is True
    assert calls == {"key": "sk-trace-123456789"}


def test_export_disabled_without_key_and_groq_key_unused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr(tracing, "set_tracing_export_api_key", lambda k: calls.update(key=k))
    monkeypatch.setattr(tracing, "set_trace_processors", lambda p: calls.update(processors=p))

    assert tracing.configure_tracing(settings()) is False
    assert calls == {"processors": []}  # Groq key never handed to the exporter


def test_secrets_are_masked_in_repr() -> None:
    s = settings(openai_tracing_key="sk-trace-123456789", gemini_api_key="gem-secret-xyz")
    text = repr(s)
    assert "sk-trace-123456789" not in text and "gem-secret-xyz" not in text
    assert "test-groq-key" not in text
