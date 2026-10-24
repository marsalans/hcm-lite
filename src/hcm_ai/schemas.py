import json
from datetime import date
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Role(StrEnum):
    ADMIN = "Admin"
    HR = "HR"
    EMPLOYEE = "Employee"


class UserContext(BaseModel):
    """Identity and scope taken from the verified JWT. Never supplied by the LLM."""

    model_config = ConfigDict(frozen=True)

    user_id: int
    role: Role
    employee_id: int | None = None

    @model_validator(mode="after")
    def _employee_needs_employee_id(self) -> Self:
        if self.role is Role.EMPLOYEE and self.employee_id is None:
            raise ValueError("Employee tokens must carry employee_id")
        return self


# ---- /ai API contracts ----

AI_LABEL = "AI-generated"
LeaveType = Literal["annual", "sick", "casual", "unpaid"]

_KPI_MAX_BYTES = 8192
_KPI_MAX_DEPTH = 4
_KPI_MAX_STR = 100
_KPI_MAX_ITEMS = 200


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChatRequest(RequestModel):
    message: str = Field(min_length=1, max_length=1000)


class SmartLeaveRequest(RequestModel):
    text: str = Field(min_length=1, max_length=500)


def _check_kpi(value: Any, depth: int = 1) -> None:
    if depth > _KPI_MAX_DEPTH:
        raise ValueError("kpis nested too deeply")
    if isinstance(value, dict):
        if len(value) > _KPI_MAX_ITEMS:
            raise ValueError("kpis too large")
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > _KPI_MAX_STR:
                raise ValueError("kpi names must be short strings")
            _check_kpi(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > _KPI_MAX_ITEMS:
            raise ValueError("kpis too large")
        for v in value:
            _check_kpi(v, depth + 1)
    elif isinstance(value, str):
        if len(value) > _KPI_MAX_STR:
            raise ValueError("kpi text values must be short")
    elif value is not None and not isinstance(value, bool | int | float):
        raise ValueError("unsupported kpi value")


class SummarizeRequest(RequestModel):
    kpis: dict[str, Any] = Field(min_length=1)

    @field_validator("kpis")
    @classmethod
    def _bounded_plain_data(cls, v: dict[str, Any]) -> dict[str, Any]:
        _check_kpi(v)
        if len(json.dumps(v, separators=(",", ":"))) > _KPI_MAX_BYTES:
            raise ValueError("kpis exceed 8KB")
        return v


class AIEnvelope(BaseModel):
    success: bool = True
    fallback: bool = False
    ai_generated: Literal[True] = True
    label: str = AI_LABEL


class ChatResponse(AIEnvelope):
    answer: str


class SummarizeResponse(AIEnvelope):
    summary: str = ""
    bullets: list[str] = []


class SmartLeave(BaseModel):
    type: LeaveType
    start: date
    end: date
    reason: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self


class SmartLeaveResponse(AIEnvelope):
    data: SmartLeave | None = None
