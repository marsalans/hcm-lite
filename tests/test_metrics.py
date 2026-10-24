from datetime import date

from hcm_ai.schemas import Role, UserContext
from hcm_ai.services import ai_tools as t
from hcm_ai.services import metrics
from hcm_ai.services.interfaces import AgentDeps, AttendanceSummary
from hcm_ai.services.mock_impl import build_mock_services

TODAY = date(2026, 10, 23)
HR = UserContext(user_id=101, role=Role.HR, employee_id=1)
BILAL = UserContext(user_id=102, role=Role.EMPLOYEE, employee_id=2)


def test_attendance_rate_follows_brief_formula() -> None:
    # (present + late + 0.5 * half_day) / (all working-day records)
    assert metrics.attendance_rate_pct(on_time=8, late=1, half_day=2, absent=1) == 83.3
    assert metrics.attendance_rate_pct(10, 0, 0, 0) == 100.0
    assert metrics.attendance_rate_pct(0, 0, 0, 5) == 0.0


def test_late_and_absenteeism_formulas() -> None:
    assert metrics.late_pct(on_time=9, late=1) == 10.0
    assert metrics.absenteeism_pct(on_time=8, late=1, half_day=0, absent=1) == 10.0


def test_nothing_to_measure_is_none_not_zero_or_error() -> None:
    assert metrics.attendance_rate_pct(0, 0, 0, 0) is None
    assert metrics.late_pct(0, 0) is None
    assert metrics.absenteeism_pct(0, 0, 0, 0) is None


def test_summary_model_exposes_the_rates() -> None:
    s = AttendanceSummary(
        scope="org",
        start=date(2026, 10, 1),
        end=date(2026, 10, 31),
        on_time=8,
        late=1,
        half_day=2,
        absent=1,
    )
    dumped = s.model_dump(mode="json")
    assert dumped["attendance_rate_pct"] == 83.3
    assert dumped["late_pct"] == 11.1
    assert dumped["absenteeism_pct"] == 8.3


def test_ai_tool_reports_the_attendance_rate_judges_ask_about() -> None:
    deps = AgentDeps(user=HR, services=build_mock_services(TODAY), today=TODAY)
    result = t.tool_attendance_summary(deps, "this_month")
    assert 0 < result["attendance_rate_pct"] <= 100


def test_employee_cannot_slice_attendance_by_department() -> None:
    deps = AgentDeps(user=BILAL, services=build_mock_services(TODAY), today=TODAY)
    out = t.run_tool(lambda: t.tool_attendance_summary(deps, "this_month", 1))
    assert out == '{"error":"forbidden"}'
