from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Subject(TimestampMixin, Base):
    __tablename__ = 'subjects'
    __table_args__ = (UniqueConstraint('family_id', 'name', name='uq_subjects_family_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default='#4f46e5', server_default='#4f46e5')

    assignments = relationship('Assignment', back_populates='subject', cascade='all, delete-orphan')
    quizzes = relationship('Quiz', back_populates='subject', cascade='all, delete-orphan')
    schedule_blocks = relationship('ScheduleBlock', back_populates='subject')
    schedule_overrides = relationship('ScheduleOverride', back_populates='subject')
    portfolio_entries = relationship('PortfolioEntry', back_populates='subject')
