"""Dashboard KPIs, built only from the same service calls the AI tools use.

Because both go through the services (and the formulas in `metrics`), the dashboard and the
assistant's answers match by construction.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict

from hcm_ai.schemas import UserContext
from hcm_ai.services.ai_tools import parse_date_range
from hcm_ai.services.errors import NotFound
from hcm_ai.services.interfaces import (
    AttendanceSummary,
    HRServices,
    LeaveBalance,
    PayrollSummary,
)

_TOP_LATE = 5


class _M(BaseModel):
    model_config = ConfigDict(frozen=True)


class DeptKpi(_M):
    name: str
    headcount: int
    attendance_rate_pct: float | None = None
    absenteeism_pct: float | None = None


class LateKpi(_M):
    name: str
    late_days: int


class PayrollKpi(_M):
    currency: str = "PKR"  # stated so the AI never has to guess a currency
    gross: int
    deductions: int
    net: int


class DashboardKpis(_M):
    """Exactly what the Summarize button sends to /ai/summarize."""

    month: str
    department: str
    headcount: int
    attendance_rate_pct: float | None = None
    late_pct: float | None = None
    absenteeism_pct: float | None = None
    late_days: int
    absent_days: int
    pending_leave_requests: int
    approved_leave_days_year: int
    leave_days_by_type_year: dict[str, int]
    payroll: PayrollKpi | None = None
    by_department: list[DeptKpi]
    top_late_comers: list[LateKpi]


class DepartmentOption(_M):
    id: int
    name: str


class MyDashboard(_M):
    month: str
    leave: LeaveBalance
    attendance: AttendanceSummary
    payslip: PayrollSummary | None = None


def list_departments(services: HRServices, user: UserContext) -> list[DepartmentOption]:
    result = services.employees.headcount(user, None)
    return [DepartmentOption(id=d.id, name=d.name) for d in result.departments]


def build_dashboard(
    services: HRServices, user: UserContext, month: str, dept_id: int | None, today: date
) -> DashboardKpis:
    start, end = parse_date_range(month, today)
    headcount = services.employees.headcount(user, dept_id)
    att = services.attendance.summary(user, start, end, dept_id)
    leave = services.leave.summary(user, dept_id)

    by_type: dict[str, int] = {}
    for row in leave.rows:
        for kind, days in row.approved_days_by_type.items():
            by_type[kind] = by_type.get(kind, 0) + days

    by_department = [
        DeptKpi(
            name=d.name,
            headcount=d.active,
            attendance_rate_pct=a.attendance_rate_pct,
            absenteeism_pct=a.absenteeism_pct,
        )
        for d in headcount.departments
        for a in [services.attendance.summary(user, start, end, d.id)]
    ]
    late = services.attendance.late_comers(user, month, dept_id)[:_TOP_LATE]

    try:
        p = services.payroll.summary(user, month, dept_id=dept_id)
        payroll: PayrollKpi | None = PayrollKpi(
            gross=p.total_gross, deductions=p.total_deductions, net=p.total_net
        )
    except NotFound:  # month with no payroll yet (future)
        payroll = None

    return DashboardKpis(
        month=month,
        department=headcount.departments[0].name if dept_id is not None else "All departments",
        headcount=headcount.active_total,
        attendance_rate_pct=att.attendance_rate_pct,
        late_pct=att.late_pct,
        absenteeism_pct=att.absenteeism_pct,
        late_days=att.late,
        absent_days=att.absent,
        pending_leave_requests=sum(r.pending for r in leave.rows),
        approved_leave_days_year=sum(r.approved_days for r in leave.rows),
        leave_days_by_type_year=by_type,
        payroll=payroll,
        by_department=by_department,
        top_late_comers=[LateKpi(name=r.name, late_days=r.late_days) for r in late],
    )


def build_my_dashboard(
    services: HRServices, user: UserContext, month: str, today: date
) -> MyDashboard:
    start, end = parse_date_range(month, today)
    try:
        payslip: PayrollSummary | None = services.payroll.summary(user, month)
    except NotFound:
        payslip = None
    return MyDashboard(
        month=month,
        leave=services.leave.my_balance(user),
        attendance=services.attendance.summary(user, start, end),
        payslip=payslip,
    )
