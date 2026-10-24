import time

import jwt
import pytest

from hcm_ai.config import Settings

JWT_SECRET = "x" * 40


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hermetic: never read the developer's real .env (it would enable live Gemini/tracing).
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_TRACING_KEY", raising=False)


def make_token(
    sub: object = 1,
    role: str | None = "Employee",
    employee_id: int | None = 7,
    exp_in: int | None = 3600,
    secret: str = JWT_SECRET,
    algorithm: str = "HS256",
) -> str:
    claims: dict[str, object] = {}
    if sub is not None:
        claims["sub"] = str(sub)
    if role is not None:
        claims["role"] = role
    if employee_id is not None:
        claims["employee_id"] = employee_id
    if exp_in is not None:
        claims["exp"] = int(time.time()) + exp_in
    return jwt.encode(claims, secret, algorithm=algorithm)
