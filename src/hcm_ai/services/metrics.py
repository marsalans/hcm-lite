"""KPI formulas shared by the dashboard and the AI tools (one implementation, so they cannot drift).

Brief formula: attendance rate = (present + late + missing_checkout + 0.5 x half_day)
/ (working-day records - on_leave). Demo data has no missing_checkout/on_leave: those terms are 0.
All results are percentages rounded to one decimal, or None when there is nothing to measure.
"""


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator * 100, 1)


def attendance_rate_pct(on_time: int, late: int, half_day: int, absent: int) -> float | None:
    total = on_time + late + half_day + absent
    return _pct(on_time + late + 0.5 * half_day, total)


def late_pct(on_time: int, late: int) -> float | None:
    return _pct(late, on_time + late)


def absenteeism_pct(on_time: int, late: int, half_day: int, absent: int) -> float | None:
    return _pct(absent, on_time + late + half_day + absent)
