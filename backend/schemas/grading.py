from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models.grading_job import GradingJobStatus


class GradingStepRead(BaseModel):
    timestamp: str
    status: str
    detail: str | None = None
    payload: dict[str, Any] | None = None


class GradingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    created_by_user_id: int
    submission_id: int
    assignment_id: int | None = None
    assignment_title: str | None = None
    student_id: int | None = None
    student_name: str | None = None
    file_path: str | None = None
    file_url: str | None = None
    file_type: str | None = None
    status: GradingJobStatus
    ocr_result: str | None = None
    ai_grade: float | None = None
    ai_feedback: str | None = None
    ai_confidence: float | None = None
    ai_response: str | None = None
    answer_key_result: dict[str, Any] | None = None
    status_history: list[dict[str, Any]] = Field(default_factory=list)
    human_override_details: dict[str, Any] | None = None
    manual_review_reason: str | None = None
    ocr_retry_count: int = 0
    ai_retry_count: int = 0
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
