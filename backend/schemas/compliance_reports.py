from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models import ComplianceReportStatus, ComplianceReportType
from backend.schemas.students import StudentRead
from backend.validation import normalize_optional_text


class ComplianceReportGenerateRequest(BaseModel):
    student_id: int = Field(gt=0)
    school_year_id: int = Field(gt=0)
    report_type: ComplianceReportType
    grading_period_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator('notes')
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return normalize_optional_text(value, field_name='Compliance report notes', max_length=2000)


class ComplianceReportSummaryRead(BaseModel):
    id: int
    family_id: int
    student_id: int
    school_year_id: int
    state_code: str
    report_type: ComplianceReportType
    generated_at: datetime
    generated_by_user_id: int | None
    generated_by_name: str | None = None
    status: ComplianceReportStatus
    notes: str | None
    student_name: str
    school_year_name: str
    period_label: str | None = None
    title: str


class ComplianceReportRead(ComplianceReportSummaryRead):
    student: StudentRead | None = None
    data: dict[str, Any]


class RequiredComplianceReportRead(BaseModel):
    report_type: ComplianceReportType
    label: str
    description: str
    cadence: str
    required_count: int
    generated_count: int
    completed_count: int
    outstanding_count: int
    is_complete: bool


class RequiredComplianceReportListResponse(BaseModel):
    state_code: str
    student_id: int | None = None
    school_year_id: int | None = None
    items: list[RequiredComplianceReportRead]

