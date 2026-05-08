from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    student_id: int
    file_path: str
    file_url: str | None = None
    file_type: str
    ocr_text: str | None
    uploaded_at: datetime
