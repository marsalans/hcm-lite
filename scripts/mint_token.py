"""DEV ONLY: mint a short-lived JWT for manual testing. Production tokens come from M1 (Auth).

Usage: uv run python scripts/mint_token.py hr
       uv run python scripts/mint_token.py employee --user-id 102 --employee-id 2
"""

import argparse
import time

import jwt

from hcm_ai.config import get_settings
from hcm_ai.schemas import Role

_DEFAULTS = {
    Role.ADMIN: (100, None),
    Role.HR: (101, 1),
    Role.EMPLOYEE: (102, 2),
}
_MAX_MINUTES = 1440


def mint(role: Role, user_id: int, employee_id: int | None, minutes: int) -> str:
    claims: dict[str, object] = {
        "sub": str(user_id),
        "role": role.value,
        "exp": int(time.time()) + minutes * 60,
    }
    if employee_id is not None:
        claims["employee_id"] = employee_id
    return jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=[r.value.lower() for r in Role])
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--employee-id", type=int)
    parser.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()

    role = next(r for r in Role if r.value.lower() == args.role)
    default_user, default_emp = _DEFAULTS[role]
    minutes = max(1, min(args.minutes, _MAX_MINUTES))
    print(mint(role, args.user_id or default_user, args.employee_id or default_emp, minutes))


if __name__ == "__main__":
    main()
