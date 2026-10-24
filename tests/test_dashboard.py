"""Dashboard endpoints, and the guarantee that dashboard numbers equal the AI tools' numbers."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hcm_ai.config import get_settings
from hcm_ai.main import create_app
from hcm_ai.ratelimit import get_rate_limiter
from hcm_ai.routers import deps
from hcm_ai.schemas import Role, SummarizeRequest, UserContext
from hcm_ai.services import ai_tools as t
from hcm_ai.services.interfaces import AgentDeps
from hcm_ai.services.mock_impl import build_mock_services
from tests.conftest import make_token

TODAY = date(2026, 10, 23)
MONTH = "2026-10"
HR_USER = UserContext(user_id=101, role=Role.HR, employee_id=1)

HR = {"Authorization": f"Bearer {make_token(sub=101, role='HR', employee_id=1)}"}
ADMIN = {"Authorization": f"Bearer {make_token(sub=100, role='Admin', employee_id=None)}"}
BILAL = {"Authorization": f"Bearer {make_token(sub=102, role='Employee', employee_id=2)}"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'd.db'}")
    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
    app = create_app()
    app.dependency_overrides[deps.get_today] = lambda: TODAY
    return TestClient(app)


def tool_deps() -> AgentDeps:
    return AgentDeps(user=HR_USER, services=build_mock_services(TODAY), today=TODAY)


def kpis(client: TestClient, **params: object) -> dict[str, Any]:
    r = client.get("/dashboard", params=params, headers=HR)
    assert r.status_code == 200, r.text
    return r.json()["kpis"]  # type: ignore[no-any-return]


# ---- access control ----


def test_dashboard_is_staff_only(client: TestClient) -> None:
    assert client.get("/dashboard", headers=HR).status_code == 200
    assert client.get("/dashboard", headers=ADMIN).status_code == 200
    assert client.get("/dashboard", headers=BILAL).status_code == 403
    assert client.get("/dashboard").status_code == 401
    assert client.get("/dashboard/departments", headers=BILAL).status_code == 403


def test_my_dashboard_is_employee_only(client: TestClient) -> None:
    assert client.get("/dashboard/me", headers=BILAL).status_code == 200
    assert client.get("/dashboard/me", headers=HR).status_code == 403
    assert client.get("/dashboard/me").status_code == 401


@pytest.mark.parametrize("params", [{"month": "2026-13"}, {"month": "oct"}, {"dept_id": 0}])
def test_bad_filters_are_422(client: TestClient, params: dict[str, object]) -> None:
    assert client.get("/dashboard", params=params, headers=HR).status_code == 422


def test_unknown_department_is_404(client: TestClient) -> None:
    assert client.get("/dashboard", params={"dept_id": 999}, headers=HR).status_code == 404


# ---- content ----


def test_defaults_to_current_month_all_departments(client: TestClient) -> None:
    k = kpis(client)
    assert k["month"] == MONTH and k["department"] == "All departments"
    assert k["headcount"] == 6
    assert len(k["by_department"]) == 3


def test_departments_endpoint_feeds_the_filter(client: TestClient) -> None:
    r = client.get("/dashboard/departments", headers=HR)
    assert [d["name"] for d in r.json()] == ["Engineering", "Sales", "HR"]


def test_future_month_has_no_payroll_and_no_rates(client: TestClient) -> None:
    k = kpis(client, month="2027-01")
    assert "payroll" not in k and "attendance_rate_pct" not in k


def test_employee_dashboard_has_own_numbers(client: TestClient) -> None:
    body = client.get("/dashboard/me", headers=BILAL).json()
    assert body["leave"]["sick"]["remaining"] == 6
    assert body["attendance"]["scope"] == "self"
    assert body["payslip"]["scope"] == "self"


# ---- the main guarantee: dashboard == AI tools ----


def test_dashboard_equals_ai_tools_org_wide(client: TestClient) -> None:
    k = kpis(client, month=MONTH)
    d = tool_deps()
    att = t.tool_attendance_summary(d, MONTH)
    assert k["attendance_rate_pct"] == att["attendance_rate_pct"]
    assert k["late_pct"] == att["late_pct"]
    assert k["absenteeism_pct"] == att["absenteeism_pct"]
    assert k["late_days"] == att["late"] and k["absent_days"] == att["absent"]
    assert k["headcount"] == t.tool_headcount(d, None)["active_total"]
    assert k["top_late_comers"] == [
        {"name": r["name"], "late_days": r["late_days"]} for r in t.tool_late_comers(d, MONTH)
    ]
    pay = t.tool_payroll_summary(d, MONTH)
    assert k["payroll"] == {
        "currency": "PKR",
        "gross": pay["total_gross"],
        "deductions": pay["total_deductions"],
        "net": pay["total_net"],
    }


@pytest.mark.parametrize("dept_id", [1, 2, 3])
def test_dashboard_equals_ai_tools_per_department(client: TestClient, dept_id: int) -> None:
    k = kpis(client, month=MONTH, dept_id=dept_id)
    d = tool_deps()
    att = t.tool_attendance_summary(d, MONTH, dept_id)
    assert k["attendance_rate_pct"] == att.get("attendance_rate_pct")
    assert k["headcount"] == t.tool_headcount(d, dept_id)["active_total"]
    assert k["pending_leave_requests"] == t.tool_leave_summary(d, dept_id)["rows"][0]["pending"]
    assert [r["name"] for r in k["top_late_comers"]] == [
        r["name"] for r in t.tool_late_comers(d, MONTH, dept_id)
    ]
    assert [x["name"] for x in k["by_department"]] == [k["department"]]


def test_dashboard_json_is_acceptable_to_the_summarize_endpoint(client: TestClient) -> None:
    """The Summarize button posts exactly this; it must pass the request validator."""
    for params in ({}, {"dept_id": 1}, {"month": "2027-01"}):
        SummarizeRequest(kpis=kpis(client, **params))
