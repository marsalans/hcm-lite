import json
from datetime import date

import pytest

from hcm_ai.schemas import Role, UserContext
from hcm_ai.services import ai_tools as t
from hcm_ai.services.interfaces import AgentDeps
from hcm_ai.services.mock_impl import build_mock_services

TODAY = date(2026, 10, 23)

HR = UserContext(user_id=101, role=Role.HR, employee_id=1)
BILAL = UserContext(user_id=102, role=Role.EMPLOYEE, employee_id=2)


def deps(user: UserContext) -> AgentDeps:
    return AgentDeps(user=user, services=build_mock_services(TODAY), today=TODAY)


def call(fn: object, user: UserContext, *args: object) -> dict | list:  # type: ignore[type-arg]
    return json.loads(t.run_tool(lambda: fn(deps(user), *args)))  # type: ignore[operator]


def test_seven_tools_with_expected_names() -> None:
    assert {x.name for x in t.ALL_TOOLS} == {
        "get_headcount",
        "get_attendance_summary",
        "get_late_comers",
        "get_leave_summary",
        "get_my_leave_balance",
        "get_payroll_summary",
        "search_employees",
    }


def test_tool_schemas_expose_no_identity_params() -> None:
    forbidden = {"user", "user_id", "employee_id", "role", "ctx", "context"}
    for tool in t.ALL_TOOLS:
        props = set(tool.params_json_schema.get("properties", {}))
        assert not props & forbidden, tool.name
    assert t.get_my_leave_balance.params_json_schema.get("properties", {}) == {}


def test_hr_headcount_matches_service() -> None:
    r = call(t.tool_headcount, HR, None)
    assert r["active_total"] == 6  # type: ignore[call-overload]


@pytest.mark.parametrize(
    ("fn", "args"),
    [
        (t.tool_headcount, (None,)),
        (t.tool_late_comers, ("2026-10",)),
        (t.tool_leave_summary, (None,)),
    ],
)
def test_employee_gets_forbidden_on_staff_tools(fn: object, args: tuple[object, ...]) -> None:
    assert call(fn, BILAL, *args) == {"error": "forbidden"}


def test_employee_own_balance() -> None:
    r = call(t.tool_my_leave_balance, BILAL)
    assert r["sick"]["remaining"] == 6  # type: ignore[call-overload]


def test_employee_payroll_is_own_only() -> None:
    r = call(t.tool_payroll_summary, BILAL, "2026-10")
    assert r["scope"] == "self"  # type: ignore[call-overload]


def test_late_comers_capped_and_ranked() -> None:
    r = call(t.tool_late_comers, HR, "2026-10")
    assert len(r) <= 5 and r[0]["name"] == "Usman Ali"  # type: ignore[index]


def test_search_employee_view_has_no_sensitive_fields() -> None:
    r = call(t.tool_search_employees, BILAL, "a")
    assert r and all(set(h) == {"name", "department"} for h in r)  # type: ignore[union-attr]


@pytest.mark.parametrize("bad", ["2026-13", "oct", "2026-1", "'; DROP TABLE x;--", ""])
def test_bad_month_rejected(bad: str) -> None:
    assert "error" in call(t.tool_late_comers, HR, bad)  # type: ignore[operator]


@pytest.mark.parametrize("bad", ["", "x" * 51])
def test_bad_query_rejected(bad: str) -> None:
    assert "error" in call(t.tool_search_employees, HR, bad)  # type: ignore[operator]


def test_date_range_parsing() -> None:
    assert t.parse_date_range("today", TODAY) == (TODAY, TODAY)
    assert t.parse_date_range("this_week", TODAY) == (date(2026, 10, 19), TODAY)
    assert t.parse_date_range("this_month", TODAY) == (date(2026, 10, 1), TODAY)
    assert t.parse_date_range("last_month", TODAY) == (date(2026, 9, 1), date(2026, 9, 30))
    assert t.parse_date_range("2026-12", TODAY) == (date(2026, 12, 1), date(2026, 12, 31))
    assert t.parse_date_range("2026-10-01..2026-10-05", TODAY) == (
        date(2026, 10, 1),
        date(2026, 10, 5),
    )
    for bad in ["yesterday", "2026-10-05..2026-10-01", "2020-01-01..2026-01-01", "a..b"]:
        with pytest.raises(t.ToolInputError):
            t.parse_date_range(bad, TODAY)


def test_unexpected_errors_are_not_swallowed() -> None:
    def boom() -> None:
        raise RuntimeError("secret internals")

    with pytest.raises(RuntimeError):
        t.run_tool(boom)


def test_tool_schemas_are_accepted_by_groq_rules() -> None:
    # Groq 400s on "required" without non-empty "properties" (found in a live run).
    for tool in t.ALL_TOOLS:
        schema = tool.params_json_schema
        if "required" in schema:
            assert schema.get("properties"), tool.name
