import time

import jwt

from hcm_ai.config import Settings
from hcm_ai.schemas import UserContext


def create_token(settings: Settings, user: UserContext, minutes: int) -> str:
    """Issue an HS256 JWT in the shape get_current_user expects (M1 normally does this)."""
    claims: dict[str, object] = {
        "sub": str(user.user_id),
        "role": user.role.value,
        "exp": int(time.time()) + minutes * 60,
    }
    if user.employee_id is not None:
        claims["employee_id"] = user.employee_id
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")
