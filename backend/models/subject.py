from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.gradebook import SubjectGradingMode


class Subject(TimestampMixin, Base):
    __tablename__ = 'subjects'
    __table_args__ = (UniqueConstraint('family_id', 'name', name='uq_subjects_family_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default='#4f46e5', server_default='#4f46e5')
    grading_mode: Mapped[SubjectGradingMode] = mapped_column(
        Enum(SubjectGradingMode, name='subject_grading_mode'),
        nullable=False,
        default=SubjectGradingMode.points,
        server_default=SubjectGradingMode.points.value,
    )
    grade_scale_id: Mapped[int | None] = mapped_column(ForeignKey('grade_scales.id', ondelete='SET NULL'), nullable=True, index=True)

    assignments = relationship('Assignment', back_populates='subject', cascade='all, delete-orphan')
    grade_categories = relationship('GradeCategory', back_populates='subject', cascade='all, delete-orphan', order_by='GradeCategory.name')
    grade_scale = relationship('GradeScale', back_populates='subjects', lazy='selectin')
    quizzes = relationship('Quiz', back_populates='subject', cascade='all, delete-orphan')
    schedule_blocks = relationship('ScheduleBlock', back_populates='subject')
    schedule_overrides = relationship('ScheduleOverride', back_populates='subject')
    portfolio_entries = relationship('PortfolioEntry', back_populates='subject')
