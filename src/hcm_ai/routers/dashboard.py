from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from hcm_ai.dependencies import require_roles
from hcm_ai.routers.deps import Services, Today
from hcm_ai.schemas import Role, UserContext
from hcm_ai.services.dashboard import (
    DashboardKpis,
    DepartmentOption,
    MyDashboard,
    build_dashboard,
    build_my_dashboard,
    list_departments,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

StaffUser = Annotated[UserContext, Depends(require_roles(Role.ADMIN, Role.HR))]
EmployeeUser = Annotated[UserContext, Depends(require_roles(Role.EMPLOYEE))]
Month = Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
DeptId = Annotated[int | None, Query(ge=1)]


class DashboardResponse(BaseModel):
    kpis: DashboardKpis


def _month(month: str | None, today_iso: str) -> str:
    return month or today_iso[:7]


@router.get("", response_model_exclude_none=True)
def dashboard(
    user: StaffUser, services: Services, today: Today, month: Month = None, dept_id: DeptId = None
) -> DashboardResponse:
    kpis = build_dashboard(services, user, _month(month, today.isoformat()), dept_id, today)
    return DashboardResponse(kpis=kpis)


@router.get("/departments")
def departments(user: StaffUser, services: Services) -> list[DepartmentOption]:
    return list_departments(services, user)


@router.get("/me", response_model_exclude_none=True)
def my_dashboard(
    user: EmployeeUser, services: Services, today: Today, month: Month = None
) -> MyDashboard:
    return build_my_dashboard(services, user, _month(month, today.isoformat()), today)
