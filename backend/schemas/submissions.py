from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.grading import GradingJobRead


class SubmissionVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    student_id: int
    file_path: str
    file_url: str | None = None
    original_filename: str
    file_name: str
    file_type: str
    file_size_bytes: int
    image_width: int | None = None
    image_height: int | None = None
    page_count: int | None = None
    submission_version: int
    parent_submission_id: int | None = None
    is_current: bool
    ocr_text: str | None
    grading_job: GradingJobRead | None = None
    uploaded_at: datetime


class SubmissionRead(SubmissionVersionRead):
    pass


class SubmissionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    student_id: int
    file_path: str
    file_url: str | None = None
    original_filename: str
    file_name: str
    file_type: str
    file_size_bytes: int
    submission_version: int
    parent_submission_id: int | None = None
    is_current: bool
    grading_job: GradingJobRead | None = None
    uploaded_at: datetime


class SubmissionListResponse(BaseModel):
    items: list[SubmissionListItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class SubmissionDetail(SubmissionRead):
    version_history: list[SubmissionVersionRead] = Field(default_factory=list)
