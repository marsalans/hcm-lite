"""Contract tests every HRServices implementation must pass.

Today `services` builds the in-memory mock. When M3-M6 exist, point the fixture at the real
implementation (seeded with at least: one Employee user with a profile, a second employee,
two departments) and these same tests prove it enforces the RBAC the AI tools rely on.
See docs/integration.md.
"""

from datetime import date

import pytest

from hcm_ai.schemas import Role, UserContext
from hcm_ai.services.errors import NotFound, PermissionDenied
from hcm_ai.services.interfaces import HRServices
from hcm_ai.services.mock_impl import build_mock_services

# Seed facts the fixture data must satisfy (override for a real implementation).
EMPLOYEE_ID = 2
OTHER_EMPLOYEE_ID = 3
UNKNOWN_DEPT_ID = 99_999
MONTH = "2026-10"
FUTURE_MONTH = "2999-01"
SALARY_FIELDS = {"salary", "basic", "gross", "net", "pay"}

ADMIN = UserContext(user_id=1, role=Role.ADMIN)
HR = UserContext(user_id=2, role=Role.HR, employee_id=1)
EMPLOYEE = UserContext(user_id=3, role=Role.EMPLOYEE, employee_id=EMPLOYEE_ID)


@pytest.fixture
def services() -> HRServices:
    return build_mock_services(date(2026, 10, 23))


# ---- staff-only data ----


def test_employee_denied_staff_only_methods(services: HRServices) -> None:
    with pytest.raises(PermissionDenied):
        services.employees.headcount(EMPLOYEE, None)
    with pytest.raises(PermissionDenied):
        services.attendance.late_comers(EMPLOYEE, MONTH)
    with pytest.raises(PermissionDenied):
        services.leave.summary(EMPLOYEE, None)


@pytest.mark.parametrize("staff", [ADMIN, HR])
def test_staff_allowed_staff_methods(services: HRServices, staff: UserContext) -> None:
    assert services.employees.headcount(staff, None).active_total >= 0
    assert isinstance(services.attendance.late_comers(staff, MONTH), list)
    assert services.leave.summary(staff, None).rows is not None


@pytest.mark.parametrize("staff", [ADMIN, HR])
def test_unknown_department_is_not_found(services: HRServices, staff: UserContext) -> None:
    with pytest.raises(NotFound):
        services.employees.headcount(staff, UNKNOWN_DEPT_ID)
    with pytest.raises(NotFound):
        services.leave.summary(staff, UNKNOWN_DEPT_ID)


# ---- own-data scoping ----


def test_employee_attendance_is_self_scoped(services: HRServices) -> None:
    result = services.attendance.summary(EMPLOYEE, date(2026, 10, 1), date(2026, 10, 23))
    assert result.scope == "self"


def test_staff_attendance_is_org_scoped(services: HRServices) -> None:
    result = services.attendance.summary(HR, date(2026, 10, 1), date(2026, 10, 23))
    assert result.scope == "org"


def test_employee_payroll_is_self_scoped(services: HRServices) -> None:
    assert services.payroll.summary(EMPLOYEE, MONTH).scope == "self"
    assert services.payroll.summary(EMPLOYEE, MONTH, employee_id=EMPLOYEE_ID).scope == "self"


def test_employee_cannot_read_a_colleagues_payroll(services: HRServices) -> None:
    with pytest.raises(PermissionDenied):
        services.payroll.summary(EMPLOYEE, MONTH, employee_id=OTHER_EMPLOYEE_ID)


def test_staff_payroll_is_org_scoped(services: HRServices) -> None:
    assert services.payroll.summary(HR, MONTH).scope == "org"


def test_payroll_for_a_future_month_is_not_found(services: HRServices) -> None:
    with pytest.raises(NotFound):
        services.payroll.summary(HR, FUTURE_MONTH)


# ---- leave balance ----


def test_employee_balance_has_the_three_quota_buckets(services: HRServices) -> None:
    b = services.leave.my_balance(EMPLOYEE)
    for bucket in (b.annual, b.sick, b.casual):
        assert bucket.quota - bucket.used == bucket.remaining


def test_user_without_employee_profile_has_no_balance(services: HRServices) -> None:
    with pytest.raises(NotFound):
        services.leave.my_balance(ADMIN)


# ---- directory search ----


def test_employee_search_exposes_only_name_and_department(services: HRServices) -> None:
    hits = services.employees.search(EMPLOYEE, "a")
    assert hits
    for hit in hits:
        assert set(hit.model_dump(exclude_none=True)) == {"name", "department"}


@pytest.mark.parametrize("staff", [ADMIN, HR])
def test_search_never_returns_pay_fields(services: HRServices, staff: UserContext) -> None:
    for hit in services.employees.search(staff, "a"):
        assert not SALARY_FIELDS & set(hit.model_dump())
