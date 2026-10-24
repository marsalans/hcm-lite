from datetime import date

import pytest

from hcm_ai.schemas import Role, UserContext
from hcm_ai.services.errors import NotFound, PermissionDenied
from hcm_ai.services.interfaces import HRServices
from hcm_ai.services.mock_impl import build_mock_services

TODAY = date(2026, 10, 23)
MONTH = "2026-10"

ADMIN = UserContext(user_id=100, role=Role.ADMIN)
HR = UserContext(user_id=101, role=Role.HR, employee_id=1)
BILAL = UserContext(user_id=102, role=Role.EMPLOYEE, employee_id=2)


@pytest.fixture
def svc() -> HRServices:
    return build_mock_services(TODAY)


@pytest.mark.parametrize("user", [ADMIN, HR])
def test_staff_headcount(svc: HRServices, user: UserContext) -> None:
    r = svc.employees.headcount(user, None)
    assert r.active_total == 6  # Zainab is inactive
    eng = svc.employees.headcount(user, 1)
    assert eng.departments[0].active == 3


def test_headcount_unknown_dept(svc: HRServices) -> None:
    with pytest.raises(NotFound):
        svc.employees.headcount(HR, 99)


def test_employee_blocked_from_staff_methods(svc: HRServices) -> None:
    with pytest.raises(PermissionDenied):
        svc.employees.headcount(BILAL, None)
    with pytest.raises(PermissionDenied):
        svc.attendance.late_comers(BILAL, MONTH)
    with pytest.raises(PermissionDenied):
        svc.leave.summary(BILAL, None)


def test_late_comers_ranked(svc: HRServices) -> None:
    rows = svc.attendance.late_comers(HR, MONTH)
    assert rows[0].name == "Usman Ali"
    assert [r.late_days for r in rows] == sorted((r.late_days for r in rows), reverse=True)


def test_attendance_scope(svc: HRServices) -> None:
    start, end = date(2026, 10, 1), TODAY
    org = svc.attendance.summary(HR, start, end)
    own = svc.attendance.summary(BILAL, start, end)
    assert org.scope == "org" and own.scope == "self"
    assert own.on_time + own.late + own.half_day + own.absent < org.on_time + org.late


def test_leave_balance_is_own_and_exact(svc: HRServices) -> None:
    b = svc.leave.my_balance(BILAL)
    assert (b.sick.quota, b.sick.used, b.sick.remaining) == (8, 2, 6)
    assert b.casual.remaining == 9
    assert b.annual.remaining == 14  # pending leave does not count


def test_leave_balance_without_profile(svc: HRServices) -> None:
    with pytest.raises(NotFound):
        svc.leave.my_balance(ADMIN)


def test_payroll_org_and_self(svc: HRServices) -> None:
    org = svc.payroll.summary(HR, MONTH)
    assert org.scope == "org" and org.employees == 6
    assert org.total_gross == round(org.total_basic * 1.5)
    assert org.total_net == org.total_gross - org.total_deductions
    own = svc.payroll.summary(BILAL, MONTH)
    assert own.scope == "self" and own.total_basic == 100_000


def test_employee_cannot_read_colleague_salary(svc: HRServices) -> None:
    with pytest.raises(PermissionDenied):
        svc.payroll.summary(BILAL, MONTH, employee_id=3)
    assert svc.payroll.summary(BILAL, MONTH, employee_id=2).scope == "self"


def test_payroll_future_month(svc: HRServices) -> None:
    with pytest.raises(NotFound):
        svc.payroll.summary(HR, "2027-01")


def test_search_hides_sensitive_fields_from_employees(svc: HRServices) -> None:
    emp_hits = svc.employees.search(BILAL, "sara")
    assert [h.model_dump(exclude_none=True) for h in emp_hits] == [
        {"name": "Sara Malik", "department": "Engineering"}
    ]
    assert svc.employees.search(BILAL, "zainab") == []  # inactive hidden
    staff_hit = svc.employees.search(HR, "zainab")[0]
    assert staff_hit.status == "inactive" and staff_hit.id == 7
    assert "salary" not in staff_hit.model_dump()
