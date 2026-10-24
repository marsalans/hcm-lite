from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from hcm_ai.ratelimit import SlidingWindowLimiter, enforce_rate_limit, get_rate_limiter
from hcm_ai.schemas import UserContext
from tests.conftest import make_token


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limit_then_429_with_retry_after() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(20, 3600, clock)
    for _ in range(20):
        limiter.check(1)
    clock.now += 100
    with pytest.raises(HTTPException) as exc:
        limiter.check(1)
    assert exc.value.status_code == 429
    assert exc.value.headers is not None
    assert exc.value.headers["Retry-After"] == "3500"


def test_window_expiry_frees_slots() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(2, 3600, clock)
    limiter.check(1)
    limiter.check(1)
    clock.now += 3600
    limiter.check(1)


def test_users_are_isolated() -> None:
    limiter = SlidingWindowLimiter(1, 3600, FakeClock())
    limiter.check(1)
    limiter.check(2)
    with pytest.raises(HTTPException):
        limiter.check(1)


def test_rejected_requests_do_not_extend_the_window() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(1, 100, clock)
    limiter.check(1)
    for _ in range(5):
        clock.now += 10
        with pytest.raises(HTTPException):
            limiter.check(1)
    clock.now += 50
    limiter.check(1)


def test_route_enforces_limit_after_auth() -> None:
    app = FastAPI()

    @app.post("/ai/x")
    def route(user: Annotated[UserContext, Depends(enforce_rate_limit)]) -> dict[str, int]:
        return {"user_id": user.user_id}

    get_rate_limiter.cache_clear()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {make_token()}"}
    assert [client.post("/ai/x", headers=headers).status_code for _ in range(20)] == [200] * 20
    r = client.post("/ai/x", headers=headers)
    assert r.status_code == 429
    assert "retry-after" in r.headers
    assert client.post("/ai/x").status_code == 401
    get_rate_limiter.cache_clear()
