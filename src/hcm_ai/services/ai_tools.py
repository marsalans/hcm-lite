"""The 7 LLM tools. Thin wrappers: identity comes from the run context, RBAC from the services."""

import json
import re
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from agents import RunContextWrapper, function_tool

from hcm_ai.services.errors import NotFound, PermissionDenied
from hcm_ai.services.interfaces import AgentDeps

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MAX_RANGE_DAYS = 366
_LATE_TOP_N = 5
_SEARCH_TOP_N = 10
_MAX_QUERY_LEN = 50


class ToolInputError(ValueError):
    """Model supplied an invalid argument; message is safe to show the model."""


def _check_month(month: str) -> str:
    if not _MONTH_RE.match(month):
        raise ToolInputError("month must be YYYY-MM")
    return month


def _month_range(month: str) -> tuple[date, date]:
    start = date(int(month[:4]), int(month[5:7]), 1)
    nxt = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, nxt - timedelta(days=1)


def parse_date_range(value: str, today: date) -> tuple[date, date]:
    v = value.strip().lower()
    if v == "today":
        return today, today
    if v == "this_week":
        return today - timedelta(days=today.weekday()), today
    if v == "this_month":
        return today.replace(day=1), today
    if v == "last_month":
        last = today.replace(day=1) - timedelta(days=1)
        return _month_range(f"{last.year}-{last.month:02d}")
    if _MONTH_RE.match(v):
        return _month_range(v)
    if ".." in v:
        a, _, b = v.partition("..")
        try:
            start, end = date.fromisoformat(a), date.fromisoformat(b)
        except ValueError:
            raise ToolInputError("invalid date_range") from None
        if end < start or (end - start).days > _MAX_RANGE_DAYS:
            raise ToolInputError("invalid date_range")
        return start, end
    raise ToolInputError("date_range: today|this_week|this_month|last_month|YYYY-MM|A..B")


def _check_dept(dept_id: int | None) -> int | None:
    if dept_id is not None and dept_id < 1:
        raise ToolInputError("dept_id must be positive")
    return dept_id


def _dump(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), default=str)


def _model(obj: Any) -> Any:
    return obj.model_dump(mode="json", exclude_none=True)


def run_tool(fn: Callable[[], Any]) -> str:
    """Execute a tool body; turn expected failures into short, leak-free error JSON."""
    try:
        return _dump(fn())
    except PermissionDenied:
        return '{"error":"forbidden"}'
    except (NotFound, ToolInputError) as e:
        return _dump({"error": str(e)})


# ---- pure tool bodies (testable without the SDK) ----


def tool_headcount(deps: AgentDeps, dept_id: int | None) -> Any:
    return _model(deps.services.employees.headcount(deps.user, _check_dept(dept_id)))


def tool_attendance_summary(deps: AgentDeps, date_range: str) -> Any:
    start, end = parse_date_range(date_range, deps.today)
    return _model(deps.services.attendance.summary(deps.user, start, end))


def tool_late_comers(deps: AgentDeps, month: str) -> Any:
    rows = deps.services.attendance.late_comers(deps.user, _check_month(month))
    return [_model(r) for r in rows[:_LATE_TOP_N]]


def tool_leave_summary(deps: AgentDeps, dept_id: int | None) -> Any:
    return _model(deps.services.leave.summary(deps.user, _check_dept(dept_id)))


def tool_my_leave_balance(deps: AgentDeps) -> Any:
    return _model(deps.services.leave.my_balance(deps.user))


def tool_payroll_summary(deps: AgentDeps, month: str) -> Any:
    return _model(deps.services.payroll.summary(deps.user, _check_month(month)))


def tool_search_employees(deps: AgentDeps, query: str) -> Any:
    q = query.strip()
    if not 1 <= len(q) <= _MAX_QUERY_LEN:
        raise ToolInputError("query must be 1-50 chars")
    return [_model(h) for h in deps.services.employees.search(deps.user, q)[:_SEARCH_TOP_N]]


# ---- SDK tools (docstrings become tool descriptions: keep terse) ----


@function_tool
def get_headcount(ctx: RunContextWrapper[AgentDeps], dept_id: int | None = None) -> str:
    """Active employee counts per department with ids. Omit dept_id for all."""
    return run_tool(lambda: tool_headcount(ctx.context, dept_id))


@function_tool
def get_attendance_summary(ctx: RunContextWrapper[AgentDeps], date_range: str) -> str:
    """Attendance counts. date_range: today|this_week|this_month|last_month|YYYY-MM|A..B."""
    return run_tool(lambda: tool_attendance_summary(ctx.context, date_range))


@function_tool
def get_late_comers(ctx: RunContextWrapper[AgentDeps], month: str) -> str:
    """Top late employees for month (YYYY-MM)."""
    return run_tool(lambda: tool_late_comers(ctx.context, month))


@function_tool
def get_leave_summary(ctx: RunContextWrapper[AgentDeps], dept_id: int | None = None) -> str:
    """Leave requests/days per department with ids. Omit dept_id for all."""
    return run_tool(lambda: tool_leave_summary(ctx.context, dept_id))


# strict_mode=False: Groq rejects the strict schema of a no-argument tool (empty "required").
@function_tool(strict_mode=False)
def get_my_leave_balance(ctx: RunContextWrapper[AgentDeps]) -> str:
    """The caller's own leave quota, used and remaining."""
    return run_tool(lambda: tool_my_leave_balance(ctx.context))


@function_tool
def get_payroll_summary(ctx: RunContextWrapper[AgentDeps], month: str) -> str:
    """Payroll totals for month (YYYY-MM). Employees only get their own."""
    return run_tool(lambda: tool_payroll_summary(ctx.context, month))


@function_tool
def search_employees(ctx: RunContextWrapper[AgentDeps], query: str) -> str:
    """Find employees by name."""
    return run_tool(lambda: tool_search_employees(ctx.context, query))


ALL_TOOLS = [
    get_headcount,
    get_attendance_summary,
    get_late_comers,
    get_leave_summary,
    get_my_leave_balance,
    get_payroll_summary,
    search_employees,
]
