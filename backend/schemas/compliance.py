from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from backend.models import ComplianceRuleType, ComplianceState
from backend.schemas.students import StudentRead
from backend.validation import normalize_optional_text, normalize_text


def _normalize_state_code(value: str) -> str:
    normalized = normalize_text(value, field_name='State code')
    if len(normalized) > 8:
        raise ValueError('State code must be 8 characters or fewer')
    return normalized.upper()


class ComplianceRuleCreate(BaseModel):
    state_code: str | None = Field(default=None, min_length=2, max_length=8)
    rule_type: ComplianceRuleType
    rule_name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    threshold_value: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    threshold_unit: str = Field(min_length=1, max_length=32)
    subjects_list: list[str] | None = None
    is_active: bool = True

    @field_validator('state_code')
    @classmethod
    def validate_state_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_state_code(value)

    @field_validator('rule_name', 'description', 'threshold_unit')
    @classmethod
    def validate_text_fields(cls, value: str, info) -> str:
        return normalize_text(value, field_name=info.field_name.replace('_', ' ').title())

    @field_validator('subjects_list')
    @classmethod
    def validate_subjects_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [normalize_text(item, field_name='Required subject') for item in value if item and item.strip()]
        return cleaned or None


class ComplianceRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int | None
    state_code: str
    rule_type: ComplianceRuleType
    rule_name: str
    description: str
    threshold_value: Decimal
    threshold_unit: str
    subjects_list: list[str] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_custom(self) -> bool:
        return self.family_id is not None


class ComplianceStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    student_id: int
    school_year_id: int
    rule_id: int
    status: ComplianceState
    current_value: Decimal
    required_value: Decimal
    last_checked_at: datetime
    notes: str | None
    rule: ComplianceRuleRead


class ComplianceStudentStatusResponse(BaseModel):
    student_id: int
    school_year_id: int | None
    state_code: str
    checked_at: datetime
    statuses: list[ComplianceStatusRead]
    summary_counts: dict[ComplianceState, int]


class ComplianceDashboardStudent(BaseModel):
    student: StudentRead
    statuses: list[ComplianceStatusRead]
    summary_counts: dict[ComplianceState, int]


class ComplianceDashboardResponse(BaseModel):
    state_code: str
    school_year_id: int | None
    checked_at: datetime
    students: list[ComplianceDashboardStudent]


class FamilyComplianceStateUpdate(BaseModel):
    state_code: str = Field(min_length=2, max_length=8)

    @field_validator('state_code')
    @classmethod
    def validate_state_code(cls, value: str) -> str:
        return _normalize_state_code(value)


class FamilyComplianceStateRead(BaseModel):
    state_code: str


class ComplianceRuleSummary(BaseModel):
    total_rules: int
    active_rules: int


class ComplianceRuleListResponse(BaseModel):
    state_code: str
    summary: ComplianceRuleSummary
    rules: list[ComplianceRuleRead]
