from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field

from backend.models import ComplianceState, FamilyRole, ScheduleOverrideType


class DashboardScheduleItem(BaseModel):
    student_id: int
    student_name: str
    schedule_id: int
    schedule_name: str
    subject_id: int
    subject_name: str
    subject_color: str | None = None
    date: date
    start_time: time
    end_time: time
    source: str
    override_type: ScheduleOverrideType | None = None
    location: str | None = None
    notes: str | None = None
    reason: str | None = None


class DashboardAssignmentItem(BaseModel):
    assignment_id: int
    title: str
    subject_id: int | None = None
    subject_name: str | None = None
    student_id: int | None = None
    student_name: str | None = None
    due_date: datetime
    status: str
    days_until_due: int


class DashboardGradeItem(BaseModel):
    grade_id: int
    assignment_id: int | None = None
    assignment_title: str
    subject_name: str | None = None
    student_id: int
    student_name: str
    score: float
    max_score: float
    percent: float
    letter_grade: str | None = None
    graded_at: datetime


class DashboardAttendanceItem(BaseModel):
    student_id: int
    student_name: str
    date: date
    status: str
    instructional_hours: Decimal | None = None
    notes: str | None = None


class DashboardPacingAlertItem(BaseModel):
    student_id: int
    student_name: str
    pacing_target_id: int
    unit_name: str
    package_name: str
    target_end_date: date
    remaining_lessons: int
    status: str


class DashboardComplianceWarningItem(BaseModel):
    student_id: int
    student_name: str
    rule_name: str
    status: ComplianceState
    current_value: Decimal
    required_value: Decimal
    threshold_unit: str
    last_checked_at: datetime
    notes: str | None = None


class DashboardStudentSummary(BaseModel):
    student_id: int
    student_name: str
    current_gpa: float | None = None
    attendance_rate: float | None = None
    assignments_due_count: int = 0
    past_due_count: int = 0
    pacing_status: str | None = None
    compliance_status: ComplianceState | None = None


class DashboardSystemStatus(BaseModel):
    status: str
    checked_at: datetime
    healthy_services: int
    degraded_services: int
    unhealthy_services: int
    not_configured_services: int
    affected_services: list[str] = Field(default_factory=list)


class DashboardRead(BaseModel):
    role: FamilyRole
    generated_at: datetime
    selected_student_id: int | None = None
    today_schedule: list[DashboardScheduleItem] = Field(default_factory=list)
    upcoming_assignments: list[DashboardAssignmentItem] = Field(default_factory=list)
    past_due_assignments: list[DashboardAssignmentItem] = Field(default_factory=list)
    recent_grades: list[DashboardGradeItem] = Field(default_factory=list)
    attendance_today: list[DashboardAttendanceItem] = Field(default_factory=list)
    pacing_alerts: list[DashboardPacingAlertItem] = Field(default_factory=list)
    compliance_warnings: list[DashboardComplianceWarningItem] = Field(default_factory=list)
    system_status: DashboardSystemStatus | None = None
    student_summaries: list[DashboardStudentSummary] = Field(default_factory=list)
