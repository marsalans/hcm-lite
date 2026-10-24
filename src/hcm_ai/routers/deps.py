"""Dependencies shared by the AI and dashboard routers (override these in tests)."""

from datetime import date, datetime
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends

from hcm_ai.config import Settings, get_settings
from hcm_ai.services.interfaces import HRServices
from hcm_ai.services.mock_impl import build_mock_services


@lru_cache
def _mock_services(today: date) -> HRServices:
    return build_mock_services(today)


def get_today(settings: Annotated[Settings, Depends(get_settings)]) -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def get_services(today: Annotated[date, Depends(get_today)]) -> HRServices:
    """Swap for the real M3-M6 service bundle when those modules exist."""
    return _mock_services(today)


Services = Annotated[HRServices, Depends(get_services)]
Today = Annotated[date, Depends(get_today)]
