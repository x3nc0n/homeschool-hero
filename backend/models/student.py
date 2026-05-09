from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Student(TimestampMixin, Base):
    __tablename__ = 'students'
    __table_args__ = (UniqueConstraint('family_id', 'name', name='uq_students_family_id_name'),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey('families.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    assignment_targets = relationship('AssignmentTarget', back_populates='student', cascade='all, delete-orphan')
    submissions = relationship('Submission', back_populates='student', cascade='all, delete-orphan')
    grades = relationship('Grade', back_populates='student', cascade='all, delete-orphan')
    quiz_attempts = relationship('QuizAttempt', back_populates='student', cascade='all, delete-orphan')
    viewer_memberships = relationship('FamilyMembership', back_populates='student')
    viewer_invitations = relationship('Invitation', back_populates='student')
    schedules = relationship('Schedule', back_populates='student', cascade='all, delete-orphan')
    lesson_plans = relationship('LessonPlan', back_populates='student', cascade='all, delete-orphan')
    pacing_targets = relationship('PacingTarget', back_populates='student', cascade='all, delete-orphan')
    attendance_records = relationship('AttendanceRecord', back_populates='student', cascade='all, delete-orphan')
