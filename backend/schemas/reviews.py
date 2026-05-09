from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models import ReviewItemStatus, ReviewPriority


class ReviewCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ReviewCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    review_item_id: int
    author_user_id: int
    author_name: str
    body: str
    created_at: datetime
    updated_at: datetime


class ReviewApproveRequest(BaseModel):
    score: float | None = Field(default=None, ge=0)
    feedback: str | None = None
    notes: str | None = None
    override_reason: str | None = None


class ReviewRejectRequest(BaseModel):
    reason: str | None = None
    notes: str | None = None


class ReviewRegradeRequest(BaseModel):
    reason: str | None = None


class ReviewAssignRequest(BaseModel):
    assigned_to_user_id: int = Field(gt=0)


class ReviewBulkApproveRequest(BaseModel):
    review_ids: list[int] = Field(min_length=1)
    notes: str | None = None
    override_reason: str | None = None


class ReviewBulkAssignRequest(BaseModel):
    review_ids: list[int] = Field(min_length=1)
    assigned_to_user_id: int = Field(gt=0)


class ReviewBulkResponse(BaseModel):
    updated: int
    items: list['ReviewItemRead']


class ReviewReviewerRead(BaseModel):
    user_id: int
    display_name: str
    email: str
    role: str


class ReviewItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    submission_id: int
    grading_job_id: int
    assignment_id: int | None = None
    assignment_title: str | None = None
    subject_id: int | None = None
    subject_name: str | None = None
    student_id: int | None = None
    student_name: str | None = None
    assigned_to_user_id: int | None = None
    assigned_to_name: str | None = None
    reviewed_by_user_id: int | None = None
    reviewed_by_name: str | None = None
    status: ReviewItemStatus
    priority: ReviewPriority
    ai_suggested_grade: float | None = None
    ai_confidence: float | None = None
    reviewer_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    submission_file_url: str | None = None
    submission_file_path: str | None = None
    submission_file_type: str | None = None
    submission_image_url: str | None = None
    ocr_text: str | None = None
    ai_feedback: str | None = None
    ai_response: str | None = None
    manual_review_reason: str | None = None
    answer_key_result: dict[str, Any] | None = None
    status_history: list[dict[str, Any]] = Field(default_factory=list)
    comments: list[ReviewCommentRead] = Field(default_factory=list)


ReviewBulkResponse.model_rebuild()
