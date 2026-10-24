from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from hcm_ai.dependencies import get_current_user, require_roles
from hcm_ai.schemas import Role, UserContext
from tests.conftest import make_token

app = FastAPI()


@app.get("/me")
def me(user: Annotated[UserContext, Depends(get_current_user)]) -> dict[str, object]:
    return {"user_id": user.user_id, "role": user.role, "employee_id": user.employee_id}


@app.get("/staff")
def staff(
    user: Annotated[UserContext, Depends(require_roles(Role.ADMIN, Role.HR))],
) -> dict[str, int]:
    return {"user_id": user.user_id}


client = TestClient(app)


def get(path: str, token: str | None) -> int:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(path, headers=headers).status_code


def test_valid_token_yields_context() -> None:
    r = client.get("/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200
    assert r.json() == {"user_id": 1, "role": "Employee", "employee_id": 7}


def test_admin_without_employee_id_is_ok() -> None:
    assert get("/me", make_token(role="Admin", employee_id=None)) == 200


@pytest.mark.parametrize(
    "token",
    [
        make_token(exp_in=-10),
        make_token(secret="y" * 40),
        make_token(exp_in=None),
        make_token(sub=None),
        make_token(role=None),
        make_token(role="Superuser"),
        make_token(role="Employee", employee_id=None),
        make_token(sub="not-a-number"),
        "garbage",
        jwt.encode({"sub": "1", "role": "Admin", "exp": 9999999999}, "", algorithm="none"),
        None,
    ],
)
def test_bad_tokens_get_401(token: str | None) -> None:
    assert get("/me", token) == 401


def test_401_is_generic() -> None:
    r = client.get("/me", headers={"Authorization": f"Bearer {make_token(exp_in=-10)}"})
    assert r.json() == {"detail": "Invalid or expired token"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_require_roles() -> None:
    assert get("/staff", make_token(role="Employee")) == 403
    assert get("/staff", make_token(role="HR", employee_id=None)) == 200
    assert get("/staff", make_token(role="Admin", employee_id=None)) == 200
    assert get("/staff", None) == 401


def test_non_bearer_scheme_is_401() -> None:
    r = client.get("/me", headers={"Authorization": f"Basic {make_token()}"})
    assert r.status_code == 401


def test_lowercase_role_is_401() -> None:
    assert get("/me", make_token(role="admin", employee_id=None)) == 401
