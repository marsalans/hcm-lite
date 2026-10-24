"""Deterministic in-memory HR data so tools can be built and tested before M1-M7 exist."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from hcm_ai.schemas import Role, UserContext
from hcm_ai.services.errors import NotFound, PermissionDenied
from hcm_ai.services.interfaces import (
    AttendanceSummary,
    DeptCount,
    EmployeeHit,
    HeadcountResult,
    HRServices,
    LateComer,
    LeaveBalance,
    LeaveBucket,
    LeaveRow,
    LeaveSummary,
    PayrollSummary,
)

_STAFF = frozenset({Role.ADMIN, Role.HR})
_QUOTAS = {"annual": 14, "sick": 8, "casual": 10}
_WORKING_DAYS_PER_MONTH = 22
_GROSS_FACTOR = 1.5
_FRIDAY = 4

DEPARTMENTS = {1: "Engineering", 2: "Sales", 3: "HR"}


@dataclass(frozen=True)
class _Emp:
    id: int
    name: str
    dept_id: int
    designation: str
    active: bool
    basic: int
    late_every: int | None = None
    absent_every: int | None = None
    half_every: int | None = None


EMPLOYEES = (
    _Emp(1, "Ayesha Khan", 3, "HR Manager", True, 120_000),
    _Emp(2, "Bilal Ahmed", 1, "Engineer", True, 100_000, late_every=9),
    _Emp(3, "Sara Malik", 1, "Engineer", True, 110_000, half_every=13),
    _Emp(4, "Usman Ali", 1, "Engineer", True, 105_000, late_every=3),
    _Emp(5, "Hina Raza", 2, "Sales Executive", True, 80_000, late_every=5),
    _Emp(6, "Omar Farooq", 2, "Sales Executive", True, 85_000, absent_every=11),
    _Emp(7, "Zainab Noor", 2, "Sales Executive", False, 75_000),
)

# (employee_id, type, status, days)
_LEAVES = (
    (2, "sick", "approved", 2),
    (2, "casual", "approved", 1),
    (2, "annual", "pending", 3),
    (3, "annual", "approved", 4),
    (5, "sick", "approved", 1),
    (4, "casual", "pending", 2),
)


def _require_staff(user: UserContext) -> None:
    if user.role not in _STAFF:
        raise PermissionDenied


def _month_bounds(month: str) -> tuple[date, date]:
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


def _status(e: _Emp, i: int) -> str:
    if e.absent_every and i % e.absent_every == 0:
        return "absent"
    if e.half_every and i % e.half_every == 0:
        return "half_day"
    if e.late_every and i % e.late_every == 0:
        return "late"
    return "on_time"


class _Core:
    """Shared seed data and helpers."""

    def __init__(self, today: date) -> None:
        self.today = today
        self.by_id = {e.id: e for e in EMPLOYEES}
        workdays = [
            d
            for d in (today - timedelta(days=n) for n in range(120, -1, -1))
            if d.weekday() <= _FRIDAY
        ]
        self.records = {
            e.id: [(d, _status(e, i)) for i, d in enumerate(workdays, start=1)] for e in EMPLOYEES
        }

    def active_ids(self, dept_id: int | None = None) -> list[int]:
        if dept_id is not None and dept_id not in DEPARTMENTS:
            raise NotFound("unknown department")
        return [e.id for e in EMPLOYEES if e.active and dept_id in (None, e.dept_id)]

    def counts(self, emp_ids: list[int], start: date, end: date) -> dict[str, int]:
        counts = {"on_time": 0, "late": 0, "half_day": 0, "absent": 0}
        for eid in emp_ids:
            for d, status in self.records[eid]:
                if start <= d <= end:
                    counts[status] += 1
        return counts

    def own_id(self, user: UserContext) -> int:
        if user.employee_id is None or user.employee_id not in self.by_id:
            raise NotFound("no employee profile")
        return user.employee_id


class MockEmployees:
    def __init__(self, core: _Core) -> None:
        self._c = core

    def headcount(self, user: UserContext, dept_id: int | None) -> HeadcountResult:
        _require_staff(user)
        if dept_id is not None and dept_id not in DEPARTMENTS:
            raise NotFound("unknown department")
        depts = [dept_id] if dept_id is not None else list(DEPARTMENTS)
        rows = [
            DeptCount(
                id=d,
                name=DEPARTMENTS[d],
                active=sum(1 for e in EMPLOYEES if e.active and e.dept_id == d),
            )
            for d in depts
        ]
        return HeadcountResult(active_total=sum(r.active for r in rows), departments=rows)

    def search(self, user: UserContext, query: str) -> list[EmployeeHit]:
        q = query.strip().lower()
        staff = user.role in _STAFF
        hits: list[EmployeeHit] = []
        for e in EMPLOYEES:
            if q not in e.name.lower() or (not staff and not e.active):
                continue
            dept = DEPARTMENTS[e.dept_id]
            if staff:
                hits.append(
                    EmployeeHit(
                        name=e.name,
                        department=dept,
                        id=e.id,
                        designation=e.designation,
                        status="active" if e.active else "inactive",
                    )
                )
            else:
                hits.append(EmployeeHit(name=e.name, department=dept))
        return hits


class MockAttendance:
    def __init__(self, core: _Core) -> None:
        self._c = core

    def summary(
        self, user: UserContext, start: date, end: date, dept_id: int | None = None
    ) -> AttendanceSummary:
        if user.role in _STAFF:
            scope = "org" if dept_id is None else "department"
            ids = self._c.active_ids(dept_id)
        else:
            if dept_id is not None:
                raise PermissionDenied
            scope, ids = "self", [self._c.own_id(user)]
        return AttendanceSummary(
            scope=scope, start=start, end=end, **self._c.counts(ids, start, end)
        )

    def late_comers(
        self, user: UserContext, month: str, dept_id: int | None = None
    ) -> list[LateComer]:
        _require_staff(user)
        start, end = _month_bounds(month)
        ranked = [
            LateComer(
                employee_id=eid,
                name=self._c.by_id[eid].name,
                late_days=self._c.counts([eid], start, end)["late"],
            )
            for eid in self._c.active_ids(dept_id)
        ]
        return sorted((r for r in ranked if r.late_days > 0), key=lambda r: (-r.late_days, r.name))


class MockLeave:
    def __init__(self, core: _Core) -> None:
        self._c = core

    def my_balance(self, user: UserContext) -> LeaveBalance:
        own = self._c.own_id(user)
        used = dict.fromkeys(_QUOTAS, 0)
        for eid, kind, status, days in _LEAVES:
            if eid == own and status == "approved":
                used[kind] += days

        def bucket(kind: str) -> LeaveBucket:
            q = _QUOTAS[kind]
            return LeaveBucket(quota=q, used=used[kind], remaining=q - used[kind])

        return LeaveBalance(
            year=self._c.today.year,
            annual=bucket("annual"),
            sick=bucket("sick"),
            casual=bucket("casual"),
        )

    def summary(self, user: UserContext, dept_id: int | None) -> LeaveSummary:
        _require_staff(user)
        if dept_id is not None and dept_id not in DEPARTMENTS:
            raise NotFound("unknown department")
        depts = [dept_id] if dept_id is not None else list(DEPARTMENTS)
        rows: list[LeaveRow] = []
        for d in depts:
            mine = [x for x in _LEAVES if self._c.by_id[x[0]].dept_id == d]
            approved = [x for x in mine if x[2] == "approved"]
            rows.append(
                LeaveRow(
                    dept_id=d,
                    dept=DEPARTMENTS[d],
                    pending=sum(1 for x in mine if x[2] == "pending"),
                    approved=len(approved),
                    approved_days=sum(x[3] for x in approved),
                    approved_days_by_type={
                        kind: sum(x[3] for x in approved if x[1] == kind) for kind in _QUOTAS
                    },
                )
            )
        return LeaveSummary(year=self._c.today.year, rows=rows)


class MockPayroll:
    def __init__(self, core: _Core) -> None:
        self._c = core

    def summary(
        self,
        user: UserContext,
        month: str,
        employee_id: int | None = None,
        dept_id: int | None = None,
    ) -> PayrollSummary:
        if user.role in _STAFF:
            if employee_id is not None:
                if employee_id not in self._c.by_id:
                    raise NotFound("unknown employee")
                scope, ids = "employee", [employee_id]
            else:
                scope = "org" if dept_id is None else "department"
                ids = self._c.active_ids(dept_id)
        else:
            own = self._c.own_id(user)
            if employee_id not in (None, own) or dept_id is not None:
                raise PermissionDenied
            scope, ids = "self", [own]

        start, end = _month_bounds(month)
        if start > self._c.today:
            raise NotFound("no payroll for that month")

        basic = gross = deductions = 0
        for eid in ids:
            emp = self._c.by_id[eid]
            c = self._c.counts([eid], start, end)
            emp_gross = round(emp.basic * _GROSS_FACTOR)
            per_day = emp_gross / _WORKING_DAYS_PER_MONTH
            basic += emp.basic
            gross += emp_gross
            deductions += round(per_day * (c["absent"] + 0.5 * c["half_day"]))
        return PayrollSummary(
            scope=scope,
            month=month,
            employees=len(ids),
            total_basic=basic,
            total_gross=gross,
            total_deductions=deductions,
            total_net=gross - deductions,
        )


def build_mock_services(today: date) -> HRServices:
    core = _Core(today)
    return HRServices(
        employees=MockEmployees(core),
        attendance=MockAttendance(core),
        leave=MockLeave(core),
        payroll=MockPayroll(core),
    )
