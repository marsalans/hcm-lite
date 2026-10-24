import math
import time
from collections import deque
from collections.abc import Callable
from functools import lru_cache
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, status

from hcm_ai.config import get_settings
from hcm_ai.dependencies import get_current_user
from hcm_ai.schemas import Role, UserContext

_SWEEP_THRESHOLD = 1000


class SlidingWindowLimiter:
    """In-memory per-user sliding window. Swap for Redis if running multiple workers."""

    def __init__(
        self,
        limit: int,
        window_seconds: float = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[int, deque[float]] = {}
        self._lock = Lock()

    def tracked_users(self) -> int:
        with self._lock:
            return len(self._hits)

    def _sweep(self, now: float) -> None:
        """Drop users whose newest hit has left the window (bounds memory)."""
        stale = [u for u, h in self._hits.items() if not h or now - h[-1] >= self._window]
        for user_id in stale:
            del self._hits[user_id]

    def check(self, user_id: int) -> None:
        """Record a hit, or raise 429 with Retry-After if the user is over the limit."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep(now)
            hits = self._hits.setdefault(user_id, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                retry_after = max(1, math.ceil(self._window - (now - hits[0])))
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "AI request limit reached. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)


@lru_cache
def get_rate_limiter() -> SlidingWindowLimiter:
    return SlidingWindowLimiter(get_settings().ai_rate_limit_per_hour)


def ai_user(*roles: Role) -> Callable[..., UserContext]:
    """Authenticate -> role check (403, free) -> rate limit (429). Use on every /ai/* route."""
    allowed = frozenset(roles)

    def dependency(
        user: Annotated[UserContext, Depends(get_current_user)],
        limiter: Annotated[SlidingWindowLimiter, Depends(get_rate_limiter)],
    ) -> UserContext:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        limiter.check(user.user_id)
        return user

    return dependency


def enforce_rate_limit(
    user: Annotated[UserContext, Depends(get_current_user)],
    limiter: Annotated[SlidingWindowLimiter, Depends(get_rate_limiter)],
) -> UserContext:
    """Authenticate, then count the request. Use on every /ai/* route."""
    limiter.check(user.user_id)
    return user
