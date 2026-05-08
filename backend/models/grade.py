import enum

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class GradedBy(str, enum.Enum):
    human = "human"
    ai = "ai"
    ai_human = "ai+human"


class Grade(TimestampMixin, Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    letter_grade: Mapped[str | None] = mapped_column(String(4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_by: Mapped[GradedBy] = mapped_column(Enum(GradedBy, name="graded_by"), nullable=False, default=GradedBy.human)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    submission = relationship("Submission", back_populates="grade")
    student = relationship("Student", back_populates="grades")
