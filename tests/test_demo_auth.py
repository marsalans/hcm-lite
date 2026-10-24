import pytest
from fastapi.testclient import TestClient

from hcm_ai.config import Settings, get_settings
from hcm_ai.main import create_app
from hcm_ai.ratelimit import get_rate_limiter


def app_client(monkeypatch: pytest.MonkeyPatch, tmp_path: object, demo: bool) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/a.db")
    monkeypatch.setenv("DEMO_MODE", "true" if demo else "false")
    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
    return TestClient(create_app())


def test_demo_login_is_off_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    client = app_client(monkeypatch, tmp_path, demo=False)
    assert client.post("/auth/demo-login", json={"role": "HR"}).status_code == 404
    assert Settings(_env_file=None).demo_mode is False  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("role", "path", "ok"),
    [
        ("Admin", "/dashboard", 200),
        ("HR", "/dashboard", 200),
        ("Employee", "/dashboard", 403),
        ("Employee", "/dashboard/me", 200),
        ("HR", "/dashboard/me", 403),
    ],
)
def test_demo_tokens_work_and_carry_the_right_role(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object, role: str, path: str, ok: int
) -> None:
    client = app_client(monkeypatch, tmp_path, demo=True)
    login = client.post("/auth/demo-login", json={"role": role})
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["role"] == role and body["expires_in"] == 8 * 3600
    r = client.get(path, headers={"Authorization": f"Bearer {body['token']}"})
    assert r.status_code == ok


@pytest.mark.parametrize("payload", [{"role": "Superuser"}, {}, {"role": "HR", "x": 1}])
def test_demo_login_rejects_bad_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object, payload: dict[str, object]
) -> None:
    client = app_client(monkeypatch, tmp_path, demo=True)
    assert client.post("/auth/demo-login", json=payload).status_code == 422


def test_ai_api_key_alias_from_the_brief(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("AI_API_KEY", "alias-key")
    assert Settings(_env_file=None).groq_api_key.get_secret_value() == "alias-key"  # type: ignore[call-arg]
