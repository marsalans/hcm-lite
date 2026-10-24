"""Service-layer contracts the AI tools depend on.

The real M3-M6 services implement these; every method receives the verified caller first and is
responsible for RBAC (raise PermissionDenied) - tools never rely on the LLM to enforce scope.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, computed_field

from hcm_ai.schemas import UserContext
from hcm_ai.services import metrics


class _Result(BaseModel):
    model_config = ConfigDict(frozen=True)


class DeptCount(_Result):
    id: int
    name: str
    active: int


class HeadcountResult(_Result):
    active_total: int
    departments: list[DeptCount]


class AttendanceSummary(_Result):
    scope: str
    start: date
    end: date
    on_time: int
    late: int
    half_day: int
    absent: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def attendance_rate_pct(self) -> float | None:
        return metrics.attendance_rate_pct(self.on_time, self.late, self.half_day, self.absent)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def late_pct(self) -> float | None:
        return metrics.late_pct(self.on_time, self.late)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def absenteeism_pct(self) -> float | None:
        return metrics.absenteeism_pct(self.on_time, self.late, self.half_day, self.absent)


class LateComer(_Result):
    employee_id: int
    name: str
    late_days: int


class LeaveBucket(_Result):
    quota: int
    used: int
    remaining: int


class LeaveBalance(_Result):
    year: int
    annual: LeaveBucket
    sick: LeaveBucket
    casual: LeaveBucket


class LeaveRow(_Result):
    dept_id: int
    dept: str
    pending: int
    approved: int
    approved_days: int
    approved_days_by_type: dict[str, int] = {}


class LeaveSummary(_Result):
    year: int
    rows: list[LeaveRow]


class PayrollSummary(_Result):
    scope: str
    month: str
    employees: int
    total_basic: int
    total_gross: int
    total_deductions: int
    total_net: int


class EmployeeHit(_Result):
    name: str
    department: str
    id: int | None = None
    designation: str | None = None
    status: str | None = None


class EmployeeService(Protocol):
    def headcount(self, user: UserContext, dept_id: int | None) -> HeadcountResult: ...
    def search(self, user: UserContext, query: str) -> list[EmployeeHit]: ...


class AttendanceService(Protocol):
    def summary(
        self, user: UserContext, start: date, end: date, dept_id: int | None = None
    ) -> AttendanceSummary: ...
    def late_comers(
        self, user: UserContext, month: str, dept_id: int | None = None
    ) -> list[LateComer]: ...


class LeaveService(Protocol):
    def my_balance(self, user: UserContext) -> LeaveBalance: ...
    def summary(self, user: UserContext, dept_id: int | None) -> LeaveSummary: ...


class PayrollService(Protocol):
    def summary(
        self,
        user: UserContext,
        month: str,
        employee_id: int | None = None,
        dept_id: int | None = None,
    ) -> PayrollSummary: ...


@dataclass(frozen=True)
class HRServices:
    employees: EmployeeService
    attendance: AttendanceService
    leave: LeaveService
    payroll: PayrollService


@dataclass(frozen=True)
class AgentDeps:
    """Run context handed to Runner.run(context=...). Never exposed to the LLM."""

    user: UserContext
    services: HRServices
    today: date = field(default_factory=date.today)
