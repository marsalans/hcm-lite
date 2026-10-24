"""Demo sign-in: a stand-in for M1 (Auth). Disabled unless DEMO_MODE=true."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from hcm_ai.config import Settings, get_settings
from hcm_ai.schemas import RequestModel, Role, UserContext
from hcm_ai.tokens import create_token

router = APIRouter(prefix="/auth", tags=["auth"])

_TOKEN_MINUTES = 8 * 60

# role -> (user_id, employee_id, display name); matches the seeded mock data
_DEMO_USERS = {
    Role.ADMIN: (100, None, "Demo Admin"),
    Role.HR: (101, 1, "Ayesha Khan (HR)"),
    Role.EMPLOYEE: (102, 2, "Bilal Ahmed"),
}


class DemoLoginRequest(RequestModel):
    role: Role


class DemoUser(BaseModel):
    user_id: int
    role: Role
    employee_id: int | None
    name: str


class DemoLoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int = _TOKEN_MINUTES * 60
    user: DemoUser


@router.post("/demo-login")
def demo_login(
    body: DemoLoginRequest, settings: Annotated[Settings, Depends(get_settings)]
) -> DemoLoginResponse:
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    user_id, employee_id, name = _DEMO_USERS[body.role]
    ctx = UserContext(user_id=user_id, role=body.role, employee_id=employee_id)
    return DemoLoginResponse(
        token=create_token(settings, ctx, _TOKEN_MINUTES),
        user=DemoUser(user_id=user_id, role=body.role, employee_id=employee_id, name=name),
    )
