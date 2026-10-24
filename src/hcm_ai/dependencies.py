from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError

from hcm_ai.config import Settings, get_settings
from hcm_ai.schemas import Role, UserContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_JWT_ALGORITHMS = ["HS256"]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserContext:
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=_JWT_ALGORITHMS,
            options={"require": ["exp", "sub"]},
        )
        return UserContext(
            user_id=int(claims["sub"]),
            role=claims["role"],
            employee_id=claims.get("employee_id"),
        )
    except (jwt.PyJWTError, ValidationError, KeyError, ValueError, TypeError):
        # One generic error for every failure mode: never reveal why a token was rejected.
        raise _unauthorized() from None


def require_roles(*roles: Role) -> Callable[..., UserContext]:
    allowed = frozenset(roles)

    def checker(user: Annotated[UserContext, Depends(get_current_user)]) -> UserContext:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return checker
